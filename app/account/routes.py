# app/account/routes.py  (FULL REPLACE)
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
    If filename looks like an absolute path, try to convert to relative static path;
    otherwise assume file is stored under static/uploads/profile_pics/.
    """
    if not filename:
        # fallback to config default (absolute path) -> try to return a static URL if possible
        default_path = current_app.config.get("UPLOAD_DEFAULT_PROFILE")
        if default_path:
            # if default_path is inside static folder, convert to static URL
            static_folder = os.path.abspath(os.path.join(current_app.root_path, "static"))
            try:
                default_abs = os.path.abspath(default_path)
                if default_abs.startswith(static_folder):
                    rel = os.path.relpath(default_abs, static_folder).replace("\\", "/")
                    return url_for("static", filename=rel)
            except Exception:
                pass
        # last resort: point to a generic static path
        return url_for("static", filename="uploads/profile_pics/default.jpg")

    # if filename already a full URL (http...), return as-is
    if str(filename).lower().startswith(("http://", "https://")):
        return filename

    # if filename looks like an absolute path on disk, try to convert to static URL
    if os.path.isabs(filename):
        static_folder = os.path.abspath(os.path.join(current_app.root_path, "static"))
        try:
            absf = os.path.abspath(filename)
            if absf.startswith(static_folder):
                rel = os.path.relpath(absf, static_folder).replace("\\", "/")
                return url_for("static", filename=rel)
        except Exception:
            pass

    # otherwise assume it's just a stored filename under uploads/profile_pics/
    return url_for("static", filename="uploads/profile_pics/" + filename)


@account_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = UpdateAccountForm()

    if form.validate_on_submit():
        # handle picture upload (if provided)
        if form.picture.data:
            try:
                # save_picture will read current_app.config to find the folder key
                saved_name = save_picture(form.picture.data, "PROFILE_UPLOAD_FOLDER")
            except ValueError as ve:
                # validation error from utils (bad image, too large, folder not configured, ...)
                flash(str(ve), "danger")
                # do not continue updating other fields if picture invalid — show form again
                return redirect(url_for("account.profile"))
            except Exception as e:
                current_app.logger.exception("Unexpected error saving uploaded profile picture")
                flash("Terjadi kesalahan ketika menyimpan gambar profil. Coba lagi.", "danger")
                return redirect(url_for("account.profile"))

            # remove old image file (if not default and exists)
            try:
                old = getattr(current_user, "image_file", None)
                # Resolve saved folder to disk path if possible
                upload_folder = None
                # prefer explicit config key if present
                for key in ("PROFILE_UPLOAD_FOLDER", "UPLOAD_FOLDER_PROFILE_PICS", "UPLOAD_PROFILE_FOLDER", "UPLOAD_FOLDER"):
                    val = current_app.config.get(key)
                    if val:
                        upload_folder = val
                        break
                # fallback to constructed default inside app static
                if not upload_folder:
                    upload_folder = os.path.join(current_app.root_path, "static", "uploads", "profile_pics")

                # Only attempt deletion if old looks like a simple filename (not None, not default) 
                default_name = None
                default_path = current_app.config.get("UPLOAD_DEFAULT_PROFILE")
                if default_path and os.path.isabs(default_path):
                    default_name = os.path.basename(default_path)

                if old and old != default_name and not old.lower().startswith(("http://", "https://")):
                    old_path = os.path.join(upload_folder, old)
                    if os.path.exists(old_path) and os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            # don't break flow for deletion failure
                            current_app.logger.debug("Failed to remove old profile image: %s", old_path)
            except Exception:
                current_app.logger.debug("Error while attempting to remove old profile picture", exc_info=True)

            # update current_user.image_file with new saved filename
            current_user.image_file = saved_name

        # update username & email
        current_user.username = form.username.data
        current_user.email = form.email.data

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to commit user profile changes")
            flash("Gagal menyimpan perubahan pada akun. Coba lagi.", "danger")
            return redirect(url_for("account.profile"))

        flash("Akun Anda telah berhasil diperbarui!", "success")
        return redirect(url_for("account.profile"))

    # GET -> prefill form fields
    if request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email

    # build image url for display (handle missing/default)
    image_file_url = _get_profile_url(getattr(current_user, "image_file", None))

    return render_template(
        "account/account.html",
        title="Akun Saya",
        form=form,
        image_file=image_file_url,
    )
