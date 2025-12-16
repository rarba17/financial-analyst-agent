from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Any

from db.session import get_db
from services import (
    create_thread,
    get_user_threads,
    get_thread,
    get_thread_messages,
    clear_thread_messages,
)
from schemas import schemas
from api.v1.auth import get_current_user
from services.message_service import create_conversation_messages

router = APIRouter()


@router.post("/threads", response_model=schemas.Thread)
def create_new_thread(
    *,
    db: Session = Depends(get_db),
    thread_in: schemas.ThreadCreate,
    current_user: schemas.User = Depends(get_current_user)
) -> Any:
    thread = create_thread(db, thread_in, current_user.id)
    return thread


@router.get("/threads", response_model=List[schemas.Thread])
def get_threads(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Any:
    threads = get_user_threads(db, current_user.id, limit=limit, offset=offset)
    return threads


@router.post("/messages")
async def create_new_message(
    *,
    db: Session = Depends(get_db),
    message_in: schemas.MessageCreate,
    current_user: schemas.User = Depends(get_current_user),
    background_tasks: BackgroundTasks
) -> Any:

    try:
        user_message, ai_message = await create_conversation_messages(
            db=db,
            user_message_dto=message_in,
            user_id=current_user.id,
            background_tasks=background_tasks,
        )

        return {
            "status": 200,
            "success": True,
            "data": [
                {
                    "id": user_message.id,
                    "content": user_message.content,
                    "thread_id": user_message.thread_id,
                    "is_bot": False,
                },
                {
                    "id": ai_message.id,
                    "content": ai_message.content,
                    "thread_id": ai_message.thread_id,
                    "is_bot": True,
                },
            ],
        }

    except Exception as e:
        raise e


@router.get("/threads/{thread_id}/messages", response_model=List[schemas.Message])
def get_messages(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
) -> Any:
    thread = get_thread(db, thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    if thread.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    messages = get_thread_messages(db, thread_id)
    return messages


@router.delete("/threads/{thread_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_messages(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
) -> None:
    thread = get_thread(db, thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    if thread.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    success = clear_thread_messages(db, thread_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear messages",
        )
