# app/__init__.py
"""
Application factory and core helpers for Rentalkuy.
FULL-REPLACE: improved send_email that respects PRINT_EMAILS_TO_CONSOLE,
robust fallback, non-blocking behaviour, and better logging for troubleshooting.
"""
import os
import threading
from base64 import b64encode
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import logging
import importlib

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

_logger = logging.getLogger(__name__)


# ==========================================================
# 2. Factory Function (FULL REPLACE)
# ==========================================================
def create_app(config_string="config.Config"):
    """
    Create and configure the Flask app.
    - Loads config from config_string (default config.Config)
    - Initializes extensions (db, migrate, login_manager, bcrypt, mail)
    - Optionally sets up Talisman when configured and installed
    - Registers existing blueprints (auto-detect bp variables)
    - Attaches helpers: send_email, generate_totp_secret, get_totp_uri, qr_image_base64
    """

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_string)

    # quick debug visibility for important flags at startup
    try:
        app.logger.debug("Config PRINT_EMAILS_TO_CONSOLE=%s", app.config.get("PRINT_EMAILS_TO_CONSOLE"))
    except Exception:
        pass

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
    # 6. Register Blueprints (auto-detect common bp names)
    # ==========================================================
    # mapping of module -> suggested url_prefix (only used if prefix not None)
    common_blueprints = {
        "app.main.routes": None,        # register at root
        "app.auth.routes": "/auth",
        "app.catalog.routes": "/catalog",
        "app.cart.routes": "/cart",
        "app.booking.routes": "/booking",
        "app.admin.routes": "/admin",
        "app.account.routes": "/account",
        "app.staff.routes": "/staff",
        "app.twofa.routes": None,       # optional
    }

    def _find_blueprint_from_module(module):
        """Try to detect a Blueprint object in a module by common attribute names."""
        for candidate in ("bp", "auth_bp", "main_bp", "catalog_bp", "cart_bp", "booking_bp", "admin_bp", "account_bp", "staff_bp", "twofa_bp"):
            bp = getattr(module, candidate, None)
            if bp is not None:
                return bp
        # fallback: try to find any attribute that looks like a Blueprint instance by type name
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            # avoid importing large objects; use duck-typing: check for 'register' attribute and 'name'
            if hasattr(obj, "name") and hasattr(obj, "register"):
                return obj
        return None

    for module_path, url_prefix in common_blueprints.items():
        try:
            mod = importlib.import_module(module_path)
            bp = _find_blueprint_from_module(mod)
            if bp:
                # if prefix explicitly provided, use it; otherwise register without prefix
                if url_prefix:
                    app.register_blueprint(bp, url_prefix=url_prefix)
                else:
                    app.register_blueprint(bp)
            else:
                _logger.debug("No blueprint found in %s", module_path)
        except ModuleNotFoundError:
            # module not present — that's acceptable for optional modules
            _logger.debug("Module not found (skipping): %s", module_path)
        except Exception:
            _logger.exception("Error while importing/registering blueprint from %s", module_path)

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
    def _send_via_flask_mail(msg):
        """Send using Flask-Mail (expects Message instance)."""
        try:
            if not _HAS_FLASK_MAIL or mail is None:
                app.logger.warning("Flask-Mail not available in _send_via_flask_mail.")
                return False
            mail.send(msg)
            return True
        except Exception:
            app.logger.exception("Exception while sending mail via Flask-Mail")
            return False

    def _send_via_smtp(subject, recipients, body, html=None, sender=None):
        """Fallback sending using smtplib; sends multipart/alternative."""
        try:
            sender = sender or app.config.get("MAIL_DEFAULT_SENDER")
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients if isinstance(recipients, (list, tuple)) else [recipients])

            part1 = MIMEText(body or "", "plain", "utf-8")
            msg.attach(part1)
            if html:
                part2 = MIMEText(html, "html", "utf-8")
                msg.attach(part2)

            server = smtplib.SMTP(app.config.get("MAIL_SERVER"), int(app.config.get("MAIL_PORT", 25)))
            if app.config.get("MAIL_USE_TLS"):
                server.starttls()
            username = app.config.get("MAIL_USERNAME")
            pwd = app.config.get("MAIL_PASSWORD")
            if username:
                server.login(username, pwd)
            server.sendmail(sender, recipients if isinstance(recipients, (list, tuple)) else [recipients], msg.as_string())
            server.quit()
            return True
        except Exception:
            app.logger.exception("Exception while sending mail via smtplib")
            return False

    def _send_async_wrapper(send_callable, *args, **kwargs):
        """Run a send callable in a freshly created app context (background thread)."""
        try:
            # create a fresh app context inside the thread so render_template etc work
            with app.app_context():
                return send_callable(*args, **kwargs)
        except Exception:
            app.logger.exception("Error in background send thread")
            return False

    def send_email(subject, recipients, body, html=None, sender=None, force_send=False):
        """
        Send email non-blocking.

        Behaviour summary:
        - If PRINT_EMAILS_TO_CONSOLE is truthy and force_send is False -> print/log email and return True (no network).
        - Otherwise, try Flask-Mail (if available), falling back to direct SMTP.
        - All network sending is performed in a background thread.
        - Returns True if scheduled (or printed), False otherwise.
        """
        if isinstance(recipients, str):
            recipients = [recipients]

        # If configured to print emails instead of sending, do that and skip network
        try:
            if app.config.get("PRINT_EMAILS_TO_CONSOLE", False) and not force_send:
                # Print a compact but informative representation to log
                try:
                    app.logger.info("[EMAIL-PRINT] subject=%s to=%s", subject, recipients)
                    app.logger.info("[EMAIL-PRINT] body (trunc): %s", (body or "").strip()[:1000])
                    if html:
                        app.logger.info("[EMAIL-PRINT] html (trunc): %s", (html or "")[:2000])
                except Exception:
                    # fallback to stdout if logger misbehaves
                    print("[EMAIL-PRINT] subject=", subject, "to=", recipients)
                    print((body or "")[:1000])
                return True
        except Exception:
            # don't crash because of logging error
            app.logger.exception("Error while checking PRINT_EMAILS_TO_CONSOLE flag")

        # Try Flask-Mail first (non-blocking)
        if _HAS_FLASK_MAIL and mail:
            try:
                msg = Message(subject=subject, recipients=recipients, body=body)
                if sender:
                    msg.sender = sender
                if html:
                    msg.html = html
                t = threading.Thread(target=_send_async_wrapper, args=(_send_via_flask_mail, msg), daemon=True)
                t.start()
                return True
            except Exception:
                app.logger.exception("Failed to prepare/send email via Flask-Mail, falling back to smtplib")

        # Fallback: use SMTP in background thread
        try:
            t = threading.Thread(target=_send_async_wrapper, args=(_send_via_smtp, subject, recipients, body, html, sender), daemon=True)
            t.start()
            return True
        except Exception:
            app.logger.exception("Failed to schedule fallback SMTP send")
            return False

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
