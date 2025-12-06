# app/staff/routes.py  (FULL REPLACE)
"""
Routes untuk area staff.
Full replace: menggabungkan dashboard (dengan status filter + pagination),
view-only inventory, daily report, dan export CSV.
"""

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    Blueprint,
    abort,
    request,
    current_app,
    Response,
)
from flask_login import login_required, current_user
from app import db
from app.models import Rental, Item
from functools import wraps
from datetime import datetime, timedelta, date
import io
import csv

# Blueprint dengan prefix /staff supaya url_for('staff.dashboard') bekerja
staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


# -------------------------
# 1) decorator security
# -------------------------
def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'staff':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# -------------------------
# Helper: build base query & apply status filter + paginate
# -------------------------
def _get_rentals(status_filter, page, per_page):
    q = Rental.query.order_by(Rental.created_at.desc())
    if status_filter:
        q = q.filter(Rental.order_status == status_filter)
    return q.paginate(page=page, per_page=per_page, error_out=False)


# ==========================================================
# 2) RUTE DASHBOARD STAF (Manajemen Reservasi)
#    - mendukung ?status=Ditinjau|ACC|Ditolak|Selesai
#    - mengirim is_staff_dashboard=True ke template
# ==========================================================
@staff_bp.route('/dashboard')
@login_required
@staff_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config.get('ITEMS_PER_PAGE', 10), type=int)
    status = request.args.get('status', type=str)  # None or status string

    rentals = _get_rentals(status, page, per_page)

    # ringkasan metrics untuk widget (sederhana)
    today = date.today()
    # pickups_today: count where pickup_date is today
    pickups_today = Rental.query.filter(
        db.func.date(Rental.pickup_date) == today
    ).count()
    # returns_today: count rentals with payment_status == 'Selesai' (example)
    returns_today = Rental.query.filter(Rental.payment_status == 'Selesai').count()
    pending_count = Rental.query.filter(Rental.order_status == 'Ditinjau').count()
    upcoming_end = today + timedelta(days=7)
    upcoming_count = Rental.query.filter(
        db.func.date(Rental.pickup_date) >= today,
        db.func.date(Rental.pickup_date) <= upcoming_end
    ).count()

    return render_template(
        'admin/manage_reservations.html',
        title='Dashboard Staf - Reservasi',
        rentals=rentals,
        is_staff_dashboard=True,   # penting supaya template tahu ini staff
        status_filter=status,
        pickups_today=pickups_today,
        returns_today=returns_today,
        pending_count=pending_count,
        upcoming_count=upcoming_count
    )


# ==========================================================
# 3) VIEW-ONLY INVENTORY for STAFF
# ==========================================================
@staff_bp.route('/items')
@login_required
@staff_required
def view_items():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config.get('ITEMS_PER_PAGE', 12), type=int)
    items = Item.query.order_by(Item.name).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('staff/view_items.html', title='Daftar Barang', items=items)


# ==========================================================
# 4) DAILY REPORT + MONTHLY INCOME FOR STAFF
# ==========================================================
@staff_bp.route('/daily-report')
@login_required
@staff_required
def daily_report():
    """
    Daily + monthly summary for staff.
    """
    now = datetime.utcnow()
    today = now.date()

    # pickups today (by date)
    pickups_today = Rental.query.filter(
        db.func.date(Rental.pickup_date) == today
    ).count()

    # returns_today (example using payment_status 'Selesai')
    returns_today = Rental.query.filter(Rental.payment_status == 'Selesai').count()

    pending_count = Rental.query.filter(Rental.order_status == 'Ditinjau').count()

    upcoming_end = today + timedelta(days=7)
    upcoming_count = Rental.query.filter(
        db.func.date(Rental.pickup_date) >= today,
        db.func.date(Rental.pickup_date) <= upcoming_end
    ).count()

    # income today
    income_today_q = db.session.query(db.func.coalesce(db.func.sum(Rental.total_price), 0)).filter(
        db.func.date(Rental.pickup_date) == today
    ).scalar()
    income_today = float(income_today_q or 0)

    # income month
    first_of_month = today.replace(day=1)
    next_month_first = (first_of_month + timedelta(days=32)).replace(day=1)
    income_month_q = db.session.query(db.func.coalesce(db.func.sum(Rental.total_price), 0)).filter(
        db.func.date(Rental.pickup_date) >= first_of_month,
        db.func.date(Rental.pickup_date) < next_month_first
    ).scalar()
    income_month = float(income_month_q or 0)

    recent_rentals_today = Rental.query.filter(
        db.func.date(Rental.pickup_date) == today
    ).order_by(Rental.created_at.desc()).limit(8).all()

    recent_rentals_all = Rental.query.order_by(Rental.created_at.desc()).limit(8).all()

    return render_template(
        'staff/daily_report.html',
        title='Laporan Harian',
        pickups_today=pickups_today,
        returns_today=returns_today,
        pending_count=pending_count,
        upcoming_count=upcoming_count,
        income_today=income_today,
        income_month=income_month,
        recent_rentals_today=recent_rentals_today,
        recent_rentals_all=recent_rentals_all
    )


# ==========================================================
# 5) EXPORT BULANAN -> CSV (SERVER-SIDE)
#    URL: /staff/export-month-csv?month=12&year=2025
# ==========================================================
@staff_bp.route('/export-month-csv')
@login_required
@staff_required
def export_month_csv():
    """
    Export CSV for rentals with pickup_date inside requested month.
    Query params:
      - month (1-12) optional
      - year  optional
    """
    # parse params
    try:
        month = int(request.args.get('month')) if request.args.get('month') else None
        year = int(request.args.get('year')) if request.args.get('year') else None
    except ValueError:
        return ("Invalid month/year", 400)

    now = datetime.utcnow().date()
    if not month or not year:
        month = now.month
        year = now.year

    first_of_month = date(year, month, 1)
    next_month_first = (first_of_month + timedelta(days=32)).replace(day=1)

    rentals_q = Rental.query.filter(
        Rental.pickup_date >= datetime.combine(first_of_month, datetime.min.time()),
        Rental.pickup_date < datetime.combine(next_month_first, datetime.min.time())
    ).order_by(Rental.pickup_date.asc()).all()

    # prepare CSV in memory
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'borrower_username', 'borrower_email', 'pickup_date', 'total_price'])
    for r in rentals_q:
        borrower = getattr(r, 'borrower', None)
        username = borrower.username if borrower else ''
        email = borrower.email if borrower else ''
        pickup_str = r.pickup_date.isoformat() if r.pickup_date else ''
        total = float(r.total_price or 0)
        cw.writerow([r.id, username, email, pickup_str, "{:.2f}".format(total)])

    output = si.getvalue()
    si.close()

    filename = f"rentals_{year:04d}-{month:02d}.csv"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Content-Type': 'text/csv; charset=utf-8'
    }
    return Response(output, headers=headers)
