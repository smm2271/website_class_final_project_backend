from fastapi import WebSocket, WebSocketDisconnect
from database.models import ChatRoom, User
from typing import Dict, List
from uuid import UUID
from database.service import create_message, mark_message_as_read, get_message_by_id, add_user_to_chat_room, remove_user_from_chat_room
from database.database import get_session
from auth.user_auth import get_current_user


class ConnectManager():
    def __init__(self):
        self.connections: Dict[UUID, List[WebSocket]] = {}

    async def add_connect(self, websocket: WebSocket, rooms: list[ChatRoom]):
        await websocket.accept()
        for room in rooms:
            if room.id not in self.connections:
                self.connections[room.id] = []
            self.connections[room.id].append(websocket)
        try:
            while True:
                data: dict = await websocket.receive_json()
                action_type = data.get("action_type")
                token = data.get("token")
                user = get_current_user(token)
                if not user:
                    await websocket.close(code=1008) # 前端要刷新token
                    break
                if action_type == "send_message":
                    room_id = UUID(data.get("chatroom_id"))
                    content = data.get("content")
                    if room_id in self.connections:
                        await self.send_message_to_room(user=user, context=content, room=room_id)
                    continue
                if action_type == "mark_read":
                    message_id = UUID(data.get("message_id"))
                    with get_session() as session:
                        message = get_message_by_id(session, message_id)
                        mark_message_as_read(session, user, message)
                    continue
                if action_type == "join_room":
                    room_id = UUID(data.get("chatroom_id"))
                    if room_id not in self.connections:
                        self.connections[room_id] = []
                    self.connections[room_id].append(websocket)
                    add_user_to_chat_room(get_session(), user, room_id)
                    continue
                if action_type == "leave_room":
                    room_id = UUID(data.get("chatroom_id"))
                    if room_id in self.connections and websocket in self.connections[room_id]:
                        self.connections[room_id].remove(websocket)
                    remove_user_from_chat_room(get_session(), user, room_id)
                    continue
                if action_type == "disconnect":
                    self.disconnect(websocket, rooms)
                    break

        except WebSocketDisconnect:
            self.disconnect(websocket, rooms)

    def disconnect(self, websocket: WebSocket, rooms: list[ChatRoom]):
        for room in rooms:
            if websocket in self.connections[room.id]:
                self.connections[room.id].remove(websocket)
                if len(self.connections[room]) == 0:  # 清理空房間
                    self.connections.pop(room.id)

    async def send_message_to_room(self, user: User, context: str, room: ChatRoom):
        with get_session() as session:
            message = create_message(
                session=session, user=user, chat_room=room, content=context)
        websockets = self.connections.get(room.id, [])
        for websocket in websockets:
            await websocket.send_json({
                "message_id": str(message.id),
                "user_id": str(user.id),
                "chatroom_id": str(room.id),
                "content": message.content,
                "timestamp": str(message.created_at)
            })
