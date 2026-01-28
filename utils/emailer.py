import smtplib
from email.message import EmailMessage
from config import config
from utils.logger import get_logger

logger = get_logger("emailer")


def send_error_email(subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = config.ALERT_EMAIL_FROM
    msg["To"] = config.ALERT_EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Sent error email to {config.ALERT_EMAIL_TO}")
    except Exception as e:
        logger.error(f"Failed to send error email: {e}")
