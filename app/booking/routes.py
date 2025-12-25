# app/booking/routes.py (FULL REPLACE - FIXED)
from flask import render_template, redirect, url_for, flash, Blueprint, abort, request
from flask_login import login_required, current_user
from app import db
from app.models import Rental
from app.utils import save_picture
from app.forms import PaymentUploadForm

# Buat blueprint
booking_bp = Blueprint('booking', __name__)


# ==========================================================
# RUTE UNTUK DASHBOARD PENYEWA (RIWAYAT PEMINJAMAN)
# ==========================================================
@booking_bp.route('/history')
@login_required  # Hanya user ter-login yang bisa lihat
def history():
    """Tampilkan riwayat pesanan user dengan pagination"""
    
    # Ambil parameter halaman dari URL (misal ?page=2), default hal 1
    page = request.args.get('page', 1, type=int)
    
    # Query dengan pagination (10 pesanan per halaman)
    rentals = Rental.query.filter_by(user_id=current_user.id)\
        .order_by(Rental.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('booking/history.html', 
                           title='Riwayat Peminjaman Saya',
                           rentals=rentals)


# ==========================================================
# RUTE UNTUK UPLOAD BUKTI PEMBAYARAN
# ==========================================================
@booking_bp.route('/payment/<int:rental_id>', methods=['GET', 'POST'])
@login_required
def upload_payment(rental_id):
    """Upload atau update bukti pembayaran transfer"""
    
    # Ambil data rental dari ID, pastikan itu punya user yang login
    rental = Rental.query.get_or_404(rental_id)
    
    # Security check: pastikan rental ini milik user yang login
    if rental.user_id != current_user.id:
        abort(403)  # Forbidden - dilarang akses punya orang
    
    # Validasi status: hanya bisa upload jika sudah di-ACC
    if rental.order_status != 'ACC':
        flash('Pesanan belum di-ACC oleh admin. Tunggu konfirmasi terlebih dahulu.', 'warning')
        return redirect(url_for('booking.history'))
    
    # Validasi pembayaran: hanya bisa upload jika belum bayar atau sedang menunggu
    if rental.payment_status not in ['Belum Bayar', 'Menunggu Konfirmasi']:
        flash('Pembayaran untuk pesanan ini sudah diproses.', 'info')
        return redirect(url_for('booking.history'))
    
    # Form upload
    form = PaymentUploadForm()

    if form.validate_on_submit():
        # Cek apakah ada file
        if form.proof.data:
            try:
                # Simpan gambar menggunakan helper
                filename = save_picture(
                    form.proof.data, 
                    'PAYMENT_UPLOAD_FOLDER', 
                    output_size=(800, 800)
                )
                
                # Update database
                rental.payment_proof = filename
                rental.payment_status = 'Menunggu Konfirmasi'
                db.session.commit()
                
                flash('✅ Bukti transfer berhasil di-upload! Admin akan segera memverifikasi.', 'success')
                return redirect(url_for('booking.history'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Gagal menyimpan bukti: {str(e)}', 'danger')
    
    return render_template('booking/upload_payment.html', 
                           title='Konfirmasi Pembayaran', 
                           form=form, 
                           rental=rental)