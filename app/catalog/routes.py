# app/catalog/routes.py
from flask import render_template, Blueprint, request
from sqlalchemy import or_
from app.models import Item, Category

catalog_bp = Blueprint('catalog', __name__)

@catalog_bp.route('/items')
@catalog_bp.route('/items/category/<int:category_id>')
def list_items(category_id=None):
    """
    Daftar item dengan:
    - pagination (per_page default 9)
    - optional filter category_id (route param)
    - optional search q (query param) -> cari di item.name atau category.name
    Query params:
      - page: nomor halaman
      - per_page: jumlah item per halaman
      - q: search query
    """
    # Ambil semua kategori untuk sidebar
    categories = Category.query.order_by(Category.name).all()

    # Pagination params
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 9, type=int)  # default 9 per halaman

    # Search query (from navbar)
    q = request.args.get('q', type=str)
    q = q.strip() if q else None

    # Bangun query dasar (join Category agar bisa search berdasarkan nama kategori)
    items_query = Item.query.join(Category, isouter=True).order_by(Item.name)

    # Jika ada filter kategori lewat route
    current_category = None
    if category_id:
        items_query = items_query.filter(Item.category_id == category_id)
        current_category = Category.query.get(category_id)

    # Jika ada search query, filter nama item atau nama kategori (case-insensitive)
    if q:
        pattern = f"%{q}%"
        items_query = items_query.filter(
            or_(
                Item.name.ilike(pattern),
                Category.name.ilike(pattern)
            )
        )

    # Jalankan paginate (error_out=False supaya tidak error ketika page terlalu besar)
    items_paginated = items_query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'catalog/list_items.html',
        title='Katalog Barang',
        items=items_paginated,            # objek pagination
        categories=categories,
        current_category=current_category,
        q=q
    )
