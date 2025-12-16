from sqlalchemy.orm import Session
from models.models import Thread, Message
from schemas import schemas
from typing import List, Optional


def create_thread(db: Session, thread_in: schemas.ThreadCreate, user_id: int) -> Thread:
    """Create a new thread for a user"""
    thread = Thread(
        title=thread_in.title,
        user_id=user_id
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def get_user_threads(
    db: Session, 
    user_id: int, 
    limit: int = 20, 
    offset: int = 0
) -> List[Thread]:
    """Get all threads for a user with pagination"""
    return (
        db.query(Thread)
        .filter(Thread.user_id == user_id)
        .order_by(Thread.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_thread(db: Session, thread_id: int) -> Optional[Thread]:
    """Get a specific thread by ID"""
    return db.query(Thread).filter(Thread.id == thread_id).first()


def get_user_default_thread(db: Session, user_id: int) -> Optional[Thread]:
    """Get the default thread for a user"""
    return (
        db.query(Thread)
        .filter(Thread.user_id == user_id, Thread.title == "default")
        .first()
    )


def get_thread_messages(db: Session, thread_id: int) -> List[Message]:
    """Get all messages in a thread"""
    return (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
        .all()
    )


def clear_thread_messages(db: Session, thread_id: int) -> bool:
    """Delete all messages in a thread"""
    try:
        db.query(Message).filter(Message.thread_id == thread_id).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error clearing thread messages: {e}")
        return False


def create_bulk_thread_messages(
    db: Session, 
    thread_id: int, 
    messages: List[schemas.Message]
) -> List[Message]:
    """Create multiple messages in a thread (used for sharing/continuing threads)"""
    new_messages = []
    for msg in messages:
        new_message = Message(
            thread_id=thread_id,
            content=msg.content,
            is_bot=msg.is_bot,
            user_id=msg.user_id
        )
        new_messages.append(new_message)
        db.add(new_message)
    
    db.commit()
    for msg in new_messages:
        db.refresh(msg)
    
    return new_messages