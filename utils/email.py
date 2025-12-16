import asyncio
from azure.communication.email import EmailClient
import os
from dotenv import load_dotenv
from core.config import settings
from fastapi import BackgroundTasks

load_dotenv()

ACS_CONNECTION_STRING = settings.AZURE_COMMUNICATION_CONNECTION_STRING
# os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING")
AZURE_EMAIL_SENDER = settings.AZURE_EMAIL_SENDER


def send_otp_email_sync(to_email: str, otp: str):
    """Synchronous version for background tasks"""
    if settings.ENVIRONMENT.lower() == "dev":
        print(f"[DEV MODE] OTP for {to_email}: {otp}")
        return

    try:
        client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)

        message = {
            "senderAddress": AZURE_EMAIL_SENDER,
            "recipients": {"to": [{"address": to_email}]},
            "content": {
                "subject": "Your OTP Code",
                "plainText": f"Your OTP is: {otp}. It is valid for 2 minutes.",
            },
        }

        poller = client.begin_send(message)
        result = poller.result()
        print("Email sent successfully:", result)
        print("OTP email sent. Message ID:", result["id"])
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_otp_email(
    to_email: str, otp: str, background_tasks: BackgroundTasks | None = None
):
    """Asynchronous email sending using background tasks"""

    if settings.ENVIRONMENT.lower() == "dev":
        print(f"[DEV MODE] OTP for {to_email}: {otp}")
        return

    if background_tasks:
        # Add to background tasks for non-blocking execution
        background_tasks.add_task(send_otp_email_sync, to_email, otp)
    else:
        # Fallback to synchronous for backward compatibility
        send_otp_email_sync(to_email, otp)
