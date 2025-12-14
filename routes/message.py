from fastapi import APIRouter, WebSocket, Header, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database.database import get_session
from database.service import add_user_to_chat_room, create_chat_room, get_chat_rooms_by_user
from database.models import ChatRoom
from auth.user_auth import get_current_user
from routes.exts.message_ext import ConnectManager
from pprint import pprint

router = APIRouter()
connect_manager = ConnectManager()


class CreateRoomRequest(BaseModel):
    room_name: str | None = None


class GetRoomsResponse(BaseModel):
    room_ids: dict[str, str]


def _parse_cookie_header(cookie_header: str | None) -> dict:
    if not cookie_header:
        return {}
    parts = [p.strip() for p in cookie_header.split(";") if p.strip()]
    cookies = {}
    for part in parts:
        if "=" in part:
            name, val = part.split("=", 1)
            cookies[name.strip()] = val.strip()
    return cookies


def get_user_from_request(request: Request):
    auth_header = request.headers.get("authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        token = request.cookies.get("access_token")
        if not token:
            cookie_header = request.headers.get("cookie")
            cookies = _parse_cookie_header(cookie_header)
            token = cookies.get("access_token")
    if isinstance(token, str) and token.lower() in ("null", "undefined", ""):
        token = None
    return get_current_user(token)


# ---------- WebSocket ----------
@router.websocket("/online")
async def get_online(websocket: WebSocket, token: str | None = None):
    # token 從 query string 傳入或從 cookie/header 中取得
    # 前端可能會傳入字串 'null' 或 'undefined'，視為未提供 token
    if isinstance(token, str) and token.lower() in ("null", "undefined", ""):
        token = None

    if not token:
        token = websocket.cookies.get("access_token")

        if not token:
            cookie_header = websocket.headers.get("cookie")
            cookies = _parse_cookie_header(cookie_header)
            token = cookies.get("access_token")

        if not token:
            auth_header = websocket.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]

    user = get_current_user(token)
    if not user:
        await websocket.close(code=1008)  # 前端要刷新 token
        return
    await connect_manager.add_connect(websocket, user)


# ---------- HTTP API ----------
@router.post("/create_room")
async def create_room(
    request_data: CreateRoomRequest,
    request: Request,
    session=Depends(get_session)
):
    user = get_user_from_request(request)
    if not user:
        return JSONResponse(content={"error": "User not authenticated"}, status_code=401)

    room = ChatRoom()
    room.name = request_data.room_name if request_data.room_name else f"room_{user.user_id}"
    create_chat_room(session, room)
    add_user_to_chat_room(session, user, room)
    return {"room_id": str(room.id)}


@router.get("/get_rooms")
async def get_rooms(
    request: Request,
    session=Depends(get_session)
):
    # print(request.headers)
    user = get_user_from_request(request)
    if not user:
        return JSONResponse(content={"error": "User not authenticated"}, status_code=401)

    rooms = get_chat_rooms_by_user(session, user)
    room_ids = {str(room.id): room.name for room in rooms}
    return GetRoomsResponse(room_ids=room_ids)
