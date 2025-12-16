from fastapi import APIRouter, Depends, HTTPException, status, Security, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Any, List
from jose import JWTError, jwt
from core.config import settings
from core.security import create_access_token
from db.session import get_db
from services import (
    get_user_by_email,
    authenticate_user,
    create_user,
    delete_user,
    get_all_users,
    get_user_default_thread,
)
from schemas import schemas
from utils.email import send_otp_email
from schemas.schemas import VerifyOTP, RequestOTP

# Generate and store OTP directly in the existing session
from auth.otp_store import generate_otp
from core.security import get_password_hash
from datetime import datetime, timedelta, timezone

router = APIRouter()
oauth2_scheme = HTTPBearer()


async def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> schemas.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        token_type = payload.get("token_type")
        if token_type != "jwt":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return schemas.User.model_validate(user)


async def get_current_admin(
    current_user: schemas.User = Security(get_current_user),
) -> schemas.User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


@router.post("/users", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_new_user(
    *,
    db: Session = Depends(get_db),
    user_in: schemas.UserCreate,
    current_admin: schemas.User = Depends(get_current_admin),
) -> Any:
    """
    Create new user (admin only).
    """

    existing_user = get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email alreday registerd",
        )
    user = create_user(db, user_in, created_by_admin=current_admin.id)
    return schemas.User.model_validate(user)


@router.get("/users", response_model=List[schemas.User])
def list_users(
    db: Session = Depends(get_db),
    current_admin: schemas.User = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve users (admin only).
    """
    users = get_all_users(db, skip=skip, limit=limit)
    return [schemas.User.model_validate(user) for user in users]


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_existing_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: schemas.User = Depends(get_current_admin),
) -> Any:
    """
    Delete user (admin only).
    """

    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete admin user"
        )

    success = delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        return {"message": "User deleted successfully"}


@router.post(
    "/request-otp",
    status_code=status.HTTP_200_OK,
)
def request_otp(
    data: RequestOTP,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email does not exist",
        )

    otp = generate_otp()
    user.otp_code = get_password_hash(otp)
    user.otp_expiry = datetime.now(timezone.utc) + timedelta(seconds=120)  # 2 minutes
    user.otp_attempts = 0
    db.commit()

    # Send email asynchronously
    send_otp_email(data.email, otp, background_tasks)
    print(f"your otp is {otp}")
    return {"message": "OTP sent successfully"}


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp_route(data: VerifyOTP, db: Session = Depends(get_db)):

    user = authenticate_user(db, data.email, data.otp)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")

    # Optional: clear OTP again here, if not already cleared inside authenticate_user/verify_otp

    # Fetch default thread
    default_thread = get_user_default_thread(db, user.id)
    if not default_thread:
        raise HTTPException(status_code=500, detail="Default thread not found")

    # Create token with expiry
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "name": user.full_name,
        "is_admin": user.is_admin,
        "default_thread_id": default_thread.id,
    }
