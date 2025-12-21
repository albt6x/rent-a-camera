# app/main/routes.py (FULL REPLACE)

from flask import render_template, Blueprint, request, jsonify
from flask_login import current_user
from app.models import Item

# Buat blueprint
main_bp = Blueprint('main', __name__)


# ========================================
# HOME PAGE (dengan fitur search biasa)
# ========================================
@main_bp.route('/')
@main_bp.route('/home')
def home():
    q = request.args.get("q", "").strip()

    # Jika user melakukan pencarian (Tekan Enter)
    if q:
        results = Item.query.filter(
            Item.name.ilike(f"%{q}%")
        ).order_by(Item.name).all()

        return render_template(
            'main/home.html',
            latest_items=results,
            search_query=q,
            search_mode=True,
            user=current_user
        )

    # MODE NORMAL → tampilkan 6 barang terbaru
    latest_items = Item.query.order_by(Item.id.desc()).limit(6).all()

    return render_template(
        'main/home.html',
        latest_items=latest_items,
        search_query="",
        search_mode=False,
        user=current_user
    )


# ========================================
# ABOUT PAGE
# ========================================
@main_bp.route('/about')
def about():
    return render_template('main/about.html', user=current_user)


# ========================================
# API: LIVE SEARCH AUTOCOMPLETE (BARU!)
# ========================================
# Ini adalah fungsi yang dipanggil oleh JavaScript di nav.html
# saat Anda mengetik huruf demi huruf.
@main_bp.route('/api/search_autocomplete')
def search_autocomplete():
    q = request.args.get('q', '').strip().lower()
    
    # Jika query kosong, kembalikan list kosong
    if not q:
        return jsonify([])

    # Cari barang yang namanya mengandung huruf yang diketik
    # Limit 5 saja biar dropdown tidak kepanjangan
    items = Item.query.filter(Item.name.ilike(f'%{q}%')).limit(5).all()
    
    # Format hasil ke dalam bentuk JSON agar bisa dibaca JavaScript
    results = []
    for item in items:
        # Cek atribut harga (sesuaikan dengan model Anda, bisa price_24h atau price_per_day)
        # Di sini saya gunakan logika: jika ada price_24h pakai itu, jika tidak pakai price_per_day, atau 0
        price = getattr(item, 'price_24h', getattr(item, 'price_per_day', 0))

        results.append({
            'id': item.id,
            'name': item.name,
            'image': item.image_filename,
            'price': price
        })
    
    return jsonify(results)