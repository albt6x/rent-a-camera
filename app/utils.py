import os
import uuid
import secrets
import logging # Tambahkan ini
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from flask import current_app

# Set up logger sederhana
logger = logging.getLogger(__name__)

# Allowed extensions untuk upload gambar
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

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
        # Ganti 'pass' dengan log agar kita tahu jika OS menolak membuat folder
        current_app.logger.error(f"Gagal membuat folder di {path}: {str(e)}")

def _resolve_upload_folder(key_or_path: str):
    """
    Jika argumen tampak seperti path (mengandung slash/backslash), kembalikan absolute path.
    Jika bukan, coba cari di current_app.config untuk key / alias.
    """
    if not key_or_path:
        return None

    if ("/" in key_or_path) or ("\\" in key_or_path) or (":" in key_or_path and os.name == "nt"):
        return os.path.abspath(key_or_path)

    cfg = current_app.config

    if key_or_path in cfg and cfg.get(key_or_path):
        return os.path.abspath(cfg.get(key_or_path))

    k_upper = key_or_path.upper()
    if k_upper in cfg and cfg.get(k_upper):
        return os.path.abspath(cfg.get(k_upper))

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

    for fallback in ('UPLOAD_FOLDER_PROFILE_PICS', 'UPLOAD_FOLDER_ITEMS', 'UPLOAD_FOLDER_PAYMENT_PROOFS', 'UPLOAD_FOLDER_BASE'):
        if fallback in cfg and cfg.get(fallback):
            return os.path.abspath(cfg.get(fallback))

    return None

def save_picture(file_storage, folder_key: str, output_size=(800, 800)):
    """
    Save uploaded picture dengan error handling yang informatif.
    """
    filename = getattr(file_storage, "filename", None)
    if not filename or not allowed_file(filename):
        raise ValueError("File bukan gambar yang diperbolehkan.")

    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024) 
    try:
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > max_bytes:
            raise ValueError(f"File terlalu besar (Maksimal {max_bytes//(1024*1024)}MB).")
    except Exception as e:
        # Jika gagal cek ukuran, log saja tapi biarkan lanjut
        current_app.logger.warning(f"Gagal menghitung ukuran file: {str(e)}")

    upload_folder = _resolve_upload_folder(folder_key)
    if not upload_folder:
        raise ValueError("Upload folder belum dikonfigurasi di app.config.")

    _ensure_folder(upload_folder)

    basename = generate_basename()
    saved_filename = f"{basename}.jpg"
    save_path = os.path.join(upload_folder, saved_filename)

    try:
        img = Image.open(file_storage.stream)
        img.verify()
    except UnidentifiedImageError:
        raise ValueError("File upload bukan gambar yang valid.")
    except Exception as e:
        current_app.logger.error(f"Gagal verifikasi gambar: {str(e)}")
        raise ValueError("Gagal memproses gambar upload.")

    file_storage.stream.seek(0)
    try:
        img = Image.open(file_storage.stream).convert("RGB")
    except Exception as e:
        current_app.logger.error(f"Gagal membuka gambar untuk konversi: {str(e)}")
        raise ValueError("Gagal membuka gambar untuk disimpan.")

    if output_size:
        try:
            img.thumbnail(output_size)
        except Exception as e:
            # Jika resize gagal, beri peringatan di log tapi tetap simpan
            current_app.logger.warning(f"Gagal melakukan thumbnail resize: {str(e)}")

    try:
        img.save(save_path, format="JPEG", quality=85, optimize=True)
    except Exception as e:
        current_app.logger.warning(f"Gagal menyimpan dengan optimasi, mencoba simpan biasa: {str(e)}")
        try:
            img.save(save_path, format="JPEG")
        except Exception as err:
            current_app.logger.error(f"FATAL: Gagal menyimpan gambar di {save_path}: {str(err)}")
            raise ValueError("Gagal menyimpan file gambar ke server.") from err

    return saved_filename