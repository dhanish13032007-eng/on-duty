"""
hod.py — HOD blueprint.
Handles: dashboard, OD approve/reject (with AJAX support), certificate verification,
         penalty removal.
"""
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, abort, jsonify, request)
from flask_login import login_required, current_user
from models import db, ODRequest, User
from utils.emails import send_status_email

hod = Blueprint('hod', __name__)


# ── Auth guard ─────────────────────────────────────────────────────────────
@hod.before_request
def before_request():
    if not current_user.is_authenticated or current_user.role != 'HOD':
        return redirect(url_for('auth.login'))


# ── Dashboard ──────────────────────────────────────────────────────────────
@hod.route('/dashboard')
def dashboard():
    """
    HOD dashboard: shows all ODs from the HOD's department.
    Includes stat cards and filterable table.
    """
    try:
        if current_user.department:
            ods = (ODRequest.query
                   .join(User)
                   .filter(User.department == current_user.department)
                   .order_by(ODRequest.created_at.desc())
                   .all())
        else:
            ods = ODRequest.query.order_by(ODRequest.created_at.desc()).all()

        # Stat counts for dashboard cards
        stats = {
            'total':    len(ods),
            'pending':  sum(1 for o in ods if o.hod_status == 'Pending'),
            'approved': sum(1 for o in ods if o.hod_status == 'Approved'),
            'rejected': sum(1 for o in ods if o.hod_status == 'Rejected'),
            'cert_pending': sum(
                1 for o in ods if o.verification_status == 'Pending Verification'
            ),
        }
    except Exception as e:
        ods, stats = [], {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0, 'cert_pending': 0}

    return render_template('hod/dashboard.html', ods=ods, stats=stats)


# ── Approve ────────────────────────────────────────────────────────────────
@hod.route('/approve/<int:od_id>', methods=['GET', 'POST'])
def approve(od_id):
    """Approve an OD request. Supports both normal redirect and AJAX JSON."""
    od = ODRequest.query.get_or_404(od_id)
    _check_dept(od)

    try:
        od.hod_status = 'Approved'
        # Fully approve only when admin has also approved
        if od.admin_status == 'Approved':
            od.final_status = 'Approved'
            try:
                send_status_email(od.student, od, 'Approved')
            except Exception:
                pass

        db.session.commit()

        if _is_ajax():
            return jsonify({
                'ok': True,
                'hod_status':   od.hod_status,
                'final_status': od.final_status,
                'message':      f'OD for {od.student.name} approved by HOD.'
            })

        flash(f'OD request for {od.student.name} approved by HOD.', 'success')

    except Exception as e:
        db.session.rollback()
        if _is_ajax():
            return jsonify({'ok': False, 'message': 'Database error. Please try again.'}), 500
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('hod.dashboard'))


# ── Reject ─────────────────────────────────────────────────────────────────
@hod.route('/reject/<int:od_id>', methods=['GET', 'POST'])
def reject(od_id):
    """Reject an OD request. Supports AJAX JSON response."""
    od = ODRequest.query.get_or_404(od_id)
    _check_dept(od)

    try:
        od.hod_status   = 'Rejected'
        od.final_status = 'Rejected'
        db.session.commit()

        try:
            send_status_email(od.student, od, 'Rejected')
        except Exception:
            pass

        if _is_ajax():
            return jsonify({
                'ok': True,
                'hod_status':   od.hod_status,
                'final_status': od.final_status,
                'message':      f'OD for {od.student.name} rejected by HOD.'
            })

        flash(f'OD request for {od.student.name} rejected by HOD.', 'success')

    except Exception as e:
        db.session.rollback()
        if _is_ajax():
            return jsonify({'ok': False, 'message': 'Database error. Please try again.'}), 500
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('hod.dashboard'))


# ── Verify Certificate ─────────────────────────────────────────────────────
@hod.route('/verify_certificate/<int:od_id>')
def verify_certificate(od_id):
    """HOD marks a student's uploaded certificate as verified."""
    od = ODRequest.query.get_or_404(od_id)
    _check_dept(od)

    try:
        if od.verification_status != 'Pending Verification':
            flash('This certificate is not pending verification.', 'error')
            return redirect(url_for('hod.dashboard'))

        od.verification_status = 'Verified'
        db.session.commit()
        flash(f'Certificate for {od.student.name} verified successfully. ✓', 'success')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while verifying. Please try again.', 'error')

    return redirect(url_for('hod.dashboard'))


# ── Remove Penalty ─────────────────────────────────────────────────────────
@hod.route('/remove_penalty/<int:user_id>')
def remove_penalty(user_id):
    """HOD can remove a penalty for a student in their department."""
    user = User.query.get_or_404(user_id)

    if current_user.department and user.department != current_user.department:
        abort(403)

    try:
        user.is_under_penalty = False
        user.penalty_end_date = None
        db.session.commit()
        flash(f'Penalty removed for {user.name}.', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('hod.dashboard'))


# ── Helpers ────────────────────────────────────────────────────────────────
def _check_dept(od):
    """Ensure the HOD can only act on ODs from their department."""
    if current_user.department and od.student.department != current_user.department:
        abort(403)


def _is_ajax():
    """Detect if the request is an AJAX call (XMLHttpRequest or JSON Accept)."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
