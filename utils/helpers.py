import os
import time
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file, folder='others'):
    if not file or not allowed_file(file.filename):
        return None
        
    filename = secure_filename(file.filename)
    
    # Check if Cloudinary is configured for production
    if current_app.config.get('CLOUDINARY_CLOUD_NAME'):
        try:
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                file, 
                folder=f"smart_od/{folder}",
                public_id=f"{int(time.time())}_{filename.split('.')[0]}"
            )
            return result.get('secure_url')
        except Exception as e:
            current_app.logger.error(f"Cloudinary upload failed: {e}")
            # Fallback to local if upload fails and we are not strictly forcing cloud
            
    # Local fallback logic (useful for development)
    timestamp = str(int(time.time()))
    filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return filename
