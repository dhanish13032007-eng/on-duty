from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False) # Register Number or Staff ID
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'Student', 'HOD', 'Admin'
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(50), nullable=True)
    section = db.Column(db.String(10), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    batch_number = db.Column(db.String(20), nullable=True)
    
    # Penalty tracking
    is_under_penalty = db.Column(db.Boolean, default=False)
    penalty_end_date = db.Column(db.DateTime, nullable=True)
    
    od_requests = db.relationship('ODRequest', backref='student', lazy=True)
    leaderboard_entries = db.relationship('Leaderboard', backref='student', lazy=True)

class ODRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    event_name = db.Column(db.String(150), nullable=False)
    college_name = db.Column(db.String(150), nullable=False)
    od_date = db.Column(db.Date, nullable=False)
    od_day = db.Column(db.String(20), nullable=False)
    number_of_days = db.Column(db.Integer, nullable=False)
    
    approval_letter_path = db.Column(db.String(255), nullable=True)
    brochure_path = db.Column(db.String(255), nullable=True)
    certificate_path = db.Column(db.String(255), nullable=True)
    
    hod_status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    admin_status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    final_status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    
    verification_status = db.Column(db.String(30), default='Pending Upload') # Pending Upload, Pending Verification, Verified
    
    is_leave = db.Column(db.Boolean, default=False) # Converted to leave due to penalty
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    leaderboard_entry = db.relationship('Leaderboard', backref='od_request', uselist=False, lazy=True)

class Leaderboard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    od_request_id = db.Column(db.Integer, db.ForeignKey('od_request.id'), nullable=False)
    
    achievement = db.Column(db.String(50), nullable=False) # Participant, Winner, 2nd Prize, 3rd Prize
    points = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
