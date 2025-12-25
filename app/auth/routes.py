import time
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    session,
    make_response,
)
from app import db, bcrypt, mail
from app.forms import (
    RegistrationForm, 
    LoginForm, 
    RequestResetForm, 
    ResetPasswordForm
)
from app.models import User
# IMPORT FUNGSI EMAIL DARI UTILS (Agar tidak dobel kode)
from app.utils import send_reset_email 
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message

auth_bp = Blueprint("auth", __name__, template_folder="templates/auth")

# ==========================================================
# REGISTRASI (TANPA NO HP)
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
# LOGIN (DENGAN MODE DETEKTIF ERROR)
# ==========================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "staff":
            return redirect(url_for("staff.dashboard"))
        return redirect(url_for("main.home"))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # DETEKTIF KASUS 1: Email tidak ditemukan
        if not user:
            flash("Login Gagal: Email tidak terdaftar. Silakan daftar akun terlebih dahulu.", "danger")
        
        # DETEKTIF KASUS 2: Password tidak cocok
        elif not bcrypt.check_password_hash(user.password_hash, form.password.data):
            flash("Login Gagal: Password salah. Periksa huruf besar, kecil, dan simbol.", "danger")
        
        # KASUS 3: Sukses (Validasi Berhasil)
        else:
            # --- LOGIKA ADMIN (2FA) ---
            if user.role == "admin":
                session["pre_2fa_userid"] = user.id
                session["pre_2fa_remember"] = bool(form.remember.data)

                if not user.otp_secret:
                    flash("Aktifkan 2FA terlebih dahulu sebelum masuk dashboard.", "warning")
                    return redirect(url_for("twofa.twofa_setup", user_id=user.id))

                flash("Masukkan kode 2FA dari aplikasi autentikator Anda.", "info")
                return redirect(url_for("twofa.verify_page"))

            # --- LOGIN NORMAL (PENYEWA/STAFF) ---
            login_user(user, remember=form.remember.data)

            if user.role == "staff":
                return redirect(url_for("staff.dashboard"))

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for("main.home"))

    return render_template("auth/login.html", title="Login", form=form)


# ==========================================================
# LUPA PASSWORD: MINTA LINK RESET
# ==========================================================
@auth_bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        try:
            # Fungsi send_reset_email sekarang dipanggil dari utils.py
            send_reset_email(user)
            flash('Instruksi reset password telah dikirim ke email Anda. Silakan cek inbox.', 'info')
        except Exception:
            flash('Terjadi kesalahan pengiriman. Silakan coba lagi dalam 1 menit.', 'warning')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_request.html', title='Reset Password', form=form)


# ==========================================================
# LUPA PASSWORD: HALAMAN INPUT PASSWORD BARU
# ==========================================================
@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    user = User.verify_reset_token(token)
    if user is None:
        flash('Token reset tidak valid atau sudah kedaluwarsa.', 'warning')
        return redirect(url_for('auth.reset_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password_hash = hashed_password
        db.session.commit()
        flash('Password Anda berhasil diperbarui! Silakan login dengan password baru.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_token.html', title='Reset Password', form=form)


# ==========================================================
# FINAL LOGIN SETELAH 2FA (ADMIN ONLY)
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

    # Bersihkan session 2FA setelah berhasil login
    session.pop("pre_2fa_userid", None)
    session.pop("pre_2fa_verified", None)
    session.pop("pre_2fa_remember", None)

    flash("2FA berhasil. Selamat datang, Admin.", "success")
    return redirect(url_for("admin.dashboard"))


# ==========================================================
# LOGOUT (HAPUS SEMUA SESI & COOKIE)
# ==========================================================
@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    
    response = make_response(redirect(url_for("main.home")))
    
    # Paksa hapus cookie remember me agar benar-benar keluar
    response.set_cookie('remember_token', '', expires=0)
    response.delete_cookie('remember_token')
    
    flash("Anda telah berhasil logout.", "info")
    return response