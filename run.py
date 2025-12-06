# run.py  (FULL REPLACE)
"""
Entrypoint untuk development server.
- Memanggil create_app() dari factory.
- Menyediakan shell context (db + model shortcuts).
- Membaca host/port dari environment untuk kemudahan (FLASK_RUN_HOST/PORT).
- Jika app.config.ENABLE_TALISMAN True dan paket flask_talisman tersedia, akan mencoba mengaktifkannya.

Catatan keamanan:
- Jangan gunakan `debug=True` di production.
- Untuk produksi gunakan WSGI server (gunicorn / uwsgi) yang memanggil create_app().
"""
import os
import sys
from app import create_app, db
from app.models import User, Item, Category, Rental, RentalItem

# Create the Flask app using factory
app = create_app()

# Optionally enable Flask-Talisman when configured and available
if app.config.get("ENABLE_TALISMAN"):
    try:
        from flask_talisman import Talisman
        # Only enable the basic Talisman instance — config already controls force-HTTPS/etc
        Talisman(app, content_security_policy=app.config.get("TALISMAN_CONTENT_SECURITY_POLICY", None), force_https=app.config.get("TALISMAN_FORCE_HTTPS", False))
        app.logger.info("Flask-Talisman enabled")
    except Exception as e:
        # Do not hard-fail if package missing; log so developer knows
        app.logger.warning("Flask-Talisman requested but could not be enabled: %s", e)

# Provide helpful objects in flask shell
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Item': Item,
        'Category': Category,
        'Rental': Rental,
        'RentalItem': RentalItem,
    }


if __name__ == '__main__':
    # Read host/port from environment for convenience
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))

    # Respect app config DEBUG flag
    debug = bool(app.config.get('DEBUG', False))

    # When running locally, show a small banner
    if debug:
        app.logger.info("Starting development server (debug=%s) on http://%s:%s", debug, host, port)

    try:
        app.run(host=host, port=port, debug=debug)
    except Exception as exc:
        app.logger.error("Failed to start Flask server: %s", exc)
        sys.exit(1)
