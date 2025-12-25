import secrets
from app import db
from flask import current_app
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
# Import untuk membuat token rahasia yang aman
from itsdangerous import URLSafeTimedSerializer as Serializer

# ==========================================================
# TABEL 1: USERS (Admin, Staff, Penyewa) + 2FA + RESET PASSWORD
# ==========================================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # --- KOLOM BARU: NOMOR HP (Untuk WhatsApp) ---
    phone = db.Column(db.String(20), nullable=True)

    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.Enum('penyewa', 'staff', 'admin'), nullable=False, default='penyewa')
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')

    # --- Kolom untuk Two-Factor Authentication ---
    otp_secret = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rentals = db.relationship('Rental', backref='borrower', lazy=True)

    # ------------------------------------------------------------------
    # FUNGSI TOKEN RESET PASSWORD (SOLUSI ERROR ATTRIBUTEERROR)
    # ------------------------------------------------------------------
    def get_reset_token(self):
        """Menghasilkan token unik untuk reset password (berlaku 30 menit)"""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        """Memvalidasi token reset password"""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except Exception:
            return None
        return User.query.get(user_id)
    # ------------------------------------------------------------------

    # Helpers Password
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
# TABEL 4: RENTALS (Pesanan) - FIXED ENUM
# ==========================================================
class Rental(db.Model):
    __tablename__ = 'rentals'
    
    id = db.Column(db.Integer, primary_key=True)

    # PUBLIC ID untuk tampilan/email
    public_id = db.Column(db.String(32), unique=True, nullable=True, default=lambda: "RK-" + secrets.token_hex(4).upper())

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pickup_date = db.Column(db.DateTime, nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    order_status = db.Column(db.Enum('Ditinjau', 'ACC', 'Ditolak'), nullable=False, default='Ditinjau')

    # ✅ FIXED: Tambah 'Menunggu Konfirmasi' dan 'Dibatalkan'
    payment_status = db.Column(
        db.Enum(
            'Ditinjau',
            'Belum Bayar',
            'Menunggu Konfirmasi',  # ✅ TAMBAH INI (untuk bukti transfer)
            'Pengambilan',
            'Selesai',
            'Dibatalkan'  # ✅ TAMBAH INI (untuk reject)
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