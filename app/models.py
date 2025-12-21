# app/models.py
import secrets
from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================================
# TABEL 1: USERS (Admin, Staff, Penyewa) + 2FA Support
# ==========================================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.Enum('penyewa', 'staff', 'admin'), nullable=False, default='penyewa')
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')

    # --- Kolom untuk Two-Factor Authentication ---
    otp_secret = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rentals = db.relationship('Rental', backref='borrower', lazy=True)

    # Helpers
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}')"


# ==========================================================
# TABEL 2: CATEGORIES
# ==========================================================
class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    items = db.relationship('Item', backref='category', lazy=True)

    def __repr__(self):
        return f"Category('{self.name}')"


# ==========================================================
# TABEL 3: ITEMS
# ==========================================================
class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price_per_hour = db.Column(db.Numeric(10, 2), nullable=True)
    price_per_day = db.Column(db.Numeric(10, 2), nullable=True)
    stock = db.Column(db.Integer, nullable=False, default=1)
    image_filename = db.Column(db.String(100), default='default_item.jpg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    rentals = db.relationship('RentalItem', backref='item', lazy=True)

    def __repr__(self):
        return f"Item('{self.name}', 'Stok: {self.stock}')"


# ==========================================================
# TABEL 4: RENTALS (Pesanan)
# ==========================================================
class Rental(db.Model):
    __tablename__ = 'rentals'
    
    id = db.Column(db.Integer, primary_key=True)

    # PUBLIC ID untuk tampilan/email (unik, tidak menggantikan PK internal)
    # Format default: RK- + 8 hex uppercase (contoh: RK-A1B2C3D4)
    public_id = db.Column(db.String(32), unique=True, nullable=True, default=lambda: "RK-" + secrets.token_hex(4).upper())

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pickup_date = db.Column(db.DateTime, nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    order_status = db.Column(db.Enum('Ditinjau', 'ACC', 'Ditolak'), nullable=False, default='Ditinjau')

    payment_status = db.Column(
        db.Enum(
            'Ditinjau', 'Belum Bayar', 'Menunggu Konfirmasi',
            'Pengambilan', 'Selesai', 'Dibatalkan'
        ),
        nullable=False,
        default='Ditinjau'
    )

    payment_proof = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('RentalItem', backref='rental', lazy=True)

    def __repr__(self):
        pid = self.public_id if getattr(self, "public_id", None) else self.id
        return f"Rental('{pid}', 'User: {self.user_id}', 'Status: {self.order_status}')"


# ==========================================================
# TABEL 5: RENTAL_ITEMS (Detail Keranjang)
# ==========================================================
class RentalItem(db.Model):
    __tablename__ = 'rental_items'
    
    id = db.Column(db.Integer, primary_key=True)
    rental_id = db.Column(db.Integer, db.ForeignKey('rentals.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    duration_hours = db.Column(db.Integer, nullable=False)
    price_at_checkout = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self):
        return f"RentalItem('RentalID: {self.rental_id}', 'ItemID: {self.item_id}', 'Durasi: {self.duration_hours} jam')"
