#!/usr/bin/env python3
# seed.py
"""
Seed script for RentalKuy Flask app.

Cara pakai:
1. Aktifkan virtualenv/project environment kamu (venv).
2. Pastikan config di create_app() mengarah ke database yang ingin diisi.
3. Jalankan: python seed.py

Script akan:
- Tambah kategori (jika belum ada).
- Tambah item (jika belum ada nama sama).
- Tambah users: 1 admin, 3 staff, 5 penyewa (username+email random).
"""

import random
import string
from datetime import datetime
from app import create_app, db, bcrypt
from app.models import Category, Item, User

# -------------------------
# Konfigurasi seed default
# -------------------------
CATEGORIES = [
    "DSLR",
    "Mirrorless",
    "Camcorder",
    "Drone",
    "Lighting",
    "Audio",
    "Accessories",
]

# Jumlah item per kategori (sesuai kesepakatan)
ITEM_COUNTS = {
    "DSLR": 4,
    "Mirrorless": 5,
    "Camcorder": 3,
    "Drone": 3,
    "Lighting": 4,
    "Audio": 3,
    "Accessories": 2,
}

# default password (akan di-hash)
DEFAULT_PASSWORD = "Password123!"

# jumlah akun
NUM_ADMIN = 1
NUM_STAFF = 3
NUM_RENTERS = 5  # penyewa

# stok default dan price - kamu bisa ubah sesuai kebutuhan
DEFAULT_STOCK = 3

# sample price ranges per day (IDR)
PRICE_RANGES = {
    "DSLR": (250000, 450000),
    "Mirrorless": (300000, 500000),
    "Camcorder": (200000, 400000),
    "Drone": (300000, 600000),
    "Lighting": (50000, 200000),
    "Audio": (50000, 150000),
    "Accessories": (20000, 100000),
}

# -------------------------
# Helper functions
# -------------------------
def rand_suffix(n=5):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def make_username(prefix):
    return f"{prefix}_{rand_suffix(4)}"

def make_email(username):
    return f"{username}@example.com"

def short_description(category, idx):
    return f"{category} model {idx} — reliable gear for photo & video."

# -------------------------
# Main seeding logic
# -------------------------
def main():
    app = create_app()  # pakai config default; pastikan .env / config diset
    with app.app_context():
        print("Connected to app, starting seed...")

        # 1) Categories
        category_objs = {}
        for cat in CATEGORIES:
            c = Category.query.filter_by(name=cat).first()
            if not c:
                c = Category(name=cat)
                db.session.add(c)
                db.session.commit()
                print(f"Added category: {cat}")
            else:
                print(f"Category already exists: {cat}")
            category_objs[cat] = c

        # 2) Items (per kategori)
        created_items = 0
        for cat in CATEGORIES:
            count = ITEM_COUNTS.get(cat, 0)
            price_min, price_max = PRICE_RANGES.get(cat, (50000, 200000))
            for i in range(1, count + 1):
                # contrive unique name
                name = f"{cat} Camera Model {i}" if cat in ["DSLR", "Mirrorless", "Camcorder"] else f"{cat} Gear {i}"
                # check duplicate by name
                existing = Item.query.filter_by(name=name).first()
                if existing:
                    print(f"Item exists, skipping: {name}")
                    continue
                # randomize price per day inside range
                price_per_day = random.randint(price_min, price_max)
                # price per hour: for simplicity set 0.6 * per day for half-day 12h pricing practice (as earlier logic)
                price_per_hour = round(price_per_day * 0.6, 2)

                item = Item(
                    name=name,
                    description=short_description(cat, i),
                    price_per_hour=price_per_hour,
                    price_per_day=price_per_day,
                    stock=DEFAULT_STOCK,
                    category_id=category_objs[cat].id,
                    image_filename="default_item.jpg",
                )
                db.session.add(item)
                db.session.commit()
                created_items += 1
                print(f"Added item: {name} (cat: {cat}, Rp{price_per_day}/day)")

        # 3) Users: admin, staff, renters
        # helper to create user safely
        def create_user_if_not_exists(username, email, role, plain_password=DEFAULT_PASSWORD):
            u = User.query.filter((User.username == username) | (User.email == email)).first()
            if u:
                print(f"User exists, skip: {username} / {email}")
                return u, False
            pw_hash = bcrypt.generate_password_hash(plain_password).decode("utf-8")
            new_u = User(
                username=username,
                email=email,
                password_hash=pw_hash,
                role=role,
                image_file="default.jpg",
            )
            db.session.add(new_u)
            db.session.commit()
            print(f"Created user: {username} ({role})")
            return new_u, True

        created_users = 0
        # Admins
        for n in range(NUM_ADMIN):
            uname = make_username("admin")
            email = make_email(uname)
            u, ok = create_user_if_not_exists(uname, email, "admin")
            if ok:
                created_users += 1

        # Staff
        for n in range(NUM_STAFF):
            uname = make_username("staff")
            email = make_email(uname)
            u, ok = create_user_if_not_exists(uname, email, "staff")
            if ok:
                created_users += 1

        # Renters (penyewa)
        for n in range(NUM_RENTERS):
            uname = make_username("renter")
            email = make_email(uname)
            # role should match what code expects — earlier forms use 'penyewa' value for renter
            # but many places might expect 'renter' or 'penyewa'. We'll insert as 'penyewa' to match forms.
            u, ok = create_user_if_not_exists(uname, email, "penyewa")
            if ok:
                created_users += 1

        print("\nDONE seeding.")
        print(f"Total items added (approx): {created_items}")
        print(f"Total users created: {created_users}")
        print(f"Default password for created users: {DEFAULT_PASSWORD}")
        print("Please change default passwords after first login for security.")

if __name__ == "__main__":
    main()
