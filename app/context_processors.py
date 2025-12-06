# app/context_processors.py
from flask import session

def inject_cart_count():
    # Fungsi ini akan otomatis membuat variabel 'cart_count'
    # tersedia di semua template kita.
    count = len(session.get('cart', {}))
    return dict(cart_count=count)