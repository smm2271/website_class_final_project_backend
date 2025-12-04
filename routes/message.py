from auth.user_auth import get_current_user
from fastapi import APIRouter, WebSocket
from exts.message_ext import ConnectManager
app = APIRouter()
connect_manager = ConnectManager()


@app.websocket('/online')
async def get_online(websocket: WebSocket, token: str):
    user = get_current_user(token)
    if not user:
        await websocket.close(code=1008)  # 前端要刷新token
        return
    await connect_manager.add_connect(websocket, user)

