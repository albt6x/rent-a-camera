# app/auth/routes.py (FULL REPLACE)

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    session,
    make_response,  # Penting untuk hapus cookie manual
)
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm
from app.models import User
from flask_login import login_user, current_user, logout_user, login_required

auth_bp = Blueprint("auth", __name__, template_folder="templates/auth")


# ==========================================================
# REGISTRASI (VERSI CEPAT - TANPA NO HP)
# ==========================================================
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RegistrationForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(
            form.password.data
        ).decode("utf-8")

        # Buat User Baru (Tanpa Phone - Phone diisi nanti di Profil)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            role="penyewa",
        )

        db.session.add(user)
        db.session.commit()

        flash("Akun berhasil dibuat. Silakan login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", title="Daftar Akun", form=form)


# ==========================================================
# LOGIN (ADMIN + FIRST TIME 2FA FIX)
# ==========================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    RULE LOGIN FINAL:
    - Admin + otp_secret NULL  -> SETUP 2FA (QR)
    - Admin + otp_secret ADA   -> VERIFY 2FA
    - Staff                   -> staff dashboard
    - Penyewa                 -> home
    """

    # kalau sudah login, arahkan sesuai role (ANTI LOOP)
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "staff":
            return redirect(url_for("staff.dashboard"))
        return redirect(url_for("main.home"))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and bcrypt.check_password_hash(
            user.password_hash, form.password.data
        ):

            # ================= ADMIN =================
            if user.role == "admin":

                # simpan context login admin
                session["pre_2fa_userid"] = user.id
                session["pre_2fa_remember"] = bool(form.remember.data)

                # 🔴 FIRST TIME SETUP 2FA (otp_secret NULL)
                if not user.otp_secret:
                    flash(
                        "Aktifkan 2FA terlebih dahulu sebelum masuk dashboard.",
                        "warning",
                    )
                    return redirect(
                        url_for("twofa.twofa_setup", user_id=user.id)
                    )

                # 🟠 VERIFY 2FA (otp_secret SUDAH ADA)
                flash(
                    "Masukkan kode 2FA dari aplikasi autentikator Anda.",
                    "info",
                )
                return redirect(url_for("twofa.verify_page"))

            # ================= LOGIN NORMAL =================
            # KUNCI REMEMBER ME: Parameter remember diambil dari form
            login_user(user, remember=form.remember.data)

            if user.role == "staff":
                return redirect(url_for("staff.dashboard"))

            # Redirect ke halaman sebelumnya (next) jika ada
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for("main.home"))

        flash("Login gagal. Periksa email dan password.", "danger")

    return render_template("auth/login.html", title="Login", form=form)


# ==========================================================
# FINAL LOGIN SETELAH 2FA
# ==========================================================
@auth_bp.route("/2fa-verify", methods=["GET"])
def twofa_verify():
    user_id = session.get("pre_2fa_userid")
    verified = session.get("pre_2fa_verified")

    if not user_id or not verified:
        flash("Sesi 2FA tidak valid atau kadaluarsa.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user or user.role != "admin":
        flash("Akses admin tidak valid.", "danger")
        return redirect(url_for("auth.login"))

    remember_flag = bool(session.get("pre_2fa_remember", False))
    login_user(user, remember=remember_flag)

    # bersihkan session 2FA
    session.pop("pre_2fa_userid", None)
    session.pop("pre_2fa_verified", None)
    session.pop("pre_2fa_remember", None)

    flash("2FA berhasil. Selamat datang, Admin.", "success")
    return redirect(url_for("admin.dashboard"))


# ==========================================================
# LOGOUT (NUCLEAR FIX - HAPUS SEMUA DATA SESI)
# ==========================================================
@auth_bp.route("/logout")
# JANGAN PAKAI @login_required DISINI AGAR TIDAK LOOPING
def logout():
    # 1. Logout user dari Flask-Login
    logout_user()
    
    # 2. Bersihkan session flask
    session.clear()
    
    # 3. Buat response redirect ke home
    response = make_response(redirect(url_for("main.home")))
    
    # 4. PAKSA HAPUS COOKIE REMEMBER ME
    response.set_cookie('remember_token', '', expires=0)
    response.delete_cookie('remember_token')
    
    flash("Anda telah logout.", "info")
    return response