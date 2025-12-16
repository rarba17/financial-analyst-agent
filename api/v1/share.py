from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Any

from db.session import get_db
from services import (
    create_share,
    get_thread,
    fetch_share,
    get_share,
    create_thread,
    create_bulk_thread_messages
)
from schemas import schemas
from api.v1.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.Share)
def create_new_share(
    *,
    db: Session = Depends(get_db),
    thread_in: schemas.ShareCreate,
    current_user: schemas.User = Depends(get_current_user)
) -> Any:
    thread = get_thread(db, thread_in.thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )
    if thread.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    share = create_share(db, thread_in, current_user.id)
    return share    

@router.get("/{share_uid}/messages", response_model=List[schemas.Message])
def fetch_share_messages(
    share_uid: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
) -> Any:
    share = get_share(db, share_uid)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )
    messages = fetch_share(db, share)
    return messages

@router.get("/{share_uid}/continue", response_model=schemas.Thread)
def fetch_share_messages(
    share_uid: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
) -> Any:
    share = get_share(db, share_uid)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )
    messages = fetch_share(db, share)
    thread_data = schemas.ThreadCreate(title=f"continue_{share.uid}")
    
    thread = create_thread(db, thread_data, current_user.id)
    create_bulk_thread_messages(db, thread.id, messages)
    return thread