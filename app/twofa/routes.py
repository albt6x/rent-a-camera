# app/twofa/routes.py  (FULL REPLACE)
from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    session,
)
from flask_login import login_required, current_user
from app import db
import functools
import time

# optional pyotp import
try:
    import pyotp
    _HAS_PYOTP = True
except Exception:
    pyotp = None
    _HAS_PYOTP = False

twofa_bp = Blueprint("twofa", __name__, url_prefix="/admin/2fa")


def _is_allowed(user_id):
    """
    Return True if current_user can manage 2FA for user_id.
    Allowed if authenticated AND (admin OR owner).
    """
    if not current_user.is_authenticated:
        return False
    if getattr(current_user, "is_admin", False):
        return True
    if getattr(current_user, "role", None) == "admin":
        return True
    try:
        return int(current_user.id) == int(user_id)
    except Exception:
        return False


# Simple in-session rate limiter per user_id for verification attempts
def _fail_count_key(uid):
    return f"twofa_fail_count_{uid}"


def _increase_fail_count(uid, window_seconds=300):
    key = _fail_count_key(uid)
    data = session.get(key, {"count": 0, "ts": time.time()})
    # reset if outside window
    if time.time() - data.get("ts", 0) > window_seconds:
        data = {"count": 0, "ts": time.time()}
    data["count"] = data.get("count", 0) + 1
    data["ts"] = time.time()
    session[key] = data
    return data["count"]


def _get_fail_count(uid, window_seconds=300):
    key = _fail_count_key(uid)
    data = session.get(key)
    if not data:
        return 0
    if time.time() - data.get("ts", 0) > window_seconds:
        # expired
        session.pop(key, None)
        return 0
    return data.get("count", 0)


def _clear_fail_count(uid):
    session.pop(_fail_count_key(uid), None)


@twofa_bp.route("/setup/<int:user_id>", methods=["GET"])
@login_required
def twofa_setup(user_id):
    # permission check
    if not _is_allowed(user_id):
        abort(403)

    # dynamic import model
    try:
        from app.models import User
    except Exception:
        return jsonify({"error": "User model not available"}), 500

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    # ensure 2FA capability
    if not _HAS_PYOTP and not (hasattr(current_app, "generate_totp_secret") and hasattr(current_app, "get_totp_uri")):
        # render page but indicate unsupported
        if request.accept_mimetypes.accept_html and not request.is_xhr:
            flash("2FA helpers (pyotp/qrcode) tidak tersedia di server.", "warning")
            return render_template("twofa/setup.html", user=user, supported=False)
        return jsonify({"error": "2FA helpers not available on app"}), 500

    # Generate temporary secret and provisioning URI
    secret = current_app.generate_totp_secret() if hasattr(current_app, "generate_totp_secret") else pyotp.random_base32()
    provisioning_uri = current_app.get_totp_uri(secret, user.email) if hasattr(current_app, "get_totp_uri") else pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=current_app.config.get("TWOFA_ISSUER", "Rentalkuy"))
    try:
        qr_b64 = current_app.qr_image_base64(provisioning_uri) if hasattr(current_app, "qr_image_base64") else None
    except Exception:
        qr_b64 = None

    # HTML dev UI (optional)
    if request.accept_mimetypes.accept_html and not request.is_xhr:
        # show QR and secret (NOT saved)
        return render_template("twofa/setup.html", user=user, secret=secret, provisioning_uri=provisioning_uri, qr_base64=qr_b64, supported=True)

    # JSON
    return jsonify({"secret": secret, "provisioning_uri": provisioning_uri, "qr_base64": qr_b64})


@twofa_bp.route("/confirm/<int:user_id>", methods=["POST"])
@login_required
def twofa_confirm(user_id):
    if not _is_allowed(user_id):
        abort(403)

    try:
        from app.models import User
    except Exception:
        return jsonify({"ok": False, "error": "User model not available"}), 500

    user = User.query.get(user_id)
    if not user:
        return jsonify({"ok": False, "error": "user not found"}), 404

    data = request.get_json() if request.is_json else request.form
    secret = data.get("secret")
    code = data.get("code")
    if not secret or not code:
        return jsonify({"ok": False, "error": "missing secret or code"}), 400

    # verify
    try:
        totp = (pyotp.TOTP(secret) if _HAS_PYOTP else None)
        is_valid = totp.verify(code, valid_window=1) if totp else False
    except Exception as exc:
        current_app.logger.exception("2FA confirm verify error: %s", exc)
        return jsonify({"ok": False, "error": "invalid totp operation"}), 400

    if not is_valid:
        return jsonify({"ok": False, "error": "code verification failed"}), 400

    # persist
    try:
        user.otp_secret = secret
        db.session.add(user)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to save otp_secret: %s", exc)
        return jsonify({"ok": False, "error": "failed to save secret"}), 500

    # If HTML, flash + redirect
    if request.accept_mimetypes.accept_html and not request.is_xhr:
        flash("2FA berhasil diaktifkan untuk user.", "success")
        try:
            return redirect(url_for("admin.edit_user", user_id=user_id))
        except Exception:
            return redirect(url_for("main.home"))

    return jsonify({"ok": True})


@twofa_bp.route("/verify/<int:user_id>", methods=["POST"])
@login_required
def twofa_verify(user_id):
    """
    Verify posted code against user's stored secret.
    Optional behaviour:
      - if form/json contains 'for_login'=1 and session contains 'pre_2fa_userid' matching user_id,
        then on success we set session['pre_2fa_verified'] = True to be consumed by auth flow.
    """
    if not _is_allowed(user_id):
        abort(403)

    try:
        from app.models import User
    except Exception:
        return jsonify({"ok": False, "error": "User model not available"}), 500

    user = User.query.get(user_id)
    if not user:
        return jsonify({"ok": False, "error": "user not found"}), 404

    secret = getattr(user, "otp_secret", None)
    if not secret:
        return jsonify({"ok": False, "error": "2FA not enabled for this user"}), 400

    # simple rate-limit
    if _get_fail_count(user_id) >= 6:
        return jsonify({"ok": False, "error": "too many attempts, try later"}), 429

    data = request.get_json() if request.is_json else request.form
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "missing code"}), 400

    try:
        totp = pyotp.TOTP(secret) if _HAS_PYOTP else None
        ok = bool(totp.verify(code, valid_window=1)) if totp else False
    except Exception as exc:
        current_app.logger.exception("2FA verify error: %s", exc)
        ok = False

    if not ok:
        _increase_fail_count(user_id)
        return jsonify({"ok": False, "error": "invalid code"}), 400

    # success -> clear fail count
    _clear_fail_count(user_id)

    # If this verify is part of login flow, set a session flag for auth route to consume.
    for_login = data.get("for_login") in ("1", "true", "True", True)
    pre_id = session.get("pre_2fa_userid")
    if for_login and pre_id and int(pre_id) == int(user_id):
        session["pre_2fa_verified"] = True

    # HTML flow: redirect if requested
    if request.accept_mimetypes.accept_html and not request.is_xhr:
        flash("2FA verification success.", "success")
        # if login flow, redirect to auth.twofa_verify or main
        if session.get("pre_2fa_verified"):
            # let auth route do final login; redirect there
            try:
                return redirect(url_for("auth.twofa_verify"))
            except Exception:
                return redirect(url_for("main.home"))
        # otherwise redirect to admin edit user page or main
        try:
            return redirect(url_for("admin.edit_user", user_id=user_id))
        except Exception:
            return redirect(url_for("main.home"))

    return jsonify({"ok": True})


@twofa_bp.route("/disable/<int:user_id>", methods=["POST"])
@login_required
def twofa_disable(user_id):
    if not _is_allowed(user_id):
        abort(403)

    # TODO: For safety, consider requiring password or current 2FA code before disabling.
    try:
        from app.models import User
    except Exception:
        return jsonify({"ok": False, "error": "User model not available"}), 500

    user = User.query.get(user_id)
    if not user:
        return jsonify({"ok": False, "error": "user not found"}), 404

    try:
        user.otp_secret = None
        db.session.add(user)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to disable 2FA: %s", exc)
        return jsonify({"ok": False, "error": "failed to update"}), 500

    if request.accept_mimetypes.accept_html and not request.is_xhr:
        flash("2FA berhasil dinonaktifkan.", "success")
        try:
            return redirect(url_for("admin.edit_user", user_id=user_id))
        except Exception:
            return redirect(url_for("main.home"))

    return jsonify({"ok": True})
