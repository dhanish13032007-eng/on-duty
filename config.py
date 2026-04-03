import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'smart-od-super-secret-key-2026')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///smart_od.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # ── Flask-Mail (configure via env vars or .env for production) ──
    MAIL_SERVER   = os.getenv('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT     = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.getenv('MAIL_USE_TLS',  'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')   # set in .env
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')   # set in .env
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME', 'noreply@smartod.app')

    # HOD & Admin email addresses (comma-separated if multiple)
    HOD_EMAIL   = os.getenv('HOD_EMAIL',   'dhanish13032007@gmail.com')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@college.edu')

    # ── Cloudinary (configure via .env or Render dashboard) ──
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY    = os.getenv('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
