import asyncio
import json
import redis.asyncio as redis
from services.ws_service import manager
from core.config import settings

REDIS_CHANNEL = "broadcast_channel"

redis_client = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
)


async def publish_to_redis(message_id: str, data: dict):
    payload = json.dumps({"message_id": message_id, "data": data})
    await redis_client.publish(REDIS_CHANNEL, payload)


async def listen_to_redis():
    while True:
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
            print("🎧 Redis Listener Started")
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        message_id = payload["message_id"]
                        data = payload["data"]
                        await manager.broadcast(message_id, data)
                    except Exception as e:
                        print(f"[Redis Listener] Error handling message: {e}")
        except Exception as e:
            print(f"[Redis Listener] Connection error: {e}")
            await asyncio.sleep(2)  # Backoff before retry


# Create a test method to check Redis connection
async def test_redis_connection():
    try:
        await redis_client.ping()
        print("✅ Redis connection successful")
    except redis.ConnectionError:
        print("❌ Redis connection failed")


# Run the test method
if __name__ == "__main__":
    asyncio.run(test_redis_connection())
