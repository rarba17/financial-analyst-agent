import logging

from services.redis_service import publish_to_redis

logger = logging.getLogger(__name__)


class ChatStatusService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def send_status(self, message_id, status):
        data = {"chat_status": status}
        logger.debug(f"Sending status: {status} on {message_id}")
        print(f"Sending status: {status} on {message_id}")
        # await manager.broadcast(message_id, data)
        await publish_to_redis(message_id, data)
        print(f"Status sent: {status} on {message_id}")

    async def send_response(self, message_id, response):
        data = {"full_response": response}
        logger.debug(f"Sending full response on {message_id}: {response}")
        print(f"Sending full response on {message_id}: {response}")
        # await manager.broadcast(message_id, data)
        await publish_to_redis(message_id, data)
        print(f"Full response sent on {message_id}: {response}")

    async def stream_response(self, message_id, chunk):
        data = {"message_chunk": chunk}
        await publish_to_redis(message_id, data)


chat_status_service = ChatStatusService()
