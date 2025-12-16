import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from core.config import settings
from api.v1 import auth, chat, share
from db.session import check_database_connection
from services.redis_service import listen_to_redis, publish_to_redis
from services.user_service import create_initial_admin
from services.ws_service import manager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_database_connection()
    create_initial_admin()

    global redis_task
    redis_task = asyncio.create_task(listen_to_redis())
    print("🚀 Redis Listener running")

    yield

    print("🔻 Shutting down Redis listener")
    redis_task.cancel()
    try:
        await redis_task
    except asyncio.CancelledError:
        print("🛑 Redis listener cancelled")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(share.router, prefix=f"{settings.API_V1_STR}/share", tags=["share"])


@app.websocket("/ws/interactions/{message_id}")
async def websocket_endpoint(websocket: WebSocket, message_id: str):
    await manager.connect(websocket, message_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Publish received message to Redis so all workers broadcast it
            await publish_to_redis(message_id, {"text": data})
    except WebSocketDisconnect:
        print(f"[WS] User {message_id} disconnected")
        # manager.disconnect(message_id, websocket)
    except Exception as e:
        print(f"[WS] Error in interaction WebSocket: {e}")
        # manager.disconnect(message_id, websocket)


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=settings.PORT, workers=settings.WORKERS
    )
