from sqlalchemy.orm import Session
from db.session import SessionLocal
from models.models import User, Thread
from schemas import schemas
from core.security import get_password_hash, verify_password
from core.config import settings
from typing import Optional, List
from datetime import datetime, timedelta, timezone


def create_initial_admin():
    """Create the admin user if it doesn't exist"""
    db = SessionLocal()
    admin = get_user_by_email(db, settings.ADMIN_EMAIL)
    if not admin:
        admin = User(
            email=settings.ADMIN_EMAIL,
            otp_code=get_password_hash(settings.ADMIN_OTP),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        # Create default thread for admin
        default_thread = Thread(title="default", user_id=admin.id)
        db.add(default_thread)
        db.commit()

    db.close()
    return admin


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session, user_in: schemas.UserCreate, created_by_admin: Optional[int] = None
) -> User:
    from auth.otp_store import generate_otp

    otp = generate_otp()
    hashed_otp = get_password_hash(otp)

    new_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        otp_code=hashed_otp,
        otp_expiry=datetime.now(timezone.utc) + timedelta(minutes=2),
        created_by=created_by_admin,  # Or current_admin.id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create default thread for the new user
    default_thread = Thread(title="default", user_id=new_user.id)
    db.add(default_thread)
    db.commit()
    db.refresh(default_thread)

    return new_user


def authenticate_user(db: Session, email: str, otp: str) -> Optional[User]:
    from auth.otp_store import verify_otp

    if not verify_otp(email, otp, db):
        return None

    user = get_user_by_email(db, email)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()
