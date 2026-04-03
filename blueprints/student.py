"""
student.py — Student-facing blueprint.
Handles: dashboard, OD application (login required), certificate upload, file serving.

Validation rules enforced server-side:
  1. Student must be logged in to apply.
  2. Only one OD may be applied per calendar month.
  3. Cannot apply if any existing approved OD has a pending certificate upload.
  4. Student cannot apply if they are under penalty.
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, send_from_directory, current_app,
                   jsonify)
from flask_login import login_required, current_user
from datetime import datetime
from models import db, ODRequest, Leaderboard, User
from utils.helpers import save_upload, validate_upload
from utils.penalties import evaluate_penalties
from utils.emails import send_application_email
import os

student = Blueprint('student', __name__)


# ── Dashboard ──────────────────────────────────────────────────────────────
@student.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard: shows all their OD requests and leaderboard points."""
    if current_user.role != 'Student':
        abort(403)

    try:
        ods = (ODRequest.query
               .filter_by(student_id=current_user.id)
               .order_by(ODRequest.created_at.desc())
               .all())

        # Sum points only from fully verified leaderboard entries
        points = sum(
            lb.points for lb in current_user.leaderboard_entries
            if lb.od_request.verification_status == 'Verified'
        )
    except Exception as e:
        current_app.logger.error(f'Dashboard error: {e}')
        ods, points = [], 0

    return render_template('student/dashboard.html', ods=ods, points=points)


# ── Apply for OD ───────────────────────────────────────────────────────────
@student.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    """Submit a new OD application. Multiple backend validations enforced."""
    if current_user.role != 'Student':
        abort(403)

    # ── Block: under penalty ───────────────────────────────────────────────
    if current_user.is_under_penalty:
        if _is_ajax(): return jsonify({'ok': False, 'message': 'You are under penalty and cannot apply.'})
        flash('You are under penalty and cannot apply for OD at this time.', 'error')
        return redirect(url_for('student.dashboard'))

    # ── Block: pending certificate upload ─────────────────────────────────
    # Student must upload their certificate for all approved ODs first
    pending_cert = ODRequest.query.filter_by(
        student_id=current_user.id,
        final_status='Approved',
        verification_status='Pending Upload'
    ).first()
    if pending_cert:
        msg = f'You must upload your certificate for "{pending_cert.event_name}" before applying for a new OD.'
        if _is_ajax(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'error')
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        # OD info from form
        event_name     = request.form.get('event_name', '').strip()
        college_name   = request.form.get('college_name', '').strip()
        od_date_str    = request.form.get('od_date', '').strip()
        od_day         = request.form.get('od_day', '').strip()
        number_of_days = request.form.get('number_of_days', '1').strip()

        # Basic field validation
        if not all([event_name, college_name, od_date_str, od_day]):
            if _is_ajax(): return jsonify({'ok': False, 'message': 'Please fill in all required fields.'})
            flash('Please fill in all required fields.', 'error')
            return render_template('student/apply.html')

        try:
            od_date = datetime.strptime(od_date_str, '%Y-%m-%d').date()
        except ValueError:
            if _is_ajax(): return jsonify({'ok': False, 'message': 'Invalid date format.'})
            flash('Invalid date format. Please use the date picker.', 'error')
            return render_template('student/apply.html')

        try:
            num_days = int(number_of_days)
            if num_days < 1 or num_days > 30:
                raise ValueError
        except ValueError:
            if _is_ajax(): return jsonify({'ok': False, 'message': 'Number of days must be between 1 and 30.'})
            flash('Number of days must be between 1 and 30.', 'error')
            return render_template('student/apply.html')

        # ── Block: once per month (DB check) ──────────────────────────────
        existing_this_month = ODRequest.query.filter(
            ODRequest.student_id == current_user.id,
            db.extract('month', ODRequest.od_date) == od_date.month,
            db.extract('year',  ODRequest.od_date) == od_date.year,
        ).first()
        if existing_this_month:
            msg = f'You already have an OD application for {od_date.strftime("%B %Y")}. Only one OD per month is allowed.'
            if _is_ajax(): return jsonify({'ok': False, 'message': msg})
            flash(msg, 'error')
            return render_template('student/apply.html')

        # ── File uploads ───────────────────────────────────────────────────
        approval_letter = request.files.get('approval_letter')
        brochure        = request.files.get('brochure')

        # Validate approval letter (required)
        if not approval_letter or not approval_letter.filename:
            if _is_ajax(): return jsonify({'ok': False, 'message': 'Approval letter is required.'})
            flash('Approval letter is required.', 'error')
            return render_template('student/apply.html')

        valid, err = validate_upload(approval_letter)
        if not valid:
            if _is_ajax(): return jsonify({'ok': False, 'message': f'Approval letter: {err}'})
            flash(f'Approval letter: {err}', 'error')
            return render_template('student/apply.html')

        # Validate brochure (required)
        if not brochure or not brochure.filename:
            if _is_ajax(): return jsonify({'ok': False, 'message': 'Event brochure is required.'})
            flash('Event brochure is required.', 'error')
            return render_template('student/apply.html')

        valid, err = validate_upload(brochure)
        if not valid:
            if _is_ajax(): return jsonify({'ok': False, 'message': f'Event brochure: {err}'})
            flash(f'Event brochure: {err}', 'error')
            return render_template('student/apply.html')

        try:
            approval_path = save_upload(approval_letter, folder='approvals')
            brochure_path = save_upload(brochure, folder='brochures')

            new_od = ODRequest(
                student_id=current_user.id,
                event_name=event_name,
                college_name=college_name,
                od_date=od_date,
                od_day=od_day,
                number_of_days=num_days,
                approval_letter_path=approval_path,
                brochure_path=brochure_path,
                hod_status='Pending',
                admin_status='Pending',
                final_status='Pending',
                verification_status='Pending Upload',
            )
            db.session.add(new_od)
            db.session.commit()

            # Send email notification (non-blocking)
            try:
                send_application_email(new_od)
            except Exception as mail_err:
                current_app.logger.warning(f'Email notification failed: {mail_err}')

            msg = 'OD application submitted successfully! HOD and Admin have been notified.'
            if _is_ajax(): return jsonify({'ok': True, 'message': msg, 'redirect': url_for('student.dashboard')})
            flash(msg, 'success')
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'OD submission error: {e}')
            if _is_ajax(): return jsonify({'ok': False, 'message': 'An error occurred while submitting your application. Please try again.'})
            flash('An error occurred while submitting your application. Please try again.', 'error')
            return render_template('student/apply.html')

    return render_template('student/apply.html')


# ── Upload Certificate ─────────────────────────────────────────────────────
@student.route('/upload_certificate/<int:od_id>', methods=['GET', 'POST'])
@login_required
def upload_certificate(od_id):
    """Student uploads their participation/achievement certificate post-event."""
    if current_user.role != 'Student':
        abort(403)

    od = ODRequest.query.get_or_404(od_id)

    # Security: only owning student can upload
    if od.student_id != current_user.id:
        abort(403)

    if od.final_status != 'Approved':
        msg = 'You can only upload a certificate for an approved OD.'
        if _is_ajax(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'error')
        return redirect(url_for('student.dashboard'))

    if od.verification_status == 'Verified':
        msg = 'This certificate has already been verified.'
        if _is_ajax(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'info')
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        certificate = request.files.get('certificate')
        achievement  = request.form.get('achievement', 'Participant')

        if not certificate or not certificate.filename:
            if _is_ajax(): return jsonify({'ok': False, 'message': 'Event certificate is required.'})
            flash('Event certificate is required.', 'error')
            return render_template('student/upload_certificate.html', od=od)

        # Validate upload
        valid, err = validate_upload(certificate)
        if not valid:
            if _is_ajax(): return jsonify({'ok': False, 'message': f'Certificate upload failed: {err}'})
            flash(f'Certificate upload failed: {err}', 'error')
            return render_template('student/upload_certificate.html', od=od)

        try:
            cert_path = save_upload(certificate, folder='certificates')
            if not cert_path:
                if _is_ajax(): return jsonify({'ok': False, 'message': 'File upload failed. Please try again.'})
                flash('File upload failed. Please try again.', 'error')
                return render_template('student/upload_certificate.html', od=od)

            od.certificate_path    = cert_path
            od.verification_status = 'Pending Verification'

            # Points mapping for achievements
            points_map = {
                'Participant': 10,
                '3rd Prize':   20,
                '2nd Prize':   30,
                'Winner':      50,
            }
            points = points_map.get(achievement, 10)

            # Prevent duplicate leaderboard entry
            existing_entry = Leaderboard.query.filter_by(od_request_id=od.id).first()
            if not existing_entry:
                leaderboard = Leaderboard(
                    student_id=current_user.id,
                    od_request_id=od.id,
                    achievement=achievement,
                    points=points,
                )
                db.session.add(leaderboard)

            db.session.commit()
            msg = 'Certificate uploaded! Your HOD will verify it shortly.'
            if _is_ajax(): return jsonify({'ok': True, 'message': msg, 'redirect': url_for('student.dashboard')})
            flash(msg, 'success')
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Certificate upload error: {e}')
            if _is_ajax(): return jsonify({'ok': False, 'message': 'An error occurred while uploading. Please try again.'})
            flash('An error occurred while uploading. Please try again.', 'error')

    return render_template('student/upload_certificate.html', od=od)


# ── File Serving ───────────────────────────────────────────────────────────
@student.route('/files/<path:filename>')
@login_required
def serve_file(filename):
    """
    Serve an uploaded file. If the stored path is a Cloudinary URL, redirect to it.
    Otherwise, serve from the local UPLOAD_FOLDER.
    """
    # Cloudinary URLs start with https://
    if filename.startswith('http'):
        return redirect(filename)

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

def _is_ajax():
    """Detect AJAX requests."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
