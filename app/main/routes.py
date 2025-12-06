# app/main/routes.py

from flask import render_template, Blueprint, request
from flask_login import current_user
from app.models import Item

# Buat blueprint
main_bp = Blueprint('main', __name__)


# ========================================
# HOME PAGE (dengan fitur search)
# ========================================
@main_bp.route('/')
@main_bp.route('/home')
def home():
    q = request.args.get("q", "").strip()

    # Jika user melakukan pencarian
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
