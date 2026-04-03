"""
admin.py — Admin blueprint.
Handles: dashboard, OD approve/reject (with AJAX), penalty override,
         CSV export, and analytics dashboard.
"""
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, send_file, abort, jsonify, current_app)
from flask_login import current_user
from models import db, ODRequest, User, Leaderboard
from sqlalchemy import func
from utils.emails import send_status_email
import pandas as pd
import io
from datetime import datetime

admin = Blueprint('admin', __name__)


# ── Auth guard ─────────────────────────────────────────────────────────────
@admin.before_request
def before_request():
    if not current_user.is_authenticated or current_user.role != 'Admin':
        return redirect(url_for('auth.login'))


# ── Dashboard ──────────────────────────────────────────────────────────────
@admin.route('/dashboard')
def dashboard():
    """Admin dashboard: all OD requests with approve/reject and override controls."""
    try:
        ods      = ODRequest.query.order_by(ODRequest.created_at.desc()).all()
        students = User.query.filter_by(role='Student').order_by(User.name).all()

        stats = {
            'total':       len(ods),
            'pending':     sum(1 for o in ods if o.admin_status == 'Pending'),
            'approved':    sum(1 for o in ods if o.final_status == 'Approved'),
            'rejected':    sum(1 for o in ods if o.final_status == 'Rejected'),
            'under_penalty': sum(1 for s in students if s.is_under_penalty),
        }
    except Exception as e:
        current_app.logger.error(f'Admin dashboard error: {e}')
        ods, students, stats = [], [], {
            'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0, 'under_penalty': 0
        }

    return render_template('admin/dashboard.html', ods=ods, students=students, stats=stats)


# ── Approve ────────────────────────────────────────────────────────────────
@admin.route('/approve/<int:od_id>', methods=['GET', 'POST'])
def approve(od_id):
    """Admin approves an OD. Supports AJAX JSON response."""
    od = ODRequest.query.get_or_404(od_id)

    try:
        od.admin_status = 'Approved'
        if od.hod_status == 'Approved':
            od.final_status = 'Approved'
            try:
                send_status_email(od.student, od, 'Approved')
            except Exception:
                pass

        db.session.commit()

        if _is_ajax():
            return jsonify({
                'ok': True,
                'admin_status':  od.admin_status,
                'final_status':  od.final_status,
                'message':       f'OD for {od.student.name} approved by Admin.'
            })

        flash(f'OD for {od.student.name} approved by Admin.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Admin approve error: {e}')
        if _is_ajax():
            return jsonify({'ok': False, 'message': 'Database error.'}), 500
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('admin.dashboard'))


# ── Reject ─────────────────────────────────────────────────────────────────
@admin.route('/reject/<int:od_id>', methods=['GET', 'POST'])
def reject(od_id):
    """Admin rejects an OD. Supports AJAX JSON response."""
    od = ODRequest.query.get_or_404(od_id)

    try:
        od.admin_status = 'Rejected'
        od.final_status = 'Rejected'
        db.session.commit()

        try:
            send_status_email(od.student, od, 'Rejected')
        except Exception:
            pass

        if _is_ajax():
            return jsonify({
                'ok': True,
                'admin_status':  od.admin_status,
                'final_status':  od.final_status,
                'message':       f'OD for {od.student.name} rejected.'
            })

        flash(f'OD for {od.student.name} rejected by Admin.', 'success')

    except Exception as e:
        db.session.rollback()
        if _is_ajax():
            return jsonify({'ok': False, 'message': 'Database error.'}), 500
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('admin.dashboard'))


# ── Manual Override ────────────────────────────────────────────────────────
@admin.route('/manual_status/<int:od_id>', methods=['POST'])
def manual_status(od_id):
    """Admin manually overrides the final OD status."""
    od = ODRequest.query.get_or_404(od_id)
    new_status = request.form.get('final_status')

    if new_status not in ('Approved', 'Rejected', 'Pending'):
        flash('Invalid status value.', 'error')
        return redirect(url_for('admin.dashboard'))

    try:
        od.final_status = new_status
        db.session.commit()
        flash(f"Final status for {od.student.name}'s OD set to {new_status}.", 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('admin.dashboard'))


# ── Penalty Override ───────────────────────────────────────────────────────
@admin.route('/override_penalty/<int:user_id>')
def override_penalty(user_id):
    """Admin removes a student's penalty."""
    user = User.query.get_or_404(user_id)

    try:
        user.is_under_penalty = False
        user.penalty_end_date = None
        db.session.commit()
        flash(f'Penalty removed for {user.name}.', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('admin.dashboard'))


# ── CSV Export ─────────────────────────────────────────────────────────────
@admin.route('/export_csv')
def export_csv():
    """Export all OD records as a downloadable CSV file."""
    try:
        ods = ODRequest.query.order_by(ODRequest.created_at).all()
        data = []
        for i, od in enumerate(ods, 1):
            data.append({
                'S.No':             i,
                'Batch Number':     od.student.batch_number or '',
                'Register Number':  od.student.username,
                'Name':             od.student.name,
                'Department':       od.student.department or '',
                'Year':             od.student.year or '',
                'Section':          od.student.section or '',
                'Event':            od.event_name,
                'College Name':     od.college_name,
                'Number of Days':   od.number_of_days,
                'Date':             od.od_date.strftime('%Y-%m-%d'),
                'Day':              od.od_day,
                'HOD Status':       od.hod_status,
                'Admin Status':     od.admin_status,
                'Final Status':     od.final_status,
                'Verification':     od.verification_status,
                'Is Leave':         'Yes' if od.is_leave else 'No',
                'Approval Letter':  od.approval_letter_path or '',
                'Brochure':         od.brochure_path or '',
                'Certificate':      od.certificate_path or '',
                'Submitted On':     od.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        df  = pd.DataFrame(data)
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        filename = f"od_records_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        return send_file(buf, mimetype='text/csv', download_name=filename, as_attachment=True)

    except Exception as e:
        current_app.logger.error(f'CSV export error: {e}')
        flash('CSV export failed. Please try again.', 'error')
        return redirect(url_for('admin.dashboard'))


# ── Analytics ──────────────────────────────────────────────────────────────
@admin.route('/analytics')
def analytics():
    """
    Analytics dashboard with:
    - Department, section, monthly trend, status breakdown charts
    - Year-wise OD distribution
    - Top 5 events by application count
    - Leaderboard + section-wise breakdowns
    - Rejection rate and avg OD days metrics
    """
    try:
        ods      = ODRequest.query.all()
        students = User.query.filter_by(role='Student').all()

        # ── Department counts ──────────────────────────────────────────────
        dept_counts = {}
        for od in ods:
            dept = od.student.department or 'Unknown'
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        dept_labels = list(dept_counts.keys())
        dept_data   = list(dept_counts.values())

        # ── Section counts ─────────────────────────────────────────────────
        section_counts = {}
        for od in ods:
            sec = od.student.section or 'Unknown'
            section_counts[sec] = section_counts.get(sec, 0) + 1
        section_labels = sorted(section_counts.keys())
        section_data   = [section_counts[s] for s in section_labels]

        # ── Monthly trend (current year) ───────────────────────────────────
        current_year   = datetime.utcnow().year
        month_names    = ['Jan','Feb','Mar','Apr','May','Jun',
                          'Jul','Aug','Sep','Oct','Nov','Dec']
        monthly_counts = [0] * 12
        for od in ods:
            if od.created_at.year == current_year:
                monthly_counts[od.created_at.month - 1] += 1

        # ── Status breakdown ───────────────────────────────────────────────
        approved = sum(1 for od in ods if od.final_status == 'Approved')
        pending  = sum(1 for od in ods if od.final_status == 'Pending')
        rejected = sum(1 for od in ods if od.final_status == 'Rejected')

        # ── Year-wise OD distribution ──────────────────────────────────────
        year_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for od in ods:
            yr = od.student.year
            if yr in year_counts:
                year_counts[yr] += 1
        year_labels = ['Year 1', 'Year 2', 'Year 3', 'Year 4']
        year_data   = [year_counts[1], year_counts[2], year_counts[3], year_counts[4]]

        # ── Top 5 events by frequency ──────────────────────────────────────
        event_counts = {}
        for od in ods:
            event_counts[od.event_name] = event_counts.get(od.event_name, 0) + 1
        top_events = sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # ── Summary stats ──────────────────────────────────────────────────
        total_ods      = len(ods)
        total_points   = db.session.query(func.sum(Leaderboard.points)).scalar() or 0
        total_students = len(students)
        rejection_rate = round((rejected / total_ods * 100), 1) if total_ods else 0
        avg_days       = round(
            sum(od.number_of_days for od in ods) / total_ods, 1
        ) if total_ods else 0

        # ── Leaderboard: top 10 by verified points ─────────────────────────
        top_students = (
            db.session.query(
                User.name,
                User.department,
                User.section,
                func.sum(Leaderboard.points).label('total_points')
            )
            .join(Leaderboard, User.id == Leaderboard.student_id)
            .join(ODRequest, ODRequest.id == Leaderboard.od_request_id)
            .filter(ODRequest.verification_status == 'Verified')
            .group_by(User.id)
            .order_by(func.sum(Leaderboard.points).desc())
            .limit(10)
            .all()
        )

        # ── Section-wise top performers ────────────────────────────────────
        section_leaderboards = {}
        for s in top_students:
            sec = s.section or 'General'
            if sec not in section_leaderboards:
                section_leaderboards[sec] = []
            section_leaderboards[sec].append(s)

    except Exception as e:
        current_app.logger.error(f'Analytics error: {e}')
        # Return empty safe defaults
        dept_labels = dept_data = section_labels = section_data = []
        month_names = year_labels = year_data = []
        monthly_counts = top_events = []
        approved = pending = rejected = total_ods = total_points = 0
        total_students = rejection_rate = avg_days = 0
        top_students = []
        section_leaderboards = {}
        dept_counts = {}

    return render_template(
        'analytics/dashboard.html',
        # Chart data
        dept_labels=dept_labels,
        dept_data=dept_data,
        section_labels=section_labels,
        section_data=section_data,
        month_labels=month_names,
        monthly_data=monthly_counts,
        status_data=[approved, pending, rejected],
        year_labels=year_labels,
        year_data=year_data,
        # Top events
        top_events=top_events,
        # Summary stats
        total_ods=total_ods,
        approved_ods=approved,
        rejected_ods=rejected,
        total_points=total_points,
        total_students=total_students,
        rejection_rate=rejection_rate,
        avg_days=avg_days,
        # Leaderboard
        top_students=top_students,
        section_leaderboards=section_leaderboards,
    )


# ── Helper ─────────────────────────────────────────────────────────────────
def _is_ajax():
    """Detect AJAX requests."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
