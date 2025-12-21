# app/email_utils.py  (FULL REPLACE)

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
    return isinstance(v, (str, int, float, bool, type(None), datetime, date))


def _fmt_dt(v):
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

    try:
        for ri in getattr(rental, "items", []) or []:
            item = getattr(ri, "item", None)
            data["items"].append({
                "id": getattr(ri, "id", None),
                "duration_hours": getattr(ri, "duration_hours", None),
                "price_at_checkout": getattr(ri, "price_at_checkout", None),
                "price": getattr(ri, "price", None),
                "item": {
                    "name": getattr(item, "name", None) if item else None
                }
            })
    except Exception:
        _log.warning("Gagal membaca rental.items (lazy-load).")

    return SimpleNamespace(**data)


def _build_safe_person(person):
    if not person:
        return None
    return SimpleNamespace(
        username=getattr(person, "username", None),
        email=getattr(person, "email", None),
    )


# ==========================================================
# RENDER AMAN
# ==========================================================
def _render_safe(template_name, context):
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
    if isinstance(recipients, str):
        recipients = [recipients]

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

    if extra_context:
        context.update(extra_context)

    html = _render_safe(template, context)

    # fallback HTML
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

    plain = (
        f"Halo {getattr(safe_person, 'username', 'Pengguna')}\n\n"
        f"Informasi untuk pesanan #{getattr(safe_rental, 'id', '-')}\n\n"
        "Silakan cek dashboard untuk detail.\n\n"
        f"{context['mail_footer']}"
    )

    try:
        return current_app.send_email(
            subject=subject,
            recipients=recipients,
            body=plain,
            html=html,
            sender=sender,
            force_send=force_send,
        )
    except Exception:
        _log.error("Gagal mengirim email %s", subject, exc_info=True)
        return False


# ==========================================================
# PUBLIC EMAIL HELPERS (EVENT-BASED)
# ==========================================================
def send_order_approved_email(rental, buyer, force_send=False):
    if not buyer or not getattr(buyer, "email", None):
        return False

    return send_template_email(
        subject=f"[Rentalkuy] Pesanan #{getattr(rental, 'id', '-') } Disetujui",
        recipients=buyer.email,
        template="emails/order_approved.html",
        rental=rental,
        person=buyer,
        extra_context={
            "dashboard_url": current_app.config.get("APP_URL"),
        },
        force_send=force_send,
    )


def send_order_rejected_email(rental, borrower, reason=None, force_send=False):
    if not borrower or not getattr(borrower, "email", None):
        return False

    return send_template_email(
        subject=f"[Rentalkuy] Pesanan #{getattr(rental, 'id', '-') } Ditolak",
        recipients=borrower.email,
        template="emails/order_rejected.html",
        rental=rental,
        person=borrower,
        extra_context={"reason": reason},
        force_send=force_send,
    )


def send_payment_confirmed_email(rental, borrower, force_send=False):
    if not borrower or not getattr(borrower, "email", None):
        return False

    return send_template_email(
        subject=f"[Rentalkuy] Pembayaran Terkonfirmasi - #{getattr(rental, 'id', '-')}",
        recipients=borrower.email,
        template="emails/payment_confirmed.html",
        rental=rental,
        person=borrower,
        force_send=force_send,
    )


def send_reservation_completed_email(rental, borrower, force_send=False):
    if not borrower or not getattr(borrower, "email", None):
        return False

    return send_template_email(
        subject=f"[Rentalkuy] Reservasi #{getattr(rental, 'id', '-') } Selesai",
        recipients=borrower.email,
        template="emails/reservation_completed.html",
        rental=rental,
        person=borrower,
        force_send=force_send,
    )
