"""
auth.py — Authentication & registration blueprint.
Handles: login, logout, student registration, leaderboard, root redirect.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Leaderboard, ODRequest
from sqlalchemy import func

auth = Blueprint('auth', __name__)


# ── Root ───────────────────────────────────────────────────────────────────
@auth.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)
    return render_template('index.html')


# ── Login ──────────────────────────────────────────────────────────────────
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        try:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user, remember=True)
                flash(f'Welcome back, {user.name}! 👋', 'success')
                return _redirect_by_role(user.role)
            else:
                flash('Invalid username or password. Please try again.', 'error')
        except Exception as e:
            flash('An error occurred during login. Please try again.', 'error')

    return render_template('auth/login.html')


# ── Student Registration ───────────────────────────────────────────────────
@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Allow new students to self-register."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        username   = request.form.get('username', '').strip()   # Register number
        name       = request.form.get('name', '').strip()
        email      = request.form.get('email', '').strip().lower()
        department = request.form.get('department', '').strip()
        section    = request.form.get('section', '').strip()
        year_str   = request.form.get('year', '').strip()
        batch      = request.form.get('batch_number', '').strip()
        password   = request.form.get('password', '')
        confirm    = request.form.get('confirm_password', '')

        # ── Validation ──────────────────────────────────────────────────
        if not all([username, name, email, department, password]):
            flash('Please fill in all required fields.', 'error')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/register.html')

        try:
            # Check for existing username or email
            if User.query.filter_by(username=username).first():
                flash('Register number already in use. Try logging in.', 'error')
                return render_template('auth/register.html')

            if User.query.filter_by(email=email).first():
                flash('Email address already registered.', 'error')
                return render_template('auth/register.html')

            year = int(year_str) if year_str.isdigit() and 1 <= int(year_str) <= 4 else None

            new_student = User(
                username=username,
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role='Student',
                department=department,
                section=section or None,
                year=year,
                batch_number=batch or None,
            )
            db.session.add(new_student)
            db.session.commit()

            login_user(new_student, remember=True)
            flash(f'Welcome, {name}! Your account has been created successfully.', 'success')
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


# ── Public Leaderboard ─────────────────────────────────────────────────────
@auth.route('/leaderboard')
def leaderboard():
    try:
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
            .limit(20)
            .all()
        )
    except Exception:
        top_students = []

    return render_template('leaderboard.html', top_students=top_students)


# ── Logout ─────────────────────────────────────────────────────────────────
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


# ── Helper ─────────────────────────────────────────────────────────────────
def _redirect_by_role(role):
    """Redirect authenticated user to their role-specific dashboard."""
    if role == 'HOD':
        return redirect(url_for('hod.dashboard'))
    elif role == 'Admin':
        return redirect(url_for('admin.dashboard'))
    # Student — go to student dashboard
    return redirect(url_for('student.dashboard'))
