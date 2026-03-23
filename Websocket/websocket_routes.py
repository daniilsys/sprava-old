from Websocket.websocket_manager import ConnectionManager, sio
from Websocket.websocket_handlers import WebSocketHandlers


class WebsocketRoutes:
    def __init__(self, app):
        self.app = app
        self.manager = ConnectionManager()
        self.handlers = WebSocketHandlers(app, self.manager)
        self.setup_events()

    def setup_events(self):
        @sio.event
        async def connect(sid, environ, auth):
            if not auth or "token" not in auth:
                raise ConnectionRefusedError("No token provided")

            token = auth["token"]
            user = self.app.users_cache.get_user_by_token(token)

            if not user:
                raise ConnectionRefusedError("Invalid token")

            user_id = user.user_id
            self.manager.register(sid, user_id)

            await self.handlers.notify_status_change(user_id, "online")

        @sio.event
        async def disconnect(sid):
            user_id = self.manager.unregister(sid)
            if user_id and not self.manager.is_user_online(user_id):
                await self.handlers.notify_status_change(user_id, "offline")

        @sio.event
        async def send_message(sid, data):
            await self.handlers.handle_send_message(sid, data)

        @sio.event
        async def typing(sid, data):
            await self.handlers.handle_typing(sid, data)

        @sio.event
        async def stop_typing(sid, data):
            await self.handlers.handle_stop_typing(sid, data)

        @sio.event
        async def mark_read(sid, data):
            await self.handlers.handle_mark_read(sid, data)

        @sio.event
        async def get_online_friends(sid, data):
            await self.handlers.handle_get_online_friends(sid, data)
