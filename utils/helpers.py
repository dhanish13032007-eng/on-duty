"""
helpers.py — File upload utilities.
Handles validation, Cloudinary upload, and local fallback storage.
"""
import os
import time
from werkzeug.utils import secure_filename
from flask import current_app

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

# Max file size: 5 MB
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename):
    """Return True if the filename has an allowed extension."""
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def validate_upload(file):
    """
    Validate an uploaded file object.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    if not file or not file.filename:
        return False, 'No file selected.'

    if not allowed_file(file.filename):
        return False, 'Invalid file type. Only PDF, JPG, and PNG are allowed.'

    # Check file size by seeking to end
    try:
        file.seek(0, 2)           # seek to end
        size = file.tell()
        file.seek(0)              # reset to start
        if size > MAX_FILE_SIZE_BYTES:
            return False, f'File too large ({size // (1024*1024):.1f} MB). Maximum allowed size is 5 MB.'
    except Exception:
        return False, 'Could not determine file size. Please try again.'

    return True, None


def save_upload(file, folder='others'):
    """
    Validate and save an uploaded file.

    Tries Cloudinary first (production), falls back to local storage (dev).
    Returns the saved path/URL string, or None on failure.
    """
    # Run validation
    valid, error = validate_upload(file)
    if not valid:
        current_app.logger.warning(f'Upload rejected: {error}')
        return None

    filename = secure_filename(file.filename)

    # ── Cloudinary (production) ────────────────────────────────────────────
    if current_app.config.get('CLOUDINARY_CLOUD_NAME'):
        try:
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                file,
                folder=f"smart_od/{folder}",
                public_id=f"{int(time.time())}_{filename.rsplit('.', 1)[0]}"
            )
            return result.get('secure_url')
        except Exception as e:
            current_app.logger.error(f'Cloudinary upload failed: {e}')
            # Fall through to local storage

    # ── Local storage (development fallback) ──────────────────────────────
    try:
        timestamp = str(int(time.time()))
        local_filename = f"{timestamp}_{filename}"
        subfolder = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
        os.makedirs(subfolder, exist_ok=True)
        filepath = os.path.join(subfolder, local_filename)
        file.seek(0)  # ensure we read from the beginning
        file.save(filepath)
        # Return a relative path for use in serve_file
        return f"{folder}/{local_filename}"
    except Exception as e:
        current_app.logger.error(f'Local file save failed: {e}')
        return None
