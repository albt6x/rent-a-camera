# app/email_utils.py
from flask import current_app, render_template

def send_order_approved_email(rental, buyer):
    """
    Simple convenience wrapper to send order approved email.
    Expects rental (Rental model) and buyer (User model).
    """
    subject = f"[Rentalkuy] Pesanan #{rental.id} Telah Disetujui"
    # render both text and html (if you create template)
    try:
        html = render_template("emails/order_approved.html", rental=rental, buyer=buyer)
    except Exception:
        html = None
    # simple plain text fallback
    body_lines = [
        f"Halo {buyer.username if buyer else ''},",
        "",
        f"Pesanan Anda (Order ID: {rental.id}) telah disetujui oleh admin.",
        "",
        "Terima kasih,\nRentalkuy Team"
    ]
    body = "\n".join(body_lines)
    # use app-level send_email
    try:
        return current_app.send_email(subject, [buyer.email], body, html=html)
    except Exception:
        current_app.logger.exception("send_order_approved_email failed for rental %s", getattr(rental, "id", None))
        return False
