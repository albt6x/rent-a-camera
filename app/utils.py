# app/utils.py  (FULL REPLACE)
import os
import uuid
import secrets
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from flask import current_app

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
    """Buat folder kalau belum ada (silent)."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        # jika gagal membuat folder (permission etc) biarkan raise nanti saat save
        pass


def _resolve_upload_folder(key_or_path: str):
    """
    Jika argumen tampak seperti path (mengandung slash/backslash), kembalikan absolute path.
    Jika bukan, coba cari di current_app.config untuk key / alias.
    """
    if not key_or_path:
        return None

    # jika terlihat seperti path langsung
    if ("/" in key_or_path) or ("\\" in key_or_path) or (":" in key_or_path and os.name == "nt"):
        return os.path.abspath(key_or_path)

    cfg = current_app.config

    # direct key
    if key_or_path in cfg and cfg.get(key_or_path):
        return os.path.abspath(cfg.get(key_or_path))

    # try uppercase
    k_upper = key_or_path.upper()
    if k_upper in cfg and cfg.get(k_upper):
        return os.path.abspath(cfg.get(k_upper))

    # common aliases mapping (expand jika perlu)
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

    # try some generic keys if present
    for fallback in ('UPLOAD_FOLDER_PROFILE_PICS', 'UPLOAD_FOLDER_ITEMS', 'UPLOAD_FOLDER_PAYMENT_PROOFS', 'UPLOAD_FOLDER_BASE'):
        if fallback in cfg and cfg.get(fallback):
            return os.path.abspath(cfg.get(fallback))

    return None


def save_picture(file_storage, folder_key: str, output_size=(800, 800)):
    """
    Save uploaded picture.
    - file_storage: werkzeug FileStorage (e.g., form.picture.data)
    - folder_key: config key name (e.g. 'PROFILE_UPLOAD_FOLDER' or 'UPLOAD_FOLDER_PROFILE_PICS')
                  or a direct path
    - output_size: (width, height) maximum thumbnail size; if None, do not resize
    Returns: saved filename (with extension)
    Raises ValueError on validation/config errors.
    """

    # basic validation
    filename = getattr(file_storage, "filename", None)
    if not filename or not allowed_file(filename):
        raise ValueError("File bukan gambar yang diperbolehkan.")

    # check size best-effort (WSGI MAX_CONTENT_LENGTH preferred)
    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)  # default 5MB
    try:
        # try to measure stream size if possible
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > max_bytes:
            raise ValueError("File terlalu besar.")
    except Exception:
        pass

    # resolve upload folder (accept key or direct path)
    upload_folder = _resolve_upload_folder(folder_key)
    if not upload_folder:
        raise ValueError("Upload folder belum dikonfigurasi di app.config.")

    # ensure exist
    _ensure_folder(upload_folder)

    # safe filename generation: we will standardize saved images as .jpg
    basename = generate_basename()
    saved_filename = f"{basename}.jpg"
    save_path = os.path.join(upload_folder, saved_filename)

    # verify image using PIL
    try:
        img = Image.open(file_storage.stream)
        img.verify()  # will raise UnidentifiedImageError if not image
    except UnidentifiedImageError:
        raise ValueError("File upload bukan gambar yang valid.")
    except Exception:
        raise ValueError("Gagal memproses gambar upload.")

    # reopen and convert (verify() may close/affect stream)
    file_storage.stream.seek(0)
    try:
        img = Image.open(file_storage.stream).convert("RGB")
    except Exception:
        raise ValueError("Gagal membuka gambar untuk disimpan.")

    # resize if requested
    if output_size:
        try:
            img.thumbnail(output_size)
        except Exception:
            # jika resize gagal, tetap lanjut untuk simpan
            pass

    # save as JPEG (consistent)
    try:
        img.save(save_path, format="JPEG", quality=85, optimize=True)
    except Exception:
        # fallback: try plain save without optimizations
        try:
            img.save(save_path, format="JPEG")
        except Exception as e:
            raise ValueError("Gagal menyimpan file gambar.") from e

    return saved_filename
