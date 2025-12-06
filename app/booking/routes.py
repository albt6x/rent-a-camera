# app/booking/routes.py
from flask import render_template, redirect, url_for, flash, Blueprint, abort
from flask_login import login_required, current_user
from app import db
from app.models import Rental
from app.utils import save_picture # <-- 1. IMPORT FUNGSI HELPER
from app.forms import PaymentUploadForm # <-- 2. IMPORT FORM BARU

# Buat blueprint
booking_bp = Blueprint('booking', __name__)


# ==========================================================
# RUTE UNTUK DASHBOARD PENYEWA (RIWAYAT PEMINJAMAN)
# ==========================================================
@booking_bp.route('/history')
@login_required # Hanya user ter-login yang bisa lihat
def history():
    rentals = Rental.query.filter_by(user_id=current_user.id).order_by(Rental.created_at.desc()).all()
    
    return render_template('booking/history.html', 
                           title='Riwayat Peminjaman Saya',
                           rentals=rentals)


# ==========================================================
# RUTE UNTUK UPLOAD BUKTI PEMBAYARAN (BARU!)
# ==========================================================
@booking_bp.route('/payment/<int:rental_id>', methods=['GET', 'POST'])
@login_required
def upload_payment(rental_id):
    # Ambil data rental dari ID, pastikan itu punya user yang login
    rental = Rental.query.get_or_404(rental_id)
    if rental.user_id != current_user.id:
        abort(403) # Dilarang akses punya orang
        
    # Jika user mencoba bayar pesanan yang belum di-ACC
    if rental.order_status != 'ACC' or rental.payment_status != 'Belum Bayar':
        flash('Pesanan ini tidak bisa dibayar saat ini.', 'warning')
        return redirect(url_for('booking.history'))
        
    form = PaymentUploadForm()

    if form.validate_on_submit():
        # Cek apakah ada file
        if form.proof.data:
            # Simpan gambar menggunakan helper kita
            # Kita simpan ke folder 'PAYMENT_UPLOAD_FOLDER'
            filename = save_picture(form.proof.data, 'PAYMENT_UPLOAD_FOLDER', output_size=(800, 800))
            
            # Update database
            rental.payment_proof = filename
            rental.payment_status = 'Menunggu Konfirmasi'
            db.session.commit()
            
            flash('Bukti transfer berhasil di-upload! Admin akan segera memverifikasi.', 'success')
            return redirect(url_for('booking.history'))
            
    return render_template('booking/upload_payment.html', 
                           title='Konfirmasi Pembayaran', 
                           form=form, 
                           rental=rental)