import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from core.database import SessionLocal
from sqlalchemy import and_
from services.user_service import get_user_by_email
from core.security import get_password_hash
from core.security import verify_password
from models.models import User
from core.config import settings


OTP_EXPIRY_SECONDS = 120  # Default 2 minutes


def generate_otp() -> str:
    if settings.ENVIRONMENT.lower() == "dev":
        return settings.ADMIN_OTP
    return str(random.randint(100000, 999999))


def store_otp(email: str, db: Session = SessionLocal()) -> str:
    try:
        user = get_user_by_email(db, email)
        if not user:
            raise ValueError("User not found")
        otp = generate_otp()

        user.otp_code = get_password_hash(otp)
        user.otp_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=OTP_EXPIRY_SECONDS
        )
        user.otp_attempts = 0
        db.commit()

        return otp
    finally:
        db.close()


def verify_otp(email: str, otp_code: str, db: Session = SessionLocal()) -> bool:
    user = db.query(User).filter(User.email == email).first()

    if user and user.otp_expiry:
        # Convert to UTC-aware if it's naive
        if user.otp_expiry.tzinfo is None:
            user.otp_expiry = user.otp_expiry.replace(tzinfo=timezone.utc)

    if (
        user
        and user.otp_code
        and user.otp_expiry
        and user.otp_expiry > datetime.now(timezone.utc)
        and verify_password(otp_code, user.otp_code)  # use hash comparison
    ):
        # Optionally clear the OTP fields after use
        user.otp_code = None
        user.otp_expiry = None
        db.commit()
        return True

    return False


def mark_otp_used(email: str, otp_code: str, db: Session = SessionLocal()):
    user = db.query(User).filter(User.email == email).first()

    if user and user.otp_code and verify_password(otp_code, user.otp_code):
        user.otp_code = None
        user.otp_expiry = None
        db.commit()
