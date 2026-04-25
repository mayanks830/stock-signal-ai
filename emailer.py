import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, GMAIL_RECIPIENT


def send_report_email(pdf_path: str, equities: list[dict], analyses: list[dict]) -> None:
    """Send the watchlist PDF report via Gmail SMTP."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  [!] Gmail not configured (GMAIL_ADDRESS / GMAIL_APP_PASSWORD missing). Skipping email.")
        return

    recipient = GMAIL_RECIPIENT or GMAIL_ADDRESS

    # Build summary for email body
    valid = [s for s in equities if not s.get("error") and s.get("daily_change_pct") is not None]
    buy_signals = [a for a in analyses if a.get("signal") == "BUY"]
    sell_signals = [a for a in analyses if a.get("signal") == "SELL"]

    top_gainer = max(valid, key=lambda x: x["daily_change_pct"]) if valid else None
    top_loser = min(valid, key=lambda x: x["daily_change_pct"]) if valid else None

    gainers = len([s for s in valid if s["daily_change_pct"] > 0])
    losers = len([s for s in valid if s["daily_change_pct"] < 0])

    date_str = datetime.now().strftime("%B %d, %Y")

    body_lines = [
        f"Daily Watchlist Report - {date_str}",
        "",
        f"Stocks analyzed: {len(valid)}",
        f"Gainers/Losers: {gainers}/{losers}",
        f"AI Signals: {len(buy_signals)} BUY, {len(sell_signals)} SELL",
        "",
    ]

    if buy_signals:
        body_lines.append("BUY signals:")
        for s in buy_signals:
            target = f" (target ${s['price_target']:,.2f})" if s.get("price_target") else ""
            body_lines.append(f"  - {s['ticker']} @ ${s.get('current_price', 0):,.2f}{target}")
        body_lines.append("")

    if sell_signals:
        body_lines.append("SELL signals:")
        for s in sell_signals:
            body_lines.append(f"  - {s['ticker']} @ ${s.get('current_price', 0):,.2f}")
        body_lines.append("")

    if top_gainer:
        body_lines.append(f"Top gainer: {top_gainer['ticker']} {top_gainer['daily_change_pct']:+.2f}%")
    if top_loser:
        body_lines.append(f"Top loser: {top_loser['ticker']} {top_loser['daily_change_pct']:+.2f}%")

    body_lines.append("")
    body_lines.append("Full report attached as PDF.")

    body = "\n".join(body_lines)

    # Build email
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = recipient
    msg["Subject"] = f"Watchlist Report - {date_str} | {len(buy_signals)} BUY, {len(sell_signals)} SELL"

    msg.attach(MIMEText(body, "plain"))

    # Attach PDF
    filename = pdf_path.replace("\\", "/").split("/")[-1]
    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {recipient}")
    except Exception as e:
        print(f"[!] Email failed: {e}")
