import socketio


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=20,
)


class ConnectionManager:
    def __init__(self):
        self.sio = sio
        # user_id -> set of sid (kept for is_user_online / get_online_users only)
        self.user_connections = {}
        # sid -> user_id
        self.sid_to_user = {}

    def register(self, sid, user_id):
        self.sid_to_user[sid] = user_id
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(sid)
        # Join a per-user room so emit_to_user can delegate to socket.io
        self.sio.enter_room(sid, f"user_{user_id}")

    def unregister(self, sid):
        user_id = self.sid_to_user.pop(sid, None)
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(sid)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        # socket.io removes the sid from all rooms automatically on disconnect
        return user_id

    def get_user_id(self, sid):
        return self.sid_to_user.get(sid)

    async def emit_to_user(self, user_id: int, event: str, data: dict):
        await self.sio.emit(event, data, room=f"user_{user_id}")

    async def emit_to_multiple(self, user_ids: list, event: str, data: dict, exclude_user_id: int = None):
        for user_id in user_ids:
            if exclude_user_id and user_id == exclude_user_id:
                continue
            await self.emit_to_user(user_id, event, data)

    async def emit_to_conversation(self, event: str, data: dict, user1_id: int, user2_id: int):
        await self.emit_to_user(user1_id, event, data)
        await self.emit_to_user(user2_id, event, data)

    def is_user_online(self, user_id: int):
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0

    def get_online_users(self):
        return list(self.user_connections.keys())
