# app/cart/routes.py
from flask import render_template, redirect, url_for, flash, request, Blueprint, session
from app.models import Item, Rental, RentalItem
from app.forms import CheckoutForm
from app import db
from flask_login import login_required, current_user

# Buat blueprint
cart_bp = Blueprint('cart', __name__)


# ==========================================================
# 1. RUTE TAMBAH ITEM KE KERANJANG
# ==========================================================
@cart_bp.route('/add/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    duration_hours = int(request.form.get('duration'))
    item = Item.query.get_or_404(item_id)

    cart = session.get('cart', {})

    # kunci unik: "itemid_durasi"
    key = f"{item_id}_{duration_hours}"

    if key in cart:
        flash(f"'{item.name}' sudah ada di keranjang Anda.", 'warning')
    else:
        cart[key] = {
            'item_id': item_id,
            'duration_hours': duration_hours,
            'name': item.name,
            'price_per_day': float(item.price_per_day),
        }
        flash(f"'{item.name}' ({duration_hours} Jam) berhasil ditambahkan ke keranjang!", 'success')

    session['cart'] = cart
    return redirect(request.referrer or url_for('catalog.list_items'))


# ==========================================================
# 2. LIHAT KERANJANG & CHECKOUT
# ==========================================================
@cart_bp.route('/view', methods=['GET', 'POST'])
@login_required
def view_cart():
    form = CheckoutForm()
    cart_data = session.get('cart', {})
    items_in_cart = []
    subtotal = 0

    # Siapkan data item untuk ditampilkan
    if cart_data:
        for key, data in cart_data.items():
            item_obj = Item.query.get(data['item_id'])
            if not item_obj:
                # Kalau item sudah dihapus dari DB, lewati saja
                continue

            # Aturan harga: 12 jam = 0.6x harga 24 jam
            if data['duration_hours'] == 12:
                item_price = data['price_per_day'] * 0.6
            else:
                item_price = data['price_per_day']

            subtotal += item_price

            items_in_cart.append({
                'item': item_obj,
                'duration_hours': data['duration_hours'],
                'price': item_price,
                'key': key,
            })
    else:
        flash('Keranjang Anda masih kosong.', 'info')

    # LOGIKA CHECKOUT
    if form.validate_on_submit():
        if not items_in_cart:
            flash('Keranjang Anda masih kosong.', 'warning')
            return redirect(url_for('cart.view_cart'))

        # 1. Buat pesanan induk
        new_rental = Rental(
            user_id=current_user.id,
            pickup_date=form.pickup_date.data,
            total_price=subtotal,
            order_status='Ditinjau',
            payment_status='Ditinjau'
        )
        db.session.add(new_rental)
        db.session.commit()

        # 2. Simpan setiap item ke RentalItem
        for cart_item in items_in_cart:
            rental_item = RentalItem(
                rental_id=new_rental.id,
                item_id=cart_item['item'].id,
                duration_hours=cart_item['duration_hours'],
                price_at_checkout=cart_item['price']
            )
            db.session.add(rental_item)

        db.session.commit()

        # 3. Kosongkan keranjang
        session.pop('cart', None)

        flash('Pesanan Anda telah berhasil dibuat! Menunggu review admin.', 'success')
        return redirect(url_for('main.home'))

    return render_template(
        'cart/keranjang.html',
        title='Keranjang Belanja',
        items_in_cart=items_in_cart,
        subtotal=subtotal,
        form=form
    )


# ==========================================================
# 3. HAPUS ITEM DARI KERANJANG
# ==========================================================
@cart_bp.route('/remove/<string:key>')
@login_required
def remove_from_cart(key):
    cart = session.get('cart', {})

    if key in cart:
        item_name = cart[key]['name']
        cart.pop(key)
        session['cart'] = cart
        flash(f"'{item_name}' telah dihapus dari keranjang.", 'info')

    return redirect(url_for('cart.view_cart'))
