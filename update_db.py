from app import create_app, db
from sqlalchemy import text

# Inisialisasi aplikasi
app = create_app()

with app.app_context():
    try:
        # Buka koneksi ke database
        with db.engine.connect() as conn:
            # Perintah SQL manual untuk menyisipkan kolom 'phone' ke tabel 'users'
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
            conn.commit()
            
        print("✅ BERHASIL! Kolom 'phone' sudah ditambahkan ke database.")
        print("Sekarang fitur WhatsApp sudah siap digunakan.")
        
    except Exception as e:
        print(f"⚠️ INFO: {e}")
        print("Kemungkinan kolom sudah ada, atau nama tabel berbeda.")