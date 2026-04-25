from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, DISCORD_WEBHOOK_URL

router = APIRouter()

TOPIC_LABELS = {
    'general': 'General Inquiry',
    'feature': 'Feature Request',
    'bug': 'Bug Report',
    'partnership': 'Partnership / Business',
    'support': 'Account Support',
}


class ContactForm(BaseModel):
    name: str
    email: str
    topic: str = "general"
    message: str


@router.post("/contact")
async def submit_contact(form: ContactForm):
    name = form.name.strip()[:100]
    email = form.email.strip()[:200]
    topic = TOPIC_LABELS.get(form.topic, form.topic)
    message = form.message.strip()[:2000]

    if not name or not email or not message:
        return JSONResponse({"error": "All fields required"}, status_code=400)

    sent = False

    # Always send to Discord if configured (fast, reliable)
    if DISCORD_WEBHOOK_URL:
        try:
            _send_discord(name, email, topic, message)
            sent = True
        except Exception as e:
            print(f"[Contact] Discord failed: {e}")

    # Also send email if configured
    if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
        try:
            _send_email(name, email, topic, message)
            sent = True
        except Exception as e:
            print(f"[Contact] Email failed: {e}")

    if not sent:
        print(f"[Contact] Logged only — From: {name} <{email}> [{topic}]\n{message}")

    return {"status": "sent"}


def _send_discord(name: str, email: str, topic: str, message: str):
    from utils import fetch_with_retry
    embed = {
        "title": f"Contact: {topic}",
        "color": 0x3B82F6,
        "fields": [
            {"name": "From", "value": f"{name} ({email})", "inline": False},
            {"name": "Message", "value": message[:1024], "inline": False},
        ],
        "footer": {"text": "Trading Signals Contact Form"},
    }
    fetch_with_retry(DISCORD_WEBHOOK_URL, method="post", timeout=10, json={"embeds": [embed]})
    print(f"[Contact] Discord notification sent for {name}")


def _send_email(name: str, email: str, topic: str, message: str):
    import smtplib
    from email.mime.text import MIMEText

    body = f"Topic: {topic}\nName: {name}\nEmail: {email}\n\n{message}"
    msg = MIMEText(body, "plain")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS
    msg["Subject"] = f"[Trading Signals] {topic} — {name}"
    msg["Reply-To"] = email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"[Contact] Email sent from {name} <{email}>")
    except Exception as e:
        print(f"[Contact] Email failed: {e}")
