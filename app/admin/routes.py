from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    Blueprint,
    abort,
    request,
    jsonify,
    send_file,
    current_app,
)
from flask_login import login_required, current_user
from app import db, bcrypt
from app.models import Category, Item, Rental, User, RentalItem
from app.forms import (
    CategoryForm,
    ItemForm,
    AddStaffForm,
    EditUserForm,
)
from app.utils import save_picture
from functools import wraps
from datetime import timedelta
import os

# safer helpers from email_utils
from app.utils import send_order_status_email # new

# Buat blueprint
admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------
# Helper: Aman mengirim email (tidak crash jika gagal)
# (tetap dipertahankan untuk backward-compat/override)
# ---------------------------------------------------------
def _safe_send_email(subject, recipients, text_body, html_body=None, sender=None):
    """
    Wrapper yang memanggil current_app.send_email (jika ada).
    Menangkap exception supaya proses utama tidak crash bila email gagal.
    """
    try:
        send_fn = getattr(current_app, "send_email", None)
        if not send_fn:
            current_app.logger.warning("send_email() tidak tersedia di app.")
            return False

        current_app.logger.debug("Scheduling email to %s (subject=%s)", recipients, subject)
        return send_fn(
            subject,
            recipients,
            text_body,
            html=html_body,
            sender=sender,
        )
    except Exception as exc:
        current_app.logger.exception("Gagal mengirim email: %s", exc)
        return False

# ==========================================================
# DECORATORS WAJIB (ADMIN / STAFF / 2FA)
# ==========================================================

from functools import wraps
from flask import abort, redirect, url_for, flash, session
from flask_login import current_user


# ----------------------------------------------------------
# 1. HANYA ADMIN
# ----------------------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ----------------------------------------------------------
# 2. ADMIN + STAFF
# ----------------------------------------------------------
def staff_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if current_user.role not in ["admin", "staff"]:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ----------------------------------------------------------
# 3. ADMIN + WAJIB 2FA
# ----------------------------------------------------------
def admin_2fa_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # wajib login admin
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)

        # admin belum aktifkan 2FA → langsung setup
        if not current_user.otp_secret:
            flash("Aktifkan 2FA terlebih dahulu sebelum masuk dashboard.", "warning")
            return redirect(url_for("twofa.twofa_setup"))

        # admin sudah punya 2FA tapi session belum verified
        if not session.get("admin_2fa_verified"):
            flash("Verifikasi 2FA diperlukan untuk mengakses halaman admin.", "warning")
            return redirect(url_for("twofa.verify_page"))

        return f(*args, **kwargs)

    return decorated_function


# ==========================================================
# 2. DASHBOARD -> LANGSUNG KE MANAJEMEN RESERVASI
# ==========================================================
@admin_bp.route("/dashboard")
@login_required
@admin_2fa_required
def dashboard():
    return redirect(url_for("admin.manage_reservations"))


# ==========================================================
# 3. MANAJEMEN KATEGORI (ROUTE MASIH ADA, MENUNYA BISA DIPAKAI)
# ==========================================================
@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@admin_2fa_required
def manage_categories():
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        exists = Category.query.filter_by(name=name).first()
        if exists:
            flash("Kategori dengan nama yang sama sudah ada.", "warning")
            return redirect(url_for("admin.manage_categories"))
        category = Category(name=name)
        db.session.add(category)
        db.session.commit()
        flash("Kategori baru berhasil ditambahkan!", "success")
        return redirect(url_for("admin.manage_categories"))

    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin/manage_categories.html", title="Manajemen Kategori", form=form, categories=categories
    )


# ==========================================================
# 4. MANAJEMEN BARANG (READ) - PAGINATED + KATEGORI INLINE
# ==========================================================
@admin_bp.route("/items/")
@login_required
@admin_2fa_required
def manage_items():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    items = Item.query.order_by(Item.name).paginate(page=page, per_page=per_page, error_out=False)

    categories = Category.query.order_by(Category.name).all()
    category_form = CategoryForm()

    return render_template(
        "admin/manage_items.html",
        title="Manajemen Stok Barang",
        items=items,
        categories=categories,
        category_form=category_form,
        per_page=per_page,
    )


# ==========================================================
# 4.b Add category inline (from manage_items page)
# ==========================================================
@admin_bp.route("/items/categories/add", methods=["POST"])
@login_required
@admin_2fa_required
def add_category_inline():
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        exists = Category.query.filter_by(name=name).first()
        if exists:
            flash("Kategori dengan nama yang sama sudah ada.", "warning")
        else:
            c = Category(name=name)
            db.session.add(c)
            db.session.commit()
            flash(f"Kategori '{c.name}' berhasil ditambahkan.", "success")
    else:
        for field, errs in form.errors.items():
            for e in errs:
                flash(e, "danger")
    return redirect(url_for("admin.manage_items"))


# ==========================================================
# 4.c Delete category inline
# ==========================================================
@admin_bp.route("/items/categories/delete/<int:category_id>", methods=["POST"])
@login_required
@admin_2fa_required
def delete_category_inline(category_id):
    category = Category.query.get_or_404(category_id)
    still_used = Item.query.filter_by(category_id=category.id).first()
    if still_used:
        flash(
            f"Tidak bisa menghapus kategori '{category.name}' karena masih ada item yang memakai kategori ini.",
            "danger",
        )
        return redirect(url_for("admin.manage_items"))

    db.session.delete(category)
    db.session.commit()
    flash(f"Kategori '{category.name}' berhasil dihapus.", "success")
    return redirect(url_for("admin.manage_items"))


# ==========================================================
# 5. TAMBAH BARANG
# ==========================================================
@admin_bp.route("/items/new", methods=["GET", "POST"])
@login_required
@admin_2fa_required
def add_item():
    form = ItemForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data, "UPLOAD_FOLDER_ITEMS", output_size=(500, 500))
        else:
            picture_file = "default_item.jpg"

        item = Item(
            name=form.name.data,
            description=form.description.data,
            price_per_hour=form.price_per_hour.data,
            price_per_day=form.price_per_day.data,
            stock=form.stock.data,
            category_id=form.category.data,
            image_filename=picture_file,
        )
        db.session.add(item)
        db.session.commit()
        flash("Barang baru berhasil ditambahkan!", "success")
        return redirect(url_for("admin.manage_items"))

    return render_template("admin/item_form.html", title="Tambah Barang Baru", form=form, current_image=None)


# ==========================================================
# 6. EDIT BARANG
# ==========================================================
@admin_bp.route("/items/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
@admin_2fa_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    form = ItemForm(obj=item)
    form.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]

    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data, "UPLOAD_FOLDER_ITEMS", output_size=(500, 500))
            item.image_filename = picture_file

        item.name = form.name.data
        item.description = form.description.data
        item.price_per_hour = form.price_per_hour.data
        item.price_per_day = form.price_per_day.data
        item.stock = form.stock.data
        item.category_id = form.category.data

        db.session.commit()
        flash(f"Barang '{item.name}' telah berhasil diperbarui!", "success")
        return redirect(url_for("admin.manage_items"))

    elif request.method == "GET":
        form.category.data = item.category_id
        form.name.data = item.name
        form.description.data = item.description
        form.price_per_hour.data = item.price_per_hour
        form.price_per_day.data = item.price_per_day
        form.stock.data = item.stock

    current_image = item.image_filename
    return render_template("admin/item_form.html", title=f"Edit Barang: {item.name}", form=form, current_image=current_image)


# ==========================================================
# 7. MANAJEMEN RESERVASI + FILTER STATUS (PAGINATED)
# ==========================================================
@admin_bp.route("/reservations")
@login_required
@staff_or_admin_required
def manage_reservations():
    status_filter = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    query = Rental.query.order_by(Rental.created_at.desc())

    if status_filter:
        if status_filter == "Selesai":
            query = query.filter(Rental.payment_status == "Selesai")
        else:
            query = query.filter(Rental.order_status == status_filter)

    rentals = query.paginate(page=page, per_page=per_page, error_out=False)
    is_staff_dashboard = (current_user.role == "staff")

    return render_template(
        "admin/manage_reservations.html",
        title="Manajemen Reservasi",
        rentals=rentals,
        is_staff_dashboard=is_staff_dashboard,
        status_filter=status_filter,
    )


# ==========================================================
# NEW: VIEW PAYMENT PROOF (ADMIN ONLY)
# ==========================================================
@admin_bp.route("/reservations/proof/<int:rental_id>")
@login_required
@admin_2fa_required
def view_proof(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    proof_filename = getattr(rental, "payment_proof", None)
    if not proof_filename:
        abort(404)

    upload_dir = current_app.config.get("UPLOAD_FOLDER_PAYMENT_PROOFS")
    if not upload_dir:
        upload_dir = os.path.join(current_app.root_path, "static", "uploads", "payment_proofs")

    file_path = os.path.join(upload_dir, proof_filename)

    if not os.path.exists(file_path):
        alt = os.path.join(current_app.root_path, "uploads", "payment_proofs", proof_filename)
        if os.path.exists(alt):
            file_path = alt
        else:
            abort(404)

    return send_file(file_path, mimetype=None, as_attachment=False)


# ==========================================================
# 8. APPROVE (ACC) RESERVASI - FIXED: CEK BUKTI BAYAR
# ==========================================================
@admin_bp.route("/reservations/approve/<int:rental_id>", methods=["POST"])
@login_required
@staff_or_admin_required
def approve_rental(rental_id):
    rental = Rental.query.get_or_404(rental_id)

    # Cek stok
    for item_in_rental in rental.items:
        item_db = item_in_rental.item
        if item_db.stock <= 0:
            flash(f"Gagal ACC: Stok untuk '{item_db.name}' sudah habis (0).", "danger")
            return redirect(url_for("admin.manage_reservations"))

    # Update stok
    for item_in_rental in rental.items:
        item_in_rental.item.stock -= 1

    # Update status order
    rental.order_status = "ACC"
    
    # ✅ FIX: CEK APAKAH USER SUDAH UPLOAD BUKTI
    if rental.payment_proof:
        # Jika sudah ada bukti → status jadi "Menunggu Konfirmasi"
        rental.payment_status = "Menunggu Konfirmasi"
        flash(f"✅ Reservasi #{rental.public_id} di-ACC. Bukti transfer perlu divalidasi.", "success")
    else:
        # Jika belum ada bukti → status "Belum Bayar" (cash)
        rental.payment_status = "Belum Bayar"
        flash(f"✅ Reservasi #{rental.public_id} di-ACC. Menunggu pembayaran cash.", "success")
    
    db.session.commit()

    # Kirim email ACC
    send_order_status_email(rental.borrower, rental, 'order_approved.html', 'Pesanan Disetujui')

    if current_user.role == "staff":
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("admin.manage_reservations"))


# ==========================================================
# 9. REJECT RESERVASI (USE email_utils helper)
# ==========================================================
@admin_bp.route("/reservations/reject/<int:rental_id>", methods=["POST"])
@login_required
@staff_or_admin_required
def reject_rental(rental_id):
    """
    TOLAK ORDER / BUKTI BAYAR
    - Kembalikan stok jika sudah dipotong
    - Set status → Ditolak / Dibatalkan
    """
    rental = Rental.query.get_or_404(rental_id)

    # Kembalikan stok (jika order sudah di-ACC sebelumnya)
    if rental.order_status == 'ACC':
        for item_in_rental in rental.items:
            item_in_rental.item.stock += 1

    # Update status
    rental.order_status = 'Ditolak'
    rental.payment_status = 'Dibatalkan'
    db.session.commit()

    # Kirim email penolakan
    try:
        from app.email_utils import send_order_rejected_email
        send_order_rejected_email(rental, rental.borrower, reason="Pesanan ditolak oleh admin.", force_send=False)
    except Exception as e:
        current_app.logger.error(f"Gagal kirim email order_rejected: {e}")

    flash(f'❌ Order #{rental.public_id} telah ditolak. Stok dikembalikan.', 'info')

    if current_user.role == "staff":
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("admin.manage_reservations"))


# ==========================================================
# 10. HAPUS ITEM
# ==========================================================
@admin_bp.route("/items/delete/<int:item_id>", methods=["POST"])
@login_required
@admin_2fa_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"Barang '{item.name}' telah berhasil dihapus.", "success")
    return redirect(url_for("admin.manage_items"))


# ==========================================================
# 11. MANAJEMEN STAF (PAGINATED)
# ==========================================================
@admin_bp.route("/staff", methods=["GET", "POST"])
@login_required
@admin_2fa_required
def manage_staff():
    form = AddStaffForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        new_staff = User(username=form.username.data, email=form.email.data, password_hash=hashed_password, role="staff")
        db.session.add(new_staff)
        db.session.commit()
        flash(f"Akun staf '{form.username.data}' berhasil dibuat!", "success")
        return redirect(url_for("admin.manage_staff"))

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    users_query = User.query.filter(User.role != "admin").order_by(User.role.desc(), User.id.asc())
    users = users_query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template("admin/manage_staff.html", title="Manajemen Staf & Pengguna", form=form, users=users)


# ==========================================================
# 12. EDIT PENGGUNA (STAF/PENYEWA)
# ==========================================================
@admin_bp.route("/staff/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_2fa_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        abort(403)

    form = EditUserForm(original_username=user.username, original_email=user.email)

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        db.session.commit()
        flash(f"Pengguna '{user.username}' telah diperbarui.", "success")
        return redirect(url_for("admin.manage_staff"))

    elif request.method == "GET":
        form.username.data = user.username
        form.email.data = user.email
        form.role.data = user.role

    return render_template("admin/edit_user.html", title=f"Edit Pengguna: {user.username}", form=form, user=user)


# ==========================================================
# 13. HAPUS PENGGUNA (STAF/PENYEWA) + CEK RIWAYAT RENTAL
# ==========================================================
@admin_bp.route("/staff/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_2fa_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == "admin" or user.id == current_user.id:
        flash("Anda tidak bisa menghapus akun Anda sendiri atau akun admin lain.", "danger")
        return redirect(url_for("admin.manage_staff"))

    has_rental = Rental.query.filter_by(user_id=user.id).first()

    if has_rental:
        flash(
            f"Pengguna '{user.username}' tidak dapat dihapus karena memiliki riwayat reservasi. Data ini dibutuhkan untuk histori transaksi.",
            "danger",
        )
        return redirect(url_for("admin.manage_staff"))

    db.session.delete(user)
    db.session.commit()
    flash(f"Pengguna '{user.username}' telah berhasil dihapus.", "success")
    return redirect(url_for("admin.manage_staff"))


# ==========================================================
# 14. DATA KALENDER (OPSIONAL)
# ==========================================================
@admin_bp.route("/calendar_data")
@login_required
@admin_2fa_required
def calendar_data():
    rentals = Rental.query.filter((Rental.order_status == "ACC") | (Rental.payment_status == "Pengambilan")).all()

    events_list = []
    for rental in rentals:
        user = rental.borrower
        for rental_item in rental.items:
            item = rental_item.item
            start_date = rental.pickup_date
            end_date = rental.pickup_date + timedelta(hours=rental_item.duration_hours)
            title = f"{item.name} - {user.username}"

            color = "#007bff"
            if rental.payment_status == "Pengambilan":
                color = "#28a745"

            events_list.append(
                {
                    "title": title,
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "color": color,
                    "url": url_for("admin.manage_reservations"),
                }
            )

    return jsonify(events_list)


# ==========================================================
# 15. KONFIRMASI PEMBAYARAN (VALIDASI BUKTI / CASH)
# ==========================================================
@admin_bp.route("/reservations/confirm_payment/<int:rental_id>", methods=["POST"])
@login_required
@staff_or_admin_required
def confirm_payment(rental_id):
    """
    VALIDASI PEMBAYARAN (Transfer atau Cash)
    - Jika ada payment_proof → Validasi bukti transfer
    - Jika tidak ada → Konfirmasi cash/offline
    """
    rental = Rental.query.get_or_404(rental_id)

    # Pastikan order sudah di-ACC
    if rental.order_status != 'ACC':
        flash('Order belum di-ACC, tidak bisa validasi pembayaran.', 'warning')
        return redirect(url_for('admin.manage_reservations'))

    # Update status → PENGAMBILAN (siap diambil)
    rental.payment_status = 'Pengambilan'
    db.session.commit()

    # Kirim email konfirmasi
    try:
        from app.email_utils import send_payment_confirmed_email
        send_payment_confirmed_email(rental, rental.borrower, force_send=False)
    except Exception as e:
        current_app.logger.error(f"Gagal kirim email payment_confirmed: {e}")

    flash(f'✅ Pembayaran untuk order #{rental.public_id} telah dikonfirmasi. Barang siap diambil!', 'success')

    if current_user.role == "staff":
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("admin.manage_reservations"))


# ==========================================================
# 16. TANDAI SELESAI (BARANG DIKEMBALIKAN)
# ==========================================================
@admin_bp.route("/reservations/mark_returned/<int:rental_id>", methods=["POST"])
@login_required
@staff_or_admin_required
def mark_as_returned(rental_id):
    """
    TANDAI SELESAI (Barang sudah dikembalikan)
    - Update status → Selesai
    - Kembalikan stok
    """
    rental = Rental.query.get_or_404(rental_id)

    # Pastikan sudah dalam status Pengambilan
    if rental.payment_status != 'Pengambilan':
        flash('Order belum dalam status "Siap Diambil".', 'warning')
        return redirect(url_for('admin.manage_reservations'))

    # Kembalikan stok
    for item_in_rental in rental.items:
        item_in_rental.item.stock += 1

    # Update status
    rental.payment_status = 'Selesai'
    db.session.commit()

    # Kirim email selesai
    try:
        from app.email_utils import send_reservation_completed_email
        send_reservation_completed_email(rental, rental.borrower, force_send=False)
    except Exception as e:
        current_app.logger.error(f"Gagal kirim email reservation_completed: {e}")

    flash(f'✅ Order #{rental.public_id} telah selesai. Stok dikembalikan.', 'success')

    if current_user.role == "staff":
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("admin.manage_reservations"))


# ==========================================================
# 17. TANDAI DIAMBIL (LEGACY - OPTIONAL)
# ==========================================================
@admin_bp.route("/reservations/take/<int:rental_id>", methods=["POST"])
@login_required
@staff_or_admin_required
def mark_as_taken(rental_id):
    rental = Rental.query.get_or_404(rental_id)

    rental.payment_status = "Pengambilan"
    db.session.commit()

    flash(f"Reservasi #{rental.public_id} telah diambil oleh penyewa.", "info")

    borrower = rental.borrower
    if borrower and getattr(borrower, "email", None):
        subject = f"[Rentalkuy] Reservasi #{rental.public_id} - Siap Diambil"
        body = (
            f"Halo {borrower.username},\n\n"
            f"Reservasi #{rental.public_id} sudah siap diambil.\n\n"
            "Terima kasih,\nRentalkuy"
        )
        _safe_send_email(subject, [borrower.email], body)

    if current_user.role == "staff":
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("admin.manage_reservations"))