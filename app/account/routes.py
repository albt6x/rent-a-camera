# app/account/routes.py (FULL REPLACE - FIX: TEMPLATE PATH + OS PATH + AUTO-FIX WA)

import os
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    current_app,
)
from flask_login import login_required, current_user
from app import db
from app.forms import UpdateAccountForm
from app.utils import save_picture

account_bp = Blueprint('account', __name__)


def _get_profile_url(filename: str):
    """
    Return a URL suitable for HTML <img> given stored filename.
    Handles default images and absolute paths logic.
    """
    if not filename:
        default_path = current_app.config.get("UPLOAD_DEFAULT_PROFILE")
        if default_path:
            static_folder = os.path.abspath(os.path.join(current_app.root_path, "static"))
            try:
                default_abs = os.path.abspath(default_path)
                if default_abs.startswith(static_folder):
                    rel = os.path.relpath(default_abs, static_folder).replace("\\", "/")
                    return url_for("static", filename=rel)
            except Exception as e:
                current_app.logger.error(f"Gagal memproses default profile path: {e}")
        
        # Fallback hardcoded jika config gagal
        return url_for("static", filename="uploads/profile_pics/default.jpg")

    # Jika filename ternyata URL eksternal (https://...)
    if str(filename).lower().startswith(("http://", "https://")):
        return filename

    # --- PERBAIKAN: Menggunakan os.path.isabs (Bukan os.isabs) ---
    if os.path.isabs(filename):
        static_folder = os.path.abspath(os.path.join(current_app.root_path, "static"))
        try:
            absf = os.path.abspath(filename)
            if absf.startswith(static_folder):
                rel = os.path.relpath(absf, static_folder).replace("\\", "/")
                return url_for("static", filename=rel)
        except Exception as e:
            current_app.logger.error(f"Gagal konversi absolute path gambar: {e}")

    # Default relative path di uploads/profile_pics/
    return url_for("static", filename="uploads/profile_pics/" + filename)


@account_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = UpdateAccountForm()

    if form.validate_on_submit():
        # --- 1. PROSES GAMBAR ---
        if form.picture.data:
            try:
                # Simpan gambar baru
                saved_name = save_picture(form.picture.data, "PROFILE_UPLOAD_FOLDER")
            except ValueError as ve:
                flash(str(ve), "danger")
                return redirect(url_for("account.profile"))
            except Exception as e:
                current_app.logger.exception("Unexpected error saving uploaded profile picture")
                flash("Terjadi kesalahan ketika menyimpan gambar profil. Coba lagi.", "danger")
                return redirect(url_for("account.profile"))

            # Logika penghapusan file lama (Pembersihan sampah)
            try:
                old = getattr(current_user, "image_file", None)
                upload_folder = None
                # Cek config key mana yang dipakai
                for key in ("PROFILE_UPLOAD_FOLDER", "UPLOAD_FOLDER_PROFILE_PICS", "UPLOAD_PROFILE_FOLDER", "UPLOAD_FOLDER"):
                    val = current_app.config.get(key)
                    if val:
                        upload_folder = val
                        break
                
                # Fallback jika config tidak ketemu
                if not upload_folder:
                    upload_folder = os.path.join(current_app.root_path, "static", "uploads", "profile_pics")

                default_name = None
                default_path = current_app.config.get("UPLOAD_DEFAULT_PROFILE")
                if default_path and os.path.isabs(default_path):
                    default_name = os.path.basename(default_path)

                # Hapus hanya jika bukan default dan bukan URL eksternal
                if old and old != default_name and not old.lower().startswith(("http://", "https://")):
                    old_path = os.path.join(upload_folder, old)
                    if os.path.exists(old_path) and os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            current_app.logger.warning(f"Gagal menghapus file lama di {old_path}: {e}")
            except Exception as e:
                current_app.logger.debug(f"Error saat mencari file lama untuk dihapus: {e}")

            # Update database dengan nama file baru
            current_user.image_file = saved_name

        # --- 2. UPDATE DATA TEKS ---
        current_user.username = form.username.data
        current_user.email = form.email.data
        
        # --- 3. LOGIKA AUTO-FIX WHATSAPP (AGAR TIDAK INVALID) ---
        raw_phone = form.phone.data
        if raw_phone:
            # Bersihkan spasi, strip, dan karakter non-digit
            raw_phone = raw_phone.strip().replace(" ", "").replace("-", "").replace("+", "")
            
            # Jika user ketik 08... ubah ke 628...
            if raw_phone.startswith('0'):
                raw_phone = '62' + raw_phone[1:]
            # Jika user ketik +62... tanda + sudah dihapus di atas, jadi 628...
                
        current_user.phone = raw_phone
        # --------------------------------------------------------

        # --- 4. COMMIT KE DATABASE ---
        try:
            db.session.commit()
            flash("Akun Anda telah berhasil diperbarui!", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Gagal database commit di profile: {e}")
            flash("Gagal menyimpan perubahan pada akun. Coba lagi.", "danger")

        return redirect(url_for("account.profile"))

    # --- 5. PRE-FILL FORM (Saat halaman dibuka) ---
    if request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.phone.data = current_user.phone

    # Siapkan URL gambar untuk template
    image_file_url = _get_profile_url(getattr(current_user, "image_file", None))

    # --- BAGIAN PENTING: Gunakan path account/account.html ---
    return render_template(
        "account/account.html", 
        title="Akun Saya",
        form=form,
        image_file=image_file_url,
    )