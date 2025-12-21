# app/twofa/routes.py  (FINAL DEBUG VERSION)

from flask import (
    Blueprint,
    current_app,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    session,
)
from flask_login import login_required, current_user, logout_user
from app import db
import time, datetime

try:
    import pyotp
except Exception:
    pyotp = None

twofa_bp = Blueprint("twofa", __name__, url_prefix="/admin/2fa")


# ==========================================================
# HELPERS
# ==========================================================
def _is_admin(user):
    return bool(user and getattr(user, "role", None) == "admin")


# ==========================================================
# RATE LIMIT (SESSION)
# ==========================================================
def _fail_key(uid):
    return f"twofa_fail_count_{uid}"


def _get_fail_count(uid, window=300):
    data = session.get(_fail_key(uid))
    if not data:
        return 0
    if time.time() - data.get("ts", 0) > window:
        session.pop(_fail_key(uid), None)
        return 0
    return data.get("count", 0)


def _increase_fail_count(uid):
    key = _fail_key(uid)
    data = session.get(key, {"count": 0, "ts": time.time()})
    data["count"] += 1
    data["ts"] = time.time()
    session[key] = data
    return data["count"]


def _clear_fail_count(uid):
    session.pop(_fail_key(uid), None)


# ==========================================================
# 🔐 FIRST-TIME SETUP 2FA (ADMIN)
# ==========================================================
@twofa_bp.route("/setup", methods=["GET"])
def twofa_setup():
    user_id = session.get("pre_2fa_userid")
    if not user_id:
        flash("Sesi 2FA tidak valid. Silakan login ulang.", "warning")
        return redirect(url_for("auth.login"))

    from app.models import User
    user = User.query.get(user_id)

    if not user or not _is_admin(user):
        flash("Akses tidak valid.", "danger")
        return redirect(url_for("auth.login"))

    if user.otp_secret:
        return redirect(url_for("twofa.verify_page"))

    if not pyotp:
        flash("2FA tidak tersedia di server.", "danger")
        return redirect(url_for("auth.login"))

    if not session.get("pending_2fa_secret"):
        session["pending_2fa_secret"] = pyotp.random_base32()

    secret = session["pending_2fa_secret"]

    issuer = current_app.config.get("TWOFA_ISSUER", "Rentalkuy")

    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name=issuer,
    )

    qr_b64 = None
    if hasattr(current_app, "qr_image_base64"):
        try:
            qr_b64 = current_app.qr_image_base64(provisioning_uri)
        except Exception:
            qr_b64 = None

    return render_template(
        "twofa/setup.html",
        user=user,
        secret=secret,
        qr_base64=qr_b64,
    )


# ==========================================================
# CONFIRM SETUP QR (FIRST TIME)
# ==========================================================
@twofa_bp.route("/confirm", methods=["POST"])
def twofa_confirm():
    user_id = session.get("pre_2fa_userid")
    if not user_id:
        flash("Sesi 2FA tidak valid.", "danger")
        return redirect(url_for("auth.login"))

    from app.models import User
    user = User.query.get(user_id)

    if not user or not _is_admin(user):
        abort(403)

    secret = session.get("pending_2fa_secret")
    code = (request.form.get("code") or "").strip()

    if not secret or not code:
        flash("Kode 2FA tidak boleh kosong.", "danger")
        return redirect(url_for("twofa.twofa_setup"))

    if len(code) != 6 or not code.isdigit():
        flash("Kode 2FA harus 6 digit angka.", "danger")
        return redirect(url_for("twofa.twofa_setup"))

    totp = pyotp.TOTP(secret)

    if not totp.verify(code, valid_window=1):
        flash("Kode 2FA salah atau kedaluwarsa.", "danger")
        return redirect(url_for("twofa.twofa_setup"))

    user.otp_secret = secret
    db.session.commit()

    session.pop("pending_2fa_secret", None)

    flash("2FA berhasil diaktifkan. Silakan verifikasi.", "success")
    return redirect(url_for("twofa.verify_page"))


# ==========================================================
# PAGE INPUT OTP (LOGIN FLOW)
# ==========================================================
@twofa_bp.route("/verify", methods=["GET"])
def verify_page():
    user_id = session.get("pre_2fa_userid")
    if not user_id:
        flash("Silakan login terlebih dahulu.", "warning")
        return redirect(url_for("auth.login"))

    from app.models import User
    user = User.query.get(user_id)

    if not user or not user.otp_secret:
        flash("2FA belum aktif.", "danger")
        return redirect(url_for("twofa.twofa_setup"))

    return render_template(
        "twofa/verify.html",
        username=user.username,
    )


# ==========================================================
# VERIFY OTP (LOGIN FLOW) — DEBUG ENABLED
# ==========================================================
@twofa_bp.route("/verify", methods=["POST"])
def twofa_login_verify():
    user_id = session.get("pre_2fa_userid")
    if not user_id:
        flash("Sesi 2FA tidak valid.", "danger")
        return redirect(url_for("auth.login"))

    from app.models import User
    user = User.query.get(user_id)

    if not user or not user.otp_secret:
        flash("2FA tidak aktif.", "danger")
        return redirect(url_for("auth.login"))

    code = (request.form.get("code") or "").strip()

    # ===== DEBUG LOG =====
    print("\n======= 2FA DEBUG =======")
    print("SERVER TIME:", datetime.datetime.now())
    print("SECRET DB:", user.otp_secret)
    print("SECRET LENGTH:", len(user.otp_secret))
    print("INPUT CODE:", code)

    totp = pyotp.TOTP(user.otp_secret)
    server_otp = totp.now()
    print("SERVER OTP NOW:", server_otp)
    print("=========================\n")

    if not code.isdigit() or len(code) != 6:
        flash("Kode 2FA salah.", "danger")
        return redirect(url_for("twofa.verify_page"))

    if not totp.verify(code, valid_window=2):
        flash("Kode 2FA salah.", "danger")
        return redirect(url_for("twofa.verify_page"))

    session["pre_2fa_verified"] = True
    session["admin_2fa_verified"] = True

    return redirect(url_for("auth.twofa_verify"))


# ==========================================================
# FORCE RESET 2FA (ADMIN LOGIN)
# ==========================================================
@twofa_bp.route("/force-reset/<int:user_id>", methods=["POST"])
@login_required
def force_reset_2fa(user_id):
    if not _is_admin(current_user):
        abort(403)

    from app.models import User
    user = User.query.get_or_404(user_id)

    user.otp_secret = None
    db.session.commit()

    session.clear()
    logout_user()

    flash("2FA admin di-reset. Silakan login ulang.", "warning")
    return redirect(url_for("auth.login"))
