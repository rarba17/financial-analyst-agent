from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        key = f"{user_id}"
        self.active_connections[key] = websocket

    def disconnect(self, user_id: str):
        key = f"{user_id}"
        if key in self.active_connections:
            del self.active_connections[key]

    async def _safe_disconnect(self, user_id: str):
        try:
            self.disconnect(user_id)
        except Exception as e:
            print(f"Error during disconnection for {user_id}: {e}")


    async def broadcast(self, user_id: str, data):
        key = f"{user_id}"
        if key in self.active_connections:
            connection = self.active_connections[key]
            try:
                if connection.client_state.name == "CONNECTED":
                    await connection.send_json(data)
            except Exception as e:
                print(f"[WebSocket Error] Failed to send to {user_id}: {e}")
                await self._safe_disconnect(user_id)



manager = ConnectionManager()