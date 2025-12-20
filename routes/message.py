from fastapi import APIRouter, WebSocket, Request, Depends, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database.database import get_session
from database.service import add_user_to_chat_room, create_chat_room, get_chat_rooms_by_user
from database.models import ChatRoom
from auth.user_auth import get_current_user
from routes.exts.message_ext import ConnectManager

router = APIRouter()
connect_manager = ConnectManager()


class CreateRoomRequest(BaseModel):
    room_name: str | None = None


class GetRoomsResponse(BaseModel):
    room_ids: dict[str, str]


# ---------------- Helper ----------------
def _parse_cookie_header(cookie_header: str | None) -> dict:
    if not cookie_header:
        return {}
    cookies = {}
    for part in cookie_header.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
    return cookies


def get_user_from_request(request: Request):
    token = None

    # Authorization header
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]

    # Cookie
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        cookie_header = request.headers.get("cookie")
        cookies = _parse_cookie_header(cookie_header)
        token = cookies.get("access_token")

    # 轉換 null / undefined
    if isinstance(token, str) and token.lower() in ("null", "undefined", ""):
        token = None

    return get_current_user(token)


# ---------------- WebSocket ----------------
@router.websocket("/online")
async def websocket_online(websocket: WebSocket, token: str | None = None):
    user = get_current_user(token) if token else None

    # token 從 cookie/header 再試一次
    if not user:
        token = websocket.cookies.get("access_token")
        if not token:
            cookies = _parse_cookie_header(websocket.headers.get("cookie"))
            token = cookies.get("access_token")
        if not token:
            auth_header = websocket.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
        user = get_current_user(token)

    if not user:
        await websocket.close(code=1008)
        return

    await connect_manager.add_connect(websocket, user)


# ---------------- HTTP API ----------------
@router.post("/create_room")
async def create_room(
    request_data: CreateRoomRequest,
    request: Request,
    session=Depends(get_session)
):
    user = get_user_from_request(request)
    if not user:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)

    room_name = request_data.room_name or f"room_{user.user_id}"
    room = ChatRoom(name=room_name)
    create_chat_room(session, room)
    add_user_to_chat_room(session, user, room)

    return {"room_id": str(room.id)}


@router.get("/get_rooms")
async def get_rooms(request: Request, session=Depends(get_session)):
    user = get_user_from_request(request)
    if not user:
        return JSONResponse({"error": "User not authenticated"}, status_code=401)

    rooms = get_chat_rooms_by_user(session, user)
    room_ids = {str(room.id): room.name for room in rooms}
    return GetRoomsResponse(room_ids=room_ids)
