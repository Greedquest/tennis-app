"""Email notification via Gmail SMTP (Red-Mail)."""

import html
import logging

import polars as pl
from redmail import gmail

from tennis_app.config import APP_PASSWORD, EMAIL_FROM, EMAIL_TO


def configure_gmail() -> None:
    """Set Gmail credentials on the module-level client (idempotent)."""
    if EMAIL_FROM and APP_PASSWORD:
        gmail.username = EMAIL_FROM
        gmail.password = APP_PASSWORD


def _dataframe_to_html(df: pl.DataFrame) -> str:
    """Render a Polars DataFrame as an HTML table string (no pyarrow needed)."""
    rows = df.to_dicts()
    cols = df.columns

    parts = ['<table border="1" cellpadding="4" cellspacing="0">']
    parts.append("<thead><tr>")
    for c in cols:
        parts.append(f"<th>{html.escape(c)}</th>")
    parts.append("</tr></thead><tbody>")

    for row in rows:
        parts.append("<tr>")
        for c in cols:
            val = row[c]
            cell = html.escape(str(val)) if val is not None else ""
            parts.append(f"<td>{cell}</td>")
        parts.append("</tr>")

    parts.append("</tbody></table>")
    return "\n".join(parts)


def send_email(subject: str, changed_rows: pl.DataFrame) -> None:
    """
    Send an HTML email listing tennis slots that just opened up.

    Args:
        subject: Email subject line
        changed_rows: Polars DataFrame of slots that transitioned booked -> free
    """
    if not EMAIL_FROM or not EMAIL_TO:
        raise RuntimeError("EMAIL_FROM/EMAIL_TO not configured")

    if not APP_PASSWORD:
        raise RuntimeError("APP_PASSWORD not configured")

    if changed_rows.is_empty():
        raise ValueError("changed_rows cannot be empty")

    configure_gmail()

    display_columns = ["Date", "Time", "Venue", "Spaces", "URL"]
    present = [c for c in display_columns if c in changed_rows.columns]
    table_html = _dataframe_to_html(changed_rows.select(present))

    n = len(changed_rows)
    body = f"""
    <h2>🎾 A Wednesday evening court just opened up</h2>
    <p>{n} slot{"s" if n != 1 else ""} moved from booked to free — book quickly:</p>
    {table_html}
    <p style="color:#666;font-size:12px">Alert only — book manually via the link.</p>
    """

    gmail.send(
        sender=EMAIL_FROM,
        receivers=[EMAIL_TO],
        subject=subject,
        html=body,
    )
    logging.info("Email sent successfully via SMTP")
