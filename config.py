import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'smart-od-super-secret-key-2026'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///smart_od.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # ── Flask-Mail (configure via env vars or .env for production) ──
    MAIL_SERVER   = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS',  'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')   # set in .env
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')   # set in .env
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME') or 'noreply@smartod.app'

    # HOD & Admin email addresses (comma-separated if multiple)
    HOD_EMAIL   = os.environ.get('HOD_EMAIL',   'hod@college.edu')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@college.edu')

    # ── Cloudinary (configure via .env or Render dashboard) ──
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
