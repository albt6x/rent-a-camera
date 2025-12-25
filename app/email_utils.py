# app/email_utils.py (FULL REPLACE - ENHANCED)

"""
Centralized & safe email helpers for Rentalkuy.

Goals:
- Satu pintu pengiriman email
- Aman dari lazy-load SQLAlchemy
- Template context stabil
- Fallback HTML & plain-text konsisten
- Siap Gmail SMTP / production
"""

import logging
import traceback
from datetime import datetime, date
from types import SimpleNamespace
from flask import current_app, render_template

_log = logging.getLogger(__name__)


# ==========================================================
# UTIL DASAR
# ==========================================================
def _is_simple(v):
    """Check apakah value adalah tipe data sederhana"""
    return isinstance(v, (str, int, float, bool, type(None), datetime, date))


def _fmt_dt(v):
    """Format datetime/date menjadi string yang aman"""
    if isinstance(v, (datetime, date)):
        try:
            return v.strftime("%d-%m-%Y %H:%M")
        except Exception:
            return str(v)
    return v


# ==========================================================
# BUILD CONTEXT AMAN (ANTI LAZY LOAD)
# ==========================================================
def _build_safe_rental(rental):
    """
    Konversi Rental object menjadi SimpleNamespace yang aman
    Mencegah lazy-load SQLAlchemy di luar application context
    """
    if not rental:
        return None

    data = {
        "id": getattr(rental, "id", None),
        "public_id": getattr(rental, "public_id", None),
        "pickup_date": _fmt_dt(getattr(rental, "pickup_date", None)),
        "created_at": _fmt_dt(getattr(rental, "created_at", None)),
        "updated_at": _fmt_dt(getattr(rental, "updated_at", None)),
        "payment_status": getattr(rental, "payment_status", None),
        "order_status": getattr(rental, "order_status", None),
        "total_price": getattr(rental, "total_price", None),
        "items": [],
    }

    # Safely load items (relationship)
    try:
        for ri in getattr(rental, "items", []) or []:
            item = getattr(ri, "item", None)
            data["items"].append({
                "id": getattr(ri, "id", None),
                "duration_hours": getattr(ri, "duration_hours", None),
                "price_at_checkout": getattr(ri, "price_at_checkout", None),
                "price": getattr(ri, "price", None),
                "item": {
                    "name": getattr(item, "name", None) if item else None,
                    "image_filename": getattr(item, "image_filename", None) if item else None,
                }
            })
    except Exception:
        _log.warning("Gagal membaca rental.items (lazy-load).")

    return SimpleNamespace(**data)


def _build_safe_person(person):
    """
    Konversi User object menjadi SimpleNamespace yang aman
    """
    if not person:
        return None
    return SimpleNamespace(
        username=getattr(person, "username", None),
        email=getattr(person, "email", None),
        phone=getattr(person, "phone", None),
    )


# ==========================================================
# RENDER AMAN
# ==========================================================
def _render_safe(template_name, context):
    """
    Render template dengan error handling
    Return None jika gagal
    """
    try:
        return render_template(template_name, **context)
    except Exception:
        _log.error(
            "Gagal render template %s\n%s",
            template_name,
            traceback.format_exc(),
        )
        return None


# ==========================================================
# GENERIC SENDER (SATU PINTU)
# ==========================================================
def send_template_email(
    *,
    subject,
    recipients,
    template,
    rental=None,
    person=None,
    extra_context=None,
    sender=None,
    force_send=False,
):
    """
    Fungsi generic untuk kirim email dengan template
    
    Args:
        subject: Judul email
        recipients: Email penerima (string atau list)
        template: Path template HTML (misal: 'emails/order_approved.html')
        rental: Object Rental (akan di-convert ke SimpleNamespace)
        person: Object User/Person (akan di-convert ke SimpleNamespace)
        extra_context: Dict context tambahan untuk template
        sender: Email pengirim (opsional)
        force_send: Paksa kirim meskipun PRINT_EMAILS_TO_CONSOLE=True
    
    Returns:
        bool: True jika berhasil, False jika gagal
    """
    if isinstance(recipients, str):
        recipients = [recipients]

    # Build safe context (anti lazy-load)
    safe_rental = _build_safe_rental(rental)
    safe_person = _build_safe_person(person)

    context = {
        "rental": safe_rental,
        "borrower": safe_person,
        "buyer": safe_person,
        "person": safe_person,
        "mail_footer": current_app.config.get(
            "MAIL_FOOTER",
            "Rentalkuy · Jl. Contoh No.1 · 0896-7833-XXXX",
        ),
    }

    # Merge extra context
    if extra_context:
        context.update(extra_context)

    # Render template HTML
    html = _render_safe(template, context)

    # Fallback HTML jika render gagal
    if not html:
        display = getattr(safe_person, "username", None) or "Pengguna"
        rid = getattr(safe_rental, "public_id", None) or getattr(safe_rental, "id", "-")
        html = (
            "<html><body>"
            f"<p>Halo {display},</p>"
            f"<p>Informasi untuk pesanan <strong>#{rid}</strong>.</p>"
            "<p>Silakan cek dashboard untuk detail.</p>"
            f"<p><small>{context['mail_footer']}</small></p>"
            "</body></html>"
        )

    # Plain text version
    rid_display = getattr(safe_rental, "public_id", None) or getattr(safe_rental, "id", "-")
    plain = (
        f"Halo {getattr(safe_person, 'username', 'Pengguna')}\n\n"
        f"Informasi untuk pesanan #{rid_display}\n\n"
        "Silakan cek dashboard untuk detail.\n\n"
        f"{context['mail_footer']}"
    )

    # Kirim via app.send_email
    try:
        return current_app.send_email(
            subject=subject,
            recipients=recipients,
            body=plain,
            html=html,
            sender=sender,
            force_send=force_send,
        )
    except Exception as e:
        _log.error("Gagal mengirim email '%s': %s", subject, str(e), exc_info=True)
        return False


# ==========================================================
# PUBLIC EMAIL HELPERS (EVENT-BASED)
# ==========================================================

def send_order_approved_email(rental, buyer, force_send=False):
    """
    Kirim email saat order disetujui admin
    
    Args:
        rental: Object Rental yang baru di-ACC
        buyer: Object User (penyewa)
        force_send: Paksa kirim meskipun mode console
    """
    if not buyer or not getattr(buyer, "email", None):
        _log.warning("send_order_approved_email: buyer atau email tidak valid")
        return False

    rid = getattr(rental, "public_id", None) or getattr(rental, "id", "-")
    
    return send_template_email(
        subject=f"[Rentalkuy] Pesanan #{rid} Disetujui",
        recipients=buyer.email,
        template="emails/order_approved.html",
        rental=rental,
        person=buyer,
        extra_context={
            "dashboard_url": current_app.config.get("APP_URL", "/booking/history"),
        },
        force_send=force_send,
    )


def send_order_rejected_email(rental, borrower, reason=None, force_send=False):
    """
    Kirim email saat order ditolak admin
    
    Args:
        rental: Object Rental yang ditolak
        borrower: Object User (penyewa)
        reason: Alasan penolakan (opsional)
        force_send: Paksa kirim
    """
    if not borrower or not getattr(borrower, "email", None):
        _log.warning("send_order_rejected_email: borrower atau email tidak valid")
        return False

    rid = getattr(rental, "public_id", None) or getattr(rental, "id", "-")
    
    return send_template_email(
        subject=f"[Rentalkuy] Pesanan #{rid} Ditolak",
        recipients=borrower.email,
        template="emails/order_rejected.html",
        rental=rental,
        person=borrower,
        extra_context={
            "reason": reason or "Maaf, pesanan Anda tidak dapat diproses saat ini."
        },
        force_send=force_send,
    )


def send_payment_confirmed_email(rental, borrower, force_send=False):
    """
    Kirim email saat pembayaran dikonfirmasi admin
    
    Args:
        rental: Object Rental dengan pembayaran tervalidasi
        borrower: Object User (penyewa)
        force_send: Paksa kirim
    """
    if not borrower or not getattr(borrower, "email", None):
        _log.warning("send_payment_confirmed_email: borrower atau email tidak valid")
        return False

    rid = getattr(rental, "public_id", None) or getattr(rental, "id", "-")
    
    return send_template_email(
        subject=f"[Rentalkuy] Pembayaran Terkonfirmasi - #{rid}",
        recipients=borrower.email,
        template="emails/payment_confirmed.html",
        rental=rental,
        person=borrower,
        extra_context={
            "pickup_info": "Barang siap diambil. Silakan datang sesuai jadwal pickup."
        },
        force_send=force_send,
    )


def send_reservation_completed_email(rental, borrower, force_send=False):
    """
    Kirim email saat reservasi selesai (barang dikembalikan)
    
    Args:
        rental: Object Rental yang sudah selesai
        borrower: Object User (penyewa)
        force_send: Paksa kirim
    """
    if not borrower or not getattr(borrower, "email", None):
        _log.warning("send_reservation_completed_email: borrower atau email tidak valid")
        return False

    rid = getattr(rental, "public_id", None) or getattr(rental, "id", "-")
    
    return send_template_email(
        subject=f"[Rentalkuy] Reservasi #{rid} Selesai",
        recipients=borrower.email,
        template="emails/reservation_completed.html",
        rental=rental,
        person=borrower,
        extra_context={
            "thank_you_message": "Terima kasih telah menggunakan layanan Rentalkuy!"
        },
        force_send=force_send,
    )