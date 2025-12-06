# wsgi.py  (FULL REPLACE)
"""
WSGI entry point for production servers (Gunicorn, uWSGI, mod_wsgi).
This file exposes the WSGI callable `app` that server processes will run.
"""

from app import create_app

# Create the Flask app using the factory pattern
app = create_app()

# Optional: simple test run if executed directly (not used in production)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
