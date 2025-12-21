# config.py  (FULL REPLACE)
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    # try load default environment (no crash if .env missing)
    load_dotenv()

class Config:
    """
    Central application configuration.
    - Reads values from environment (.env recommended)
    - Sensible defaults provided for development
    """

    # ----------------------------
    # App / env flags
    # ----------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "changeme_dev_secret")
    DEBUG = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    TESTING = os.environ.get("FLASK_TESTING", "0").lower() in ("1", "true", "yes")

    # ----------------------------
    # Database
    # ----------------------------
    # Priority: DATABASE_URL env -> fallback sqlite file app.db in project root
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + str(BASE_DIR / "app.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Optional echo for debug SQL
    SQLALCHEMY_ECHO = os.environ.get("SQLALCHEMY_ECHO", "0").lower() in ("1", "true", "yes")

    # ----------------------------
    # Upload folders (absolute paths)
    # ----------------------------
    # Default base: app/static/uploads inside project (safe for dev)
    UPLOAD_FOLDER_BASE = os.environ.get(
        "UPLOAD_FOLDER_BASE",
        str(BASE_DIR / "app" / "static" / "uploads")
    )

    # Individual upload folder keys (fall back to subfolders of base)
    UPLOAD_FOLDER_ITEMS = os.environ.get("UPLOAD_FOLDER_ITEMS", os.path.join(UPLOAD_FOLDER_BASE, "items"))
    UPLOAD_FOLDER_PAYMENT_PROOFS = os.environ.get("UPLOAD_FOLDER_PAYMENT_PROOFS", os.path.join(UPLOAD_FOLDER_BASE, "payment_proofs"))
    UPLOAD_FOLDER_PROFILE_PICS = os.environ.get("UPLOAD_FOLDER_PROFILE_PICS", os.path.join(UPLOAD_FOLDER_BASE, "profile_pics"))

    # Backwards-compatible aliases used by some modules
    PROFILE_UPLOAD_FOLDER = UPLOAD_FOLDER_PROFILE_PICS
    UPLOAD_PROFILE_FOLDER = UPLOAD_FOLDER_PROFILE_PICS
    ITEMS_UPLOAD_FOLDER = UPLOAD_FOLDER_ITEMS
    PAYMENT_UPLOAD_FOLDER = UPLOAD_FOLDER_PAYMENT_PROOFS
    UPLOAD_FOLDER = UPLOAD_FOLDER_BASE

    # Max upload by default 10 MB (in bytes)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))

    # Allowed image extensions as list
    ALLOWED_IMAGE_EXTENSIONS = os.environ.get("ALLOWED_IMAGE_EXTENSIONS", "jpg,jpeg,png,webp,gif").split(",")

    # Default image fallback paths (these are suggestions; files may not exist)
    UPLOAD_DEFAULT_ITEM = os.environ.get("UPLOAD_DEFAULT_ITEM", os.path.join(UPLOAD_FOLDER_ITEMS, "default_item.jpg"))
    UPLOAD_DEFAULT_PROFILE = os.environ.get("UPLOAD_DEFAULT_PROFILE", os.path.join(UPLOAD_FOLDER_PROFILE_PICS, "default.jpg"))

    # ----------------------------
    # Pagination / UI
    # ----------------------------
    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", 10))

    # ----------------------------
    # Security / headers
    # ----------------------------
    ENABLE_TALISMAN = os.environ.get("ENABLE_TALISMAN", "0").lower() in ("1", "true", "yes")
    TALISMAN_CONTENT_SECURITY_POLICY = None
    TALISMAN_FORCE_HTTPS = os.environ.get("TALISMAN_FORCE_HTTPS", "0").lower() in ("1", "true", "yes")

    # Cookie settings
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False if DEBUG else True

    # ----------------------------
    # Optional admin contact
    # ----------------------------
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")

    # ----------------------------
    # Mail / Email (Flask-Mail)
    # ----------------------------
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.mailtrap.io")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", os.environ.get("MAILPORT", 2525)))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1").lower() in ("1", "true", "yes")
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "0").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    # Default sender: prefer explicit env value; fallback to formatted admin email
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", f"Rentalkuy <{os.environ.get('MAIL_FROM', 'no-reply@rentalkuy.local')}>")
    MAIL_DEBUG = os.environ.get("MAIL_DEBUG", "0").lower() in ("1", "true", "yes")

    # Friendly footer used by templates and fallback HTML in email_utils / routes
    MAIL_FOOTER = os.environ.get("MAIL_FOOTER", "Rentalkuy · Jl. Contoh No.1 · 0896-7833-XXXX")

    # ----------------------------
    # Two-Factor Authentication (TOTP)
    # ----------------------------
    TWOFA_ENABLED = os.environ.get("TWOFA_ENABLED", "1").lower() in ("1", "true", "yes")
    TWOFA_ISSUER = os.environ.get("TWOFA_ISSUER", "Rentalkuy")

    # ----------------------------
    # Convenience: ensure upload folders (list for app factory to create)
    # App factory may call os.makedirs on these paths.
    # ----------------------------
    UPLOAD_FOLDERS_TO_CREATE = [
        UPLOAD_FOLDER_BASE,
        UPLOAD_FOLDER_ITEMS,
        UPLOAD_FOLDER_PAYMENT_PROOFS,
        UPLOAD_FOLDER_PROFILE_PICS,
    ]

    # ----------------------------
    # Misc / extension toggles
    # ----------------------------
    # If you want emails to print to console for debugging when MAIL not configured
    PRINT_EMAILS_TO_CONSOLE = os.environ.get("PRINT_EMAILS_TO_CONSOLE", "0").lower() in ("1", "true", "yes")

    # Useful for external service keys (left blank unless in .env)
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
    SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

    # Add any other app-specific config values below as needed
