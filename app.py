import os
from dotenv import load_dotenv
load_dotenv()  # Load variables from .env file

from flask import Flask
from config import Config
from models import db, User
from flask_login import LoginManager
from utils.emails import mail

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    import cloudinary
    if app.config.get('CLOUDINARY_CLOUD_NAME'):
        cloudinary.config(
            cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
            api_key=app.config['CLOUDINARY_API_KEY'],
            api_secret=app.config['CLOUDINARY_API_SECRET']
        )

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from blueprints.auth    import auth    as auth_bp
    from blueprints.student import student as student_bp
    from blueprints.hod     import hod     as hod_bp
    from blueprints.admin   import admin   as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(hod_bp,     url_prefix='/hod')
    app.register_blueprint(admin_bp,   url_prefix='/admin')

    # Ensure uploads dir exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        db.create_all()
        
        # Hardcode default users for HOD and Admin to avoid manual registration
        from werkzeug.security import generate_password_hash
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                name='Administrator',
                email='admin@example.com',
                password_hash=generate_password_hash('admin'),
                role='Admin'
            )
            db.session.add(admin_user)
            
        hod_user = User.query.filter_by(username='hod').first()
        if not hod_user:
            hod_user = User(
                username='hod',
                name='Head of Department',
                email='hod@example.com',
                password_hash=generate_password_hash('hod'),
                role='HOD',
                department='CSE' # Default department
            )
            db.session.add(hod_user)
            
        db.session.commit()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
