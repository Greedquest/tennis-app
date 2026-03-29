"""Email notification via Gmail SMTP (Red-Mail)."""

import logging

import polars as pl
from redmail import gmail

from tennis_app.config import APP_PASSWORD, EMAIL_FROM, EMAIL_TO


def configure_gmail() -> None:
    """Set Gmail credentials on the module-level client (idempotent)."""
    if EMAIL_FROM and APP_PASSWORD:
        gmail.username = EMAIL_FROM
        gmail.password = APP_PASSWORD


def send_email(subject: str, changed_rows: pl.DataFrame) -> None:
    """
    Send an HTML email with a table of changed tennis court availability.

    Red-Mail renders pandas DataFrames as styled HTML tables, so we convert
    the Polars frame to pandas for the email body.

    Args:
        subject: Email subject line
        changed_rows: Polars DataFrame of rows that have changed
    """
    if not EMAIL_FROM or not EMAIL_TO:
        raise RuntimeError("EMAIL_FROM/EMAIL_TO not configured")

    if not APP_PASSWORD:
        raise RuntimeError("APP_PASSWORD not configured")

    if changed_rows.is_empty():
        raise ValueError("changed_rows cannot be empty")

    configure_gmail()

    display_columns = ["Date", "Time", "Venue", "Spaces", "Venue Size", "URL"]
    df_display = changed_rows.select(display_columns).to_pandas()

    gmail.send(
        sender=EMAIL_FROM,
        receivers=[EMAIL_TO],
        subject=subject,
        html="""
        <h2>Tennis Court Availability Changes</h2>
        <p>{{ num_changes }} availability change(s) detected:</p>
        {{ my_table }}
        """,
        body_tables={"my_table": df_display},
        body_params={"num_changes": len(changed_rows)},
    )
    logging.info("Email sent successfully via SMTP")
