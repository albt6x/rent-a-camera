import os
import uuid
import secrets
import logging
import time # Untuk mengatur jeda pengiriman email
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from flask import current_app, render_template, url_for
from flask_mail import Message
from app import mail # Pastikan mail diimport dari app/__init__.py

# Set up logger sederhana
logger = logging.getLogger(__name__)

# Allowed extensions untuk upload gambar
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

# ==========================================================
# HELPER: FUNGSI PENGIRIMAN EMAIL DENGAN SAFETY DELAY
# ==========================================================

def send_reset_email(user):
    """Kirim email reset password dengan jeda agar tidak terkena Rate Limit"""
    time.sleep(2) # Jeda keamanan 2 detik
    token = user.get_reset_token()
    reset_url = url_for('auth.reset_token', token=token, _external=True)
    msg = Message('Permintaan Reset Password - RentalKuy',
                  recipients=[user.email])
    
    msg.html = render_template('emails/reset_password_email.html', 
                               reset_url=reset_url, 
                               user=user)
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Gagal kirim email reset ke {user.email}: {str(e)}")

def send_order_status_email(user, order, template_name, subject):
    """
    Fungsi pusat untuk mengirim email status pesanan.
    Mengirimkan alias variabel (rental/order, buyer/borrower) agar template HTML lama tetap jalan.
    """
    time.sleep(2) # Jeda keamanan 2 detik
    
    msg = Message(f'{subject} - RentalKuy', recipients=[user.email])
    
    # RENDER TEMPLATE DENGAN ALIAS VARIABLE LENGKAP
    msg.html = render_template(
        f'emails/{template_name}',
        
        # Variabel User (Kirim 3 nama sekaligus biar aman)
        user=user,
        buyer=user,
        borrower=user,
        
        # Variabel Order/Rental (Kirim 2 nama sekaligus)
        order=order,
        rental=order
    )
    
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Gagal kirim email {template_name} ke {user.email}: {str(e)}")


# ==========================================================
# FUNGSI PENGOLAHAN GAMBAR (EXISTING)
# ==========================================================

def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def generate_basename() -> str:
    """Buat nama file random (tanpa ekstensi)."""
    return secrets.token_hex(12)

def _ensure_folder(path: str):
    """Buat folder kalau belum ada dengan logging jika gagal."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        current_app.logger.error(f"Gagal membuat folder di {path}: {str(e)}")

def _resolve_upload_folder(key_or_path: str):
    if not key_or_path:
        return None
    if ("/" in key_or_path) or ("\\" in key_or_path) or (":" in key_or_path and os.name == "nt"):
        return os.path.abspath(key_or_path)

    cfg = current_app.config
    if key_or_path in cfg and cfg.get(key_or_path):
        return os.path.abspath(cfg.get(key_or_path))

    k_upper = key_or_path.upper()
    aliases = {
        'PROFILE_UPLOAD_FOLDER': ['PROFILE_UPLOAD_FOLDER', 'UPLOAD_FOLDER_PROFILE_PICS', 'UPLOAD_FOLDER_PROFILE', 'UPLOAD_PROFILE_FOLDER'],
        'ITEMS_UPLOAD_FOLDER': ['ITEMS_UPLOAD_FOLDER', 'UPLOAD_FOLDER_ITEMS', 'UPLOAD_ITEMS_FOLDER'],
        'PAYMENT_UPLOAD_FOLDER': ['PAYMENT_UPLOAD_FOLDER', 'UPLOAD_FOLDER_PAYMENT_PROOFS', 'UPLOAD_PAYMENT_FOLDER'],
    }

    for alias_list in aliases.values():
        if key_or_path in alias_list or k_upper in alias_list:
            for a in alias_list:
                if a in cfg and cfg.get(a):
                    return os.path.abspath(cfg.get(a))

    return None

def save_picture(file_storage, folder_key: str, output_size=(800, 800)):
    filename = getattr(file_storage, "filename", None)
    if not filename or not allowed_file(filename):
        raise ValueError("File bukan gambar yang diperbolehkan.")

    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024) 
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_bytes:
        raise ValueError(f"File terlalu besar (Maksimal {max_bytes//(1024*1024)}MB).")

    upload_folder = _resolve_upload_folder(folder_key)
    if not upload_folder:
        raise ValueError("Upload folder belum dikonfigurasi.")

    _ensure_folder(upload_folder)
    basename = generate_basename()
    saved_filename = f"{basename}.jpg"
    save_path = os.path.join(upload_folder, saved_filename)

    try:
        img = Image.open(file_storage.stream)
        img = img.convert("RGB")
        if output_size:
            img.thumbnail(output_size)
        img.save(save_path, format="JPEG", quality=85, optimize=True)
    except Exception as e:
        current_app.logger.error(f"Gagal menyimpan gambar: {str(e)}")
        raise ValueError("Gagal menyimpan file gambar ke server.")

    return saved_filename