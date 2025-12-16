from sqlalchemy.orm import Session
from models.models import Message
from schemas import schemas
from typing import List, Optional
from services.agent_service import AgentService
from fastapi import BackgroundTasks
from db.session import SessionLocal  # Import to create new session


async def process_message_task(
    user_message_id: int,
    ai_message_id: int,
):
    """
    Background task to process message with agent
    Creates its own database session to avoid conflicts
    """
    # Create a new database session for this background task
    db = SessionLocal()
    
    try:
        user_message = db.query(Message).filter(Message.id == user_message_id).first()
        ai_message = db.query(Message).filter(Message.id == ai_message_id).first()

        if not user_message or not ai_message:
            raise ValueError("User message or AI message not found")

        print(f"[Message Service] Processing message ID: {user_message_id}")
        
        # Initialize agent service
        agent_service = AgentService(str(ai_message.id))

        # Process the message
        response = await agent_service.process_message(user_message)

        print(f"[Message Service] Got response, updating AI message")
        
        # Update AI message with response
        ai_message.content = response
        db.commit()
        db.refresh(ai_message)
        
        print(f"[Message Service] AI message updated successfully")

    except Exception as e:
        db.rollback()
        print(f"[Message Service] Error in process_message_task: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try to update message with error
        try:
            ai_msg = db.query(Message).filter(Message.id == ai_message_id).first()
            if ai_msg:
                ai_msg.content = f"Error processing your request: {str(e)}"
                db.commit()
        except Exception as update_error:
            print(f"[Message Service] Failed to update error message: {update_error}")
    finally:
        db.close()


async def create_conversation_messages(
    db: Session,
    user_message_dto: schemas.MessageCreate,
    user_id: int,
    background_tasks: BackgroundTasks,
):
    """
    Create user and AI messages, then process in background
    """
    # Create user message
    user_message = Message(
        content=user_message_dto.content,
        thread_id=user_message_dto.thread_id,
        user_id=user_id,
        is_bot=False,
    )

    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Create placeholder AI message
    ai_message = Message(
        content="",
        thread_id=user_message_dto.thread_id,
        user_id=user_id,
        is_bot=True,
    )

    db.add(ai_message)
    db.commit()
    db.refresh(ai_message)

    print(f"[Message Service] Created messages - User: {user_message.id}, AI: {ai_message.id}")

    # Add background task - DO NOT pass db session
    background_tasks.add_task(
        process_message_task,
        user_message_id=user_message.id,
        ai_message_id=ai_message.id,
    )

    return user_message, ai_message


def get_thread_messages(db: Session, thread_id: int) -> List[Message]:
    """Get all messages in a thread ordered by creation time"""
    messages = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    return messages


def clear_thread_messages(db: Session, thread_id: int) -> bool:
    """Delete all messages from a thread"""
    try:
        db.query(Message).filter(Message.thread_id == thread_id).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error clearing thread messages: {e}")
        return False


def create_bulk_thread_messages(
    db: Session, thread_id: int, messages: List[Message]
) -> bool:
    """Insert bulk messages into a thread"""
    try:
        new_messages = [
            Message(
                content=msg.content,
                is_bot=msg.is_bot,
                user_id=msg.user_id,
                thread_id=thread_id,
            )
            for msg in messages
        ]

        db.add_all(new_messages)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error creating bulk messages: {e}")
        return False


def update_message_content(
    db: Session, message_id: int, content: str
) -> Optional[Message]:
    """Update the content of a message"""
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if message:
            message.content = content
            db.commit()
            db.refresh(message)
        return message
    except Exception as e:
        db.rollback()
        print(f"Error updating message {message_id}: {str(e)}")
        raise