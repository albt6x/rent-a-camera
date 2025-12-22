"""
Application factory and core helpers for Rentalkuy.
FULL-REPLACE: improved logging, error handling, and security.
"""
import os
import threading
import smtplib
import logging
import importlib
from base64 import b64encode
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt

# ==========================================================
# 0. Optional Libraries Handling (Safe Import)
# ==========================================================
try:
    from flask_talisman import Talisman
    _HAS_TALISMAN = True
except Exception:
    Talisman = None
    _HAS_TALISMAN = False

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

# Login manager defaults
login_manager.login_view = "auth.login"
login_manager.login_message = "Silakan login untuk mengakses halaman ini."
login_manager.login_message_category = "info"

_logger = logging.getLogger(__name__)

# ==========================================================
# 2. Factory Function
# ==========================================================
def create_app(config_string="config.Config"):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_string)

    # Inisialisasi logger internal app
    with app.app_context():
        try:
            app.logger.debug("Config PRINT_EMAILS_TO_CONSOLE=%s", app.config.get("PRINT_EMAILS_TO_CONSOLE"))
        except Exception as e:
            app.logger.warning(f"Gagal mencetak debug config: {e}")

        # Ensure upload folders exist
        upload_base = app.config.get("UPLOAD_FOLDER_BASE")
        if upload_base:
            try:
                os.makedirs(upload_base, exist_ok=True)
                for key in ("UPLOAD_FOLDER_ITEMS", "UPLOAD_FOLDER_PAYMENT_PROOFS", "UPLOAD_FOLDER_PROFILE_PICS"):
                    p = app.config.get(key)
                    if p:
                        os.makedirs(p, exist_ok=True)
            except Exception as e:
                app.logger.error(f"Gagal menyiapkan folder upload: {e}")

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
    except Exception as e:
        app.logger.error(f"Gagal mengaktifkan Talisman: {e}")

    # ==========================================================
    # 5. Import models early so user_loader works
    # ==========================================================
    with app.app_context():
        try:
            from app import models  # noqa: F401
        except Exception as e:
            app.logger.error(f"Gagal mengimport models: {e}. User loader mungkin tidak berfungsi.")

    # ==========================================================
    # 6. Register Blueprints
    # ==========================================================
    common_blueprints = {
        "app.main.routes": None,
        "app.auth.routes": "/auth",
        "app.catalog.routes": "/catalog",
        "app.cart.routes": "/cart",
        "app.booking.routes": "/booking",
        "app.admin.routes": "/admin",
        "app.account.routes": "/account",
        "app.staff.routes": "/staff",
        "app.twofa.routes": None,
    }

    def _find_blueprint_from_module(module):
        for candidate in ("bp", "auth_bp", "main_bp", "catalog_bp", "cart_bp", "booking_bp", "admin_bp", "account_bp", "staff_bp", "twofa_bp"):
            bp = getattr(module, candidate, None)
            if bp is not None:
                return bp
        return None

    for module_path, url_prefix in common_blueprints.items():
        try:
            mod = importlib.import_module(module_path)
            bp = _find_blueprint_from_module(mod)
            if bp:
                app.register_blueprint(bp, url_prefix=url_prefix) if url_prefix else app.register_blueprint(bp)
        except Exception as e:
            app.logger.debug(f"Info Blueprint {module_path}: {e}")

    # ==========================================================
    # 7. Context Processor
    # ==========================================================
    try:
        from app.context_processors import inject_cart_count
        app.context_processor(inject_cart_count)
    except Exception as e:
        app.logger.warning(f"Gagal registrasi context processor: {e}")

    # ==========================================================
    # 8. Error Handlers
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

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models import User
            return User.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f"Login Manager gagal memuat user {user_id}: {e}")
            return None

    # ==========================================================
    # 10. EMAIL Helpers
    # ==========================================================
    def _send_async_wrapper(send_callable, *args, **kwargs):
        with app.app_context():
            try:
                return send_callable(*args, **kwargs)
            except Exception as e:
                app.logger.error(f"Gagal mengirim email di background thread: {e}")
                return False

    def send_email(subject, recipients, body, html=None, sender=None, force_send=False):
        if isinstance(recipients, str):
            recipients = [recipients]

        # Handle Console Printing
        if app.config.get("PRINT_EMAILS_TO_CONSOLE", False) and not force_send:
            try:
                app.logger.info(f"[EMAIL-PRINT] To: {recipients} | Subject: {subject}")
                return True
            except Exception as e:
                app.logger.error(f"Gagal mencetak email ke console: {e}")

        # Async Send
        if _HAS_FLASK_MAIL and mail:
            try:
                msg = Message(subject=subject, recipients=recipients, body=body, html=html, sender=sender)
                threading.Thread(target=_send_async_wrapper, args=(mail.send, msg), daemon=True).start()
                return True
            except Exception as e:
                app.logger.error(f"Gagal menjadwalkan email via Flask-Mail: {e}")
        
        return False

    app.send_email = send_email

    # ==========================================================
    # 11. 2FA Helpers
    # ==========================================================
    def qr_image_base64(provisioning_uri):
        if not qrcode:
            app.logger.error("Library qrcode tidak ditemukan.")
            return ""
        try:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            return f"data:image/png;base64,{b64encode(buf.getvalue()).decode('ascii')}"
        except Exception as e:
            app.logger.error(f"Gagal membuat QR Code: {e}")
            return ""

    app.qr_image_base64 = qr_image_base64
    return app