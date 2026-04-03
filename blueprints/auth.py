from flask import Blueprint, render_template, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Leaderboard, ODRequest
from sqlalchemy import func

auth = Blueprint('auth', __name__)

@auth.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)
    return render_template('index.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.name}! 👋', 'success')
            return _redirect_by_role(user.role)
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('auth/login.html')


@auth.route('/leaderboard')
def leaderboard():
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
    return render_template('leaderboard.html', top_students=top_students)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


def _redirect_by_role(role):
    if role == 'HOD':
        return redirect(url_for('hod.dashboard'))
    elif role == 'Admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('auth.index'))
