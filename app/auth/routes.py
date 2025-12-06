# app/auth/routes.py
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    session,
    current_app,
)
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm
from app.models import User
from flask_login import login_user, current_user, logout_user, login_required
import pyotp

auth_bp = Blueprint("auth", __name__, template_folder="templates/auth")


# ==========================================================
# RUTE UNTUK REGISTRASI (DAFTAR AKUN BARU)
# ==========================================================
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RegistrationForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            role="penyewa",  # Pendaftaran publik SELALU 'penyewa'
        )

        db.session.add(user)
        db.session.commit()

        flash("Akun Anda telah berhasil dibuat! Silakan login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", title="Daftar Akun", form=form)


# ==========================================================
# RUTE UNTUK LOGIN (DENGAN PENGALIHAN ROLE + 2FA ADMIN)
# ==========================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Kalau sudah login, arahkan berdasarkan role
    if current_user.is_authenticated:
        if getattr(current_user, "role", None) == "admin":
            return redirect(url_for("admin.dashboard"))
        elif getattr(current_user, "role", None) == "staff":
            return redirect(url_for("staff.dashboard"))
        else:
            return redirect(url_for("main.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            # Jika admin dan punya otp_secret -> harus melewati 2FA (TOTP)
            if getattr(user, "role", None) == "admin" and getattr(user, "otp_secret", None):
                # simpan sementara user id & remember ke session, redirect ke halaman verify
                session["pre_2fa_userid"] = int(user.id)
                session["pre_2fa_remember"] = bool(form.remember.data)
                flash("Masukkan kode 2FA dari aplikasi autentikator Anda.", "info")
                return redirect(url_for("auth.twofa_verify"))

            # Bukan admin (atau admin tanpa 2FA) -> login langsung
            login_user(user, remember=form.remember.data)

            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)

            # Pengalihan role setelah login
            if getattr(user, "role", None) == "admin":
                flash("Login Berhasil! Selamat Datang, Admin.", "success")
                return redirect(url_for("admin.dashboard"))
            elif getattr(user, "role", None) == "staff":
                flash("Login Berhasil! Selamat Datang, Staf.", "success")
                return redirect(url_for("staff.dashboard"))
            else:
                flash("Login Berhasil!", "success")
                return redirect(url_for("main.home"))
        else:
            flash("Login Gagal. Cek kembali email dan password Anda.", "danger")

    return render_template("auth/login.html", title="Login", form=form)


# ==========================================================
# RUTE 2FA VERIFY (untuk admin yang punya otp_secret)
# ==========================================================
@auth_bp.route("/2fa-verify", methods=["GET", "POST"])
def twofa_verify():
    """
    Halaman/endpoint verifikasi 2FA.
    Flow:
      - Setelah login password OK, admin dengan otp_secret akan diarahkan ke sini.
      - Session harus memiliki 'pre_2fa_userid' dan optional 'pre_2fa_remember'.
      - POST body/form: 'code' -> verifikasi via pyotp.
      - Jika valid -> login_user(...) dan hapus session sementara -> redirect ke admin.dashboard
    """
    pre_user_id = session.get("pre_2fa_userid")
    if not pre_user_id:
        flash("Sesi 2FA tidak ditemukan. Silakan login ulang.", "warning")
        return redirect(url_for("auth.login"))

    # Ambil user
    user = User.query.get(pre_user_id)
    if not user:
        session.pop("pre_2fa_userid", None)
        session.pop("pre_2fa_remember", None)
        flash("User tidak ditemukan. Silakan login ulang.", "warning")
        return redirect(url_for("auth.login"))

    # Jika user tidak punya otp_secret (misalnya sudah dihapus), balik ke login
    secret = getattr(user, "otp_secret", None)
    if not secret:
        session.pop("pre_2fa_userid", None)
        session.pop("pre_2fa_remember", None)
        flash("2FA tidak ditemukan untuk akun ini. Silakan login secara biasa.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code") or (request.json and request.json.get("code"))
        if not code:
            flash("Masukkan kode 2FA.", "warning")
            return render_template("auth/2fa_verify.html", title="Verifikasi 2FA")

        # verify
        try:
            totp = pyotp.TOTP(secret)
            ok = bool(totp.verify(code, valid_window=1))
        except Exception:
            ok = False

        if ok:
            # sukses: login user, hapus session sementara
            remember_flag = bool(session.get("pre_2fa_remember", False))
            login_user(user, remember=remember_flag)
            session.pop("pre_2fa_userid", None)
            session.pop("pre_2fa_remember", None)
            flash("2FA berhasil. Anda kini login sebagai admin.", "success")
            return redirect(url_for("admin.dashboard"))
        else:
            flash("Kode 2FA salah atau kedaluwarsa. Coba lagi.", "danger")
            return render_template("auth/2fa_verify.html", title="Verifikasi 2FA")

    # GET -> tampilkan halaman input kode 2FA
    return render_template("auth/2fa_verify.html", title="Verifikasi 2FA")


# ==========================================================
# RUTE UNTUK LOGOUT
# ==========================================================
@auth_bp.route("/logout")
@login_required
def logout():
    # Hapus juga sesi sementara apabila ada
    session.pop("pre_2fa_userid", None)
    session.pop("pre_2fa_remember", None)

    logout_user()
    flash("Anda telah logout.", "info")
    return redirect(url_for("main.home"))
