import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .auth_api.main import AuthAPI
from Database.users import UsersCache
from .user_api.main import UserAPI
from Database.users_profile import UsersProfileCache
from Database.relationships import RelationshipsCache
from .conversation_api.main import ConversationsAPI
from Database.conversations import ConversationsCache
from .media_api.main import MediaAPI
from Database.media import MediaDatabase
from Websocket.websocket_routes import WebsocketRoutes
from Websocket.websocket_manager import sio
from Database.pool import pool, get_cursor

fastapi_app = FastAPI()
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sprava.top", "https://app.sprava.top", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.db_pool = pool
fastapi_app.get_cursor = get_cursor

fastapi_app.users_cache = UsersCache(fastapi_app).init_table()
fastapi_app.users_profile_cache = UsersProfileCache(fastapi_app).init_table()
fastapi_app.relationships_cache = RelationshipsCache(fastapi_app).init_table()
fastapi_app.conversations_cache = ConversationsCache(fastapi_app).init_table()
fastapi_app.medias = MediaDatabase(fastapi_app).init_table()


AuthAPI(fastapi_app)
UserAPI(fastapi_app)
ConversationsAPI(fastapi_app)
MediaAPI(fastapi_app)
websocket_routes = WebsocketRoutes(fastapi_app)
fastapi_app.websocket_manager = websocket_routes.manager

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
