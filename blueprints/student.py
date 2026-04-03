from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime
from models import db, ODRequest, Leaderboard
from utils.helpers import save_upload
from utils.penalties import evaluate_penalties
from utils.emails import send_application_email
from config import Config
import os

student = Blueprint('student', __name__)


# User is now not required to login to apply.
# We will create/find the student in the apply route.


@student.route('/dashboard')
@login_required
def dashboard():
    ods = ODRequest.query.filter_by(student_id=current_user.id)\
                         .order_by(ODRequest.created_at.desc()).all()
    # Sum points only from verified entries
    points = sum(
        lb.points for lb in current_user.leaderboard_entries
        if lb.od_request.verification_status == 'Verified'
    )
    return render_template('student/dashboard.html', ods=ods, points=points)


@student.route('/apply', methods=['GET', 'POST'])
def apply():
    if request.method == 'POST':
        # Student info
        username       = request.form.get('username', '').strip()
        name           = request.form.get('name', '').strip()
        department     = request.form.get('department', '').strip()
        section        = request.form.get('section', '').strip()
        year_str       = request.form.get('year', '')
        
        # OD info
        event_name     = request.form.get('event_name', '').strip()
        college_name   = request.form.get('college_name', '').strip()
        od_date_str    = request.form.get('od_date', '')
        od_day         = request.form.get('od_day', '')
        number_of_days = int(request.form.get('number_of_days', 1))

        if not all([username, name, event_name, college_name, od_date_str, od_day]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('student.apply'))

        try:
            od_date = datetime.strptime(od_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(url_for('student.apply'))

        approval_letter = request.files.get('approval_letter')
        brochure        = request.files.get('brochure')

        approval_path = save_upload(approval_letter, folder='approvals') if approval_letter and approval_letter.filename else None
        brochure_path = save_upload(brochure, folder='brochures')        if brochure and brochure.filename         else None

        # Find or create student user
        student_user = User.query.filter_by(username=username).first()
        if not student_user:
            student_user = User(
                username=username,
                name=name,
                email=f"{username}@dummy.com",
                role='Student',
                password_hash='not_needed',
                department=department,
                section=section,
                year=int(year_str) if year_str.isdigit() else None
            )
            db.session.add(student_user)
            db.session.flush()

        new_od = ODRequest(
            student_id=student_user.id,
            event_name=event_name,
            college_name=college_name,
            od_date=od_date,
            od_day=od_day,
            number_of_days=number_of_days,
            approval_letter_path=approval_path,
            brochure_path=brochure_path,
            hod_status='Pending',
            admin_status='Pending',
            final_status='Pending',
            verification_status='Pending Upload',
        )
        db.session.add(new_od)
        db.session.commit()

        # Send email notification
        try:
            send_application_email(new_od)
        except:
            pass # ignore email errors

        flash('OD Application submitted successfully! HOD and Admin have been notified.', 'success')
        return redirect(url_for('auth.index'))

    return render_template('student/apply.html')


@student.route('/upload_certificate/<int:od_id>', methods=['GET', 'POST'])
@login_required
def upload_certificate(od_id):
    od = ODRequest.query.get_or_404(od_id)

    # Security: only the owning student
    if od.student_id != current_user.id:
        abort(403)

    if od.final_status != 'Approved':
        flash('You can only upload a certificate for an approved OD.', 'error')
        return redirect(url_for('student.dashboard'))

    if od.verification_status == 'Verified':
        flash('This certificate has already been verified.', 'info')
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        certificate = request.files.get('certificate')
        achievement  = request.form.get('achievement', 'Participant')

        if not certificate or not certificate.filename:
            flash('Please select a certificate file to upload.', 'error')
            return redirect(url_for('student.upload_certificate', od_id=od_id))

        cert_path = save_upload(certificate, folder='certificates')
        if not cert_path:
            flash('Invalid file type. Please upload JPG, PNG, or PDF.', 'error')
            return redirect(url_for('student.upload_certificate', od_id=od_id))

        od.certificate_path    = cert_path
        od.verification_status = 'Pending Verification'

        points_map = {'Participant': 10, '3rd Prize': 20, '2nd Prize': 30, 'Winner': 50}
        points = points_map.get(achievement, 10)

        # Prevent duplicate leaderboard entry
        existing = Leaderboard.query.filter_by(od_request_id=od.id).first()
        if not existing:
            leaderboard = Leaderboard(
                student_id=current_user.id,
                od_request_id=od.id,
                achievement=achievement,
                points=points
            )
            db.session.add(leaderboard)

        db.session.commit()

        flash('Certificate uploaded! Your HOD will verify it shortly.', 'success')
        return redirect(url_for('student.dashboard'))

    return render_template('student/upload_certificate.html', od=od)


@student.route('/files/<path:filename>')
def serve_file(filename):
    """Serve uploaded files (approval letters, brochures, certificates)."""
    # If the filename is actually a full Cloudinary URL, redirect to it
    if filename.startswith('http'):
        return redirect(filename)
        
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
