# app/context_processors.py
from flask import has_request_context, session
from flask_login import current_user

def inject_cart_count():
    """
    Safe context processor — aman digunakan di dalam dan di luar request context.
    Menghindari error 'Working outside of request context'.
    """
    # Jika dipanggil tanpa request actif (flask shell, email renderer) → return default
    if not has_request_context():
        return {"cart_count": 0, "current_user": None}

    # Aman membaca session
    try:
        cart = session.get("cart", {})
        cart_count = len(cart) if hasattr(cart, "__len__") else 0
    except Exception:
        cart_count = 0

    # Aman membaca current_user
    try:
        user = current_user if getattr(current_user, "is_authenticated", False) else None
    except Exception:
        user = None

    return {
        "cart_count": cart_count,
        "current_user": user
    }
