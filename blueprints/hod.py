from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, ODRequest, User
from utils.emails import send_status_email

hod = Blueprint('hod', __name__)


def _check_hod():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.role != 'HOD':
        abort(403)
    return None


@hod.before_request
def before_request():
    if not current_user.is_authenticated or current_user.role != 'HOD':
        return redirect(url_for('auth.login'))


@hod.route('/dashboard')
def dashboard():
    if current_user.department:
        ods = (ODRequest.query
               .join(User)
               .filter(User.department == current_user.department)
               .order_by(ODRequest.created_at.desc())
               .all())
    else:
        ods = ODRequest.query.order_by(ODRequest.created_at.desc()).all()

    return render_template('hod/dashboard.html', ods=ods)


@hod.route('/approve/<int:od_id>')
def approve(od_id):
    od = ODRequest.query.get_or_404(od_id)
    _check_dept(od)

    od.hod_status = 'Approved'
    # Fully approve only if admin also approved
    if od.admin_status == 'Approved':
        od.final_status = 'Approved'
        send_status_email(od.student, od, 'Approved')

    db.session.commit()
    flash(f'OD request for {od.student.name} approved by HOD.', 'success')
    return redirect(url_for('hod.dashboard'))


@hod.route('/reject/<int:od_id>')
def reject(od_id):
    od = ODRequest.query.get_or_404(od_id)
    _check_dept(od)

    od.hod_status  = 'Rejected'
    od.final_status = 'Rejected'
    send_status_email(od.student, od, 'Rejected')

    db.session.commit()
    flash(f'OD request for {od.student.name} rejected by HOD.', 'success')
    return redirect(url_for('hod.dashboard'))


@hod.route('/verify_certificate/<int:od_id>')
def verify_certificate(od_id):
    od = ODRequest.query.get_or_404(od_id)
    _check_dept(od)

    if od.verification_status != 'Pending Verification':
        flash('This certificate is not pending verification.', 'error')
        return redirect(url_for('hod.dashboard'))

    od.verification_status = 'Verified'
    db.session.commit()
    flash(f'Certificate for {od.student.name} verified successfully. ✓', 'success')
    return redirect(url_for('hod.dashboard'))


@hod.route('/remove_penalty/<int:user_id>')
def remove_penalty(user_id):
    """HOD can remove penalty for students in their department."""
    user = User.query.get_or_404(user_id)

    if current_user.department and user.department != current_user.department:
        abort(403)

    user.is_under_penalty = False
    user.penalty_end_date = None
    db.session.commit()
    flash(f'Penalty removed for {user.name}.', 'success')
    return redirect(url_for('hod.dashboard'))


def _check_dept(od):
    """Ensure HOD can only action ODs from their department."""
    if current_user.department and od.student.department != current_user.department:
        abort(403)
