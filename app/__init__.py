# app/__init__.py
import os
import threading
from base64 import b64encode
from io import BytesIO

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt

# optional security lib
try:
    from flask_talisman import Talisman
    _HAS_TALISMAN = True
except Exception:
    Talisman = None
    _HAS_TALISMAN = False

# mail & 2fa libs
try:
    from flask_mail import Mail, Message
    _HAS_FLASK_MAIL = True
except Exception:
    Mail = None
    Message = None
    _HAS_FLASK_MAIL = False

try:
    import pyotp
    import qrcode
    _HAS_PYOTP = True
except Exception:
    pyotp = None
    qrcode = None
    _HAS_PYOTP = False

# ==========================================================
# 1. Inisialisasi Extension (object only)
# ==========================================================
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail() if _HAS_FLASK_MAIL else None

# Login manager defaults (keamanan UX)
login_manager.login_view = "auth.login"
login_manager.login_message = "Silakan login untuk mengakses halaman ini."
login_manager.login_message_category = "info"


# ==========================================================
# 2. Factory Function (FULL REPLACE)
# ==========================================================
def create_app(config_string="config.Config"):
    """
    Create and configure the Flask app.
    - Loads config from config_string (default config.Config)
    - Initializes extensions (db, migrate, login_manager, bcrypt, mail)
    - Optionally sets up Talisman when configured and installed
    - Registers existing blueprints (main, auth, catalog, cart, booking, admin, account, staff)
    - Attaches helpers: send_email, generate_totp_secret, get_totp_uri, qr_image_base64
    """

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_string)

    # Ensure upload folders exist (best-effort)
    upload_base = app.config.get("UPLOAD_FOLDER_BASE")
    if upload_base:
        try:
            os.makedirs(upload_base, exist_ok=True)
            for key in ("UPLOAD_FOLDER_ITEMS", "UPLOAD_FOLDER_PAYMENT_PROOFS", "UPLOAD_FOLDER_PROFILE_PICS"):
                p = app.config.get(key)
                if p:
                    os.makedirs(p, exist_ok=True)
        except Exception:
            pass

    # ==========================================================
    # 3. Hubungkan Extension
    # ==========================================================
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    if _HAS_FLASK_MAIL and mail:
        mail.init_app(app)

    # ==========================================================
    # 4. OPTIONAL: Talisman (security headers)
    # ==========================================================
    try:
        if _HAS_TALISMAN and app.config.get("ENABLE_TALISMAN", False) and not app.debug and not app.testing:
            talisman_csp = app.config.get("TALISMAN_CONTENT_SECURITY_POLICY", None)
            Talisman(
                app,
                content_security_policy=talisman_csp,
                force_https=app.config.get("TALISMAN_FORCE_HTTPS", True),
            )
    except Exception:
        pass

    # ==========================================================
    # 5. Import models early so user_loader works
    # ==========================================================
    with app.app_context():
        try:
            # app/models.py must exist in your project
            from app import models  # noqa: F401
        except Exception:
            # If models.py missing or import fails, app still runs but user_loader will be disabled
            pass

    # ==========================================================
    # 6. Register Blueprint (keep same names as project)
    # ==========================================================
    # we import and register blueprints by the names used in your original file
    try:
        from app.main.routes import main_bp
        app.register_blueprint(main_bp)
    except Exception:
        pass

    try:
        from app.auth.routes import auth_bp
        app.register_blueprint(auth_bp, url_prefix="/auth")
    except Exception:
        pass

    try:
        from app.catalog.routes import catalog_bp
        app.register_blueprint(catalog_bp, url_prefix="/catalog")
    except Exception:
        pass

    try:
        from app.cart.routes import cart_bp
        app.register_blueprint(cart_bp, url_prefix="/cart")
    except Exception:
        pass

    try:
        from app.booking.routes import booking_bp
        app.register_blueprint(booking_bp, url_prefix="/booking")
    except Exception:
        pass

    try:
        from app.admin.routes import admin_bp
        app.register_blueprint(admin_bp, url_prefix="/admin")
    except Exception:
        pass

    try:
        from app.account.routes import account_bp
        app.register_blueprint(account_bp, url_prefix="/account")
    except Exception:
        pass

    try:
        from app.staff.routes import staff_bp
        app.register_blueprint(staff_bp, url_prefix="/staff")
    except Exception:
        pass

    # register optional twofa blueprint if exists (we will create this file separately)
    try:
        from app.twofa.routes import twofa_bp
        app.register_blueprint(twofa_bp)
    except Exception:
        # blueprint doesn't exist yet; that's fine
        pass

    # ==========================================================
    # 7. Context Processor (example: inject cart count)
    # ==========================================================
    try:
        from app.context_processors import inject_cart_count
        app.context_processor(inject_cart_count)
    except Exception:
        pass

    # ==========================================================
    # 8. CUSTOM ERROR HANDLER (UI)
    # ==========================================================
    @app.errorhandler(403)
    def error_403(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def error_404(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def error_500(e):
        return render_template("errors/500.html"), 500

    # ==========================================================
    # 9. Login manager user_loader (tries to load app.models.User)
    # ==========================================================
    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models import User
            return User.query.get(int(user_id))
        except Exception:
            return None

    # ==========================================================
    # 10. EMAIL helper (non-blocking) - attach to app
    # ==========================================================
    def _send_async(msg):
        # run mail.send in app context
        with app.app_context():
            if _HAS_FLASK_MAIL and mail:
                mail.send(msg)
            else:
                # If Flask-Mail not installed, fallback to logging (no crash)
                app.logger.warning("Mail not configured or Flask-Mail not installed. Subject: %s", getattr(msg, "subject", None))

    def send_email(subject, recipients, body, html=None, sender=None):
        """
        Send email non-blocking.
        Usage:
            send_email("Hi", ["to@example.com"], "plain text", html="<b>HTML</b>")
        """
        if not _HAS_FLASK_MAIL or not mail:
            app.logger.warning("Attempt to send email but Flask-Mail not available.")
            return False

        msg = Message(subject=subject, recipients=recipients)
        if sender:
            msg.sender = sender
        msg.body = body
        if html:
            msg.html = html
        t = threading.Thread(target=_send_async, args=(msg,))
        t.start()
        return True

    # attach to app for easy use: app.send_email(...)
    app.send_email = send_email

    # ==========================================================
    # 11. 2FA helpers (pyotp + qrcode) - attach to app
    # ==========================================================
    def generate_totp_secret():
        if not _HAS_PYOTP:
            raise RuntimeError("pyotp not installed")
        return pyotp.random_base32()

    def get_totp_uri(secret, user_email, issuer=None):
        if not _HAS_PYOTP:
            raise RuntimeError("pyotp not installed")
        issuer_name = issuer or app.config.get("TWOFA_ISSUER", "Rentalkuy")
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=user_email, issuer_name=issuer_name)

    def qr_image_base64(provisioning_uri, box_size=6, border=2):
        if not qrcode:
            raise RuntimeError("qrcode not installed")
        qr = qrcode.QRCode(box_size=box_size, border=border)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    # attach 2fa helpers to app object
    app.generate_totp_secret = generate_totp_secret
    app.get_totp_uri = get_totp_uri
    app.qr_image_base64 = qr_image_base64

    # ==========================================================
    # 12. Return configured app
    # ==========================================================
    return app
