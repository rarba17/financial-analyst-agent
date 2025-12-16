from sqlalchemy.orm import Session
from models.models import Share, Message
from schemas import schemas
from typing import Optional, List
import uuid

from .message_service import (
    get_thread_messages
)

def create_share(db: Session, thread: schemas.ShareCreate, user_id: int) -> Share:
    db_share = Share(uid = uuid.uuid4(), thread_id=thread.thread_id, user_id=user_id)
    db.add(db_share)
    db.commit()
    db.refresh(db_share)
    return db_share

def get_share(db: Session, uid: int) -> Optional[Share]:
    return db.query(Share).filter(Share.uid == uid).first()

def fetch_share(db: Session, share: schemas.Share) -> List[Message]:
    print(share.thread_id)
    return get_thread_messages(db, share.thread_id)