from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort
from flask_login import current_user
from models import db, ODRequest, User, Leaderboard
from sqlalchemy import func
from utils.emails import send_status_email
import pandas as pd
import io
from datetime import datetime

admin = Blueprint('admin', __name__)


def _check_admin():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.role not in ('Admin', 'HOD'):
        abort(403)
    return None


@admin.before_request
def before_request():
    if not current_user.is_authenticated or current_user.role != 'Admin':
        return redirect(url_for('auth.login'))


# ── Dashboard ──────────────────────────────────────────────────
@admin.route('/dashboard')
def dashboard():
    # Admin only
    if current_user.role != 'Admin':
        abort(403)
    ods      = ODRequest.query.order_by(ODRequest.created_at.desc()).all()
    students = User.query.filter_by(role='Student').order_by(User.name).all()
    return render_template('admin/dashboard.html', ods=ods, students=students)


# ── Approve / Reject ───────────────────────────────────────────
@admin.route('/approve/<int:od_id>')
def approve(od_id):
    if current_user.role != 'Admin':
        abort(403)
    od = ODRequest.query.get_or_404(od_id)
    od.admin_status = 'Approved'
    if od.hod_status == 'Approved':
        od.final_status = 'Approved'
        send_status_email(od.student, od, 'Approved')
    db.session.commit()
    flash(f'OD for {od.student.name} approved by Admin.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/reject/<int:od_id>')
def reject(od_id):
    if current_user.role != 'Admin':
        abort(403)
    od = ODRequest.query.get_or_404(od_id)
    od.admin_status  = 'Rejected'
    od.final_status  = 'Rejected'
    send_status_email(od.student, od, 'Rejected')
    db.session.commit()
    flash(f'OD for {od.student.name} rejected by Admin.', 'success')
    return redirect(url_for('admin.dashboard'))


# ── Manual Override ────────────────────────────────────────────
@admin.route('/manual_status/<int:od_id>', methods=['POST'])
def manual_status(od_id):
    if current_user.role != 'Admin':
        abort(403)
    od = ODRequest.query.get_or_404(od_id)
    new_status = request.form.get('final_status')
    if new_status in ('Approved', 'Rejected', 'Pending'):
        od.final_status = new_status
        db.session.commit()
        flash(f'Final status for {od.student.name}\'s OD set to {new_status}.', 'success')
    return redirect(url_for('admin.dashboard'))


# ── Penalty Override ───────────────────────────────────────────
@admin.route('/override_penalty/<int:user_id>')
def override_penalty(user_id):
    if current_user.role != 'Admin':
        abort(403)
    user = User.query.get_or_404(user_id)
    user.is_under_penalty = False
    user.penalty_end_date = None
    db.session.commit()
    flash(f'Penalty removed for {user.name}.', 'success')
    return redirect(url_for('admin.dashboard'))


# ── CSV Export ─────────────────────────────────────────────────
@admin.route('/export_csv')
def export_csv():
    if current_user.role != 'Admin':
        abort(403)
    ods = ODRequest.query.order_by(ODRequest.created_at).all()
    data = []
    for i, od in enumerate(ods, 1):
        data.append({
            'S.No':              i,
            'Batch Number':      od.student.batch_number or '',
            'Register Number':   od.student.username,
            'Name':              od.student.name,
            'Department':        od.student.department or '',
            'Year':              od.student.year or '',
            'Section':           od.student.section or '',
            'Event':             od.event_name,
            'College Name':      od.college_name,
            'Number of Days':    od.number_of_days,
            'Date':              od.od_date.strftime('%Y-%m-%d'),
            'Day':               od.od_day,
            'HOD Status':        od.hod_status,
            'Admin Status':      od.admin_status,
            'Final Status':      od.final_status,
            'Verification':      od.verification_status,
            'Is Leave':          'Yes' if od.is_leave else 'No',
            'Approval Letter':   od.approval_letter_path or '',
            'Brochure':          od.brochure_path or '',
            'Certificate':       od.certificate_path or '',
            'Submitted On':      od.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    df  = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    filename = f"od_records_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return send_file(buf, mimetype='text/csv', download_name=filename, as_attachment=True)


# ── Analytics ──────────────────────────────────────────────────
@admin.route('/analytics')
def analytics():
    ods      = ODRequest.query.all()
    students = User.query.filter_by(role='Student').all()

    # ── Department counts ──
    dept_counts = {}
    for od in ods:
        dept = od.student.department or 'Unknown'
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    dept_labels = list(dept_counts.keys())
    dept_data   = list(dept_counts.values())

    # ── Section counts ──
    section_counts = {}
    for od in ods:
        sec = od.student.section or 'Unknown'
        section_counts[sec] = section_counts.get(sec, 0) + 1

    section_labels = list(section_counts.keys())
    section_data   = list(section_counts.values())

    # ── Monthly trend (current year) ──
    current_year   = datetime.utcnow().year
    month_names    = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    monthly_counts = [0] * 12
    for od in ods:
        if od.created_at.year == current_year:
            monthly_counts[od.created_at.month - 1] += 1

    # ── Status breakdown ──
    approved = sum(1 for od in ods if od.final_status == 'Approved')
    pending  = sum(1 for od in ods if od.final_status == 'Pending')
    rejected = sum(1 for od in ods if od.final_status == 'Rejected')

    # ── Summary stats ──
    total_ods     = len(ods)
    approved_ods  = approved
    total_points  = db.session.query(func.sum(Leaderboard.points)).scalar() or 0
    total_students = len(students)

    # ── Leaderboard: top 10 by verified points ──
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

    # ── Leaderboard section-wise ──
    section_leaderboards = {}
    for student in top_students:
        sec = student.section or 'General'
        if sec not in section_leaderboards:
            section_leaderboards[sec] = []
        section_leaderboards[sec].append(student)

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
        # Summary stats
        total_ods=total_ods,
        approved_ods=approved_ods,
        total_points=total_points,
        total_students=total_students,
        # Leaderboard
        top_students=top_students,
        section_leaderboards=section_leaderboards,
        # Legacy (dept_counts kept for any old template refs)
        dept_counts=dept_counts,
    )
