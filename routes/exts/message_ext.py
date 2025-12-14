from fastapi import WebSocket, WebSocketDisconnect
from database.models import ChatRoom, User
from typing import Dict, List
from uuid import UUID
from database.service import create_message, mark_message_as_read, get_message_by_id, add_user_to_chat_room, remove_user_from_chat_room, get_chat_room_by_id, get_chat_rooms_by_user
from database.database import get_session
from auth.user_auth import get_current_user


class ConnectManager():
    def __init__(self):
        self.connections: Dict[UUID, List[WebSocket]] = {}

    async def add_connect(self, websocket: WebSocket, user: User):
        """
        Accept a websocket connection for an already authenticated user.
        Subscribe the websocket to all chat rooms the user belongs to.
        Use the authenticated user for subsequent actions (no per-message token required).
        """
        await websocket.accept()

        with get_session() as session:
            rooms = get_chat_rooms_by_user(session, user)

        for room in rooms:
            if room.id not in self.connections:
                self.connections[room.id] = []
            self.connections[room.id].append(websocket)
        try:
            while True:
                data: dict = await websocket.receive_json()
                action_type = data.get("action_type")
                if action_type == "send_message":
                    room_id = UUID(data.get("chatroom_id"))
                    content = data.get("content")
                    with get_session() as session:
                        room = get_chat_room_by_id(session, room_id)
                        if not room:
                            await websocket.send_json({"error": "room not exists"})
                            continue
                        message = create_message(session=session, user=user, chat_room=room, content=content)
                    websockets = self.connections.get(room.id, [])
                    for ws in websockets:
                        await ws.send_json({
                            "message_id": str(message.id),
                            "user_id": str(user.id),
                            "chatroom_id": str(room.id),
                            "content": message.content,
                            "timestamp": str(message.created_at)
                        })
                    continue
                if action_type == "mark_read":
                    message_id = UUID(data.get("message_id"))
                    with get_session() as session:
                        message = get_message_by_id(session, message_id)
                        if message:
                            mark_message_as_read(session, user, message)
                    continue
                if action_type == "join_room":
                    room_id = UUID(data.get("chatroom_id"))
                    with get_session() as session:
                        room = get_chat_room_by_id(session, room_id)
                        if not room:
                            await websocket.send_json({"error": "room not exists"})
                            continue
                        add_user_to_chat_room(session, user, room)
                    if room_id not in self.connections:
                        self.connections[room_id] = []
                    self.connections[room_id].append(websocket)
                    continue
                if action_type == "leave_room":
                    room_id = UUID(data.get("chatroom_id"))
                    if room_id in self.connections and websocket in self.connections[room_id]:
                        self.connections[room_id].remove(websocket)
                        if len(self.connections[room_id]) == 0:
                            self.connections.pop(room_id)
                    with get_session() as session:
                        room = get_chat_room_by_id(session, room_id)
                        if room:
                            remove_user_from_chat_room(session, user, room)
                    continue
                if action_type == "disconnect":
                    self.disconnect(websocket, rooms)
                    break
                print(f"Received unknown action type: {action_type}")

        except WebSocketDisconnect:
            self.disconnect(websocket, rooms)

    def disconnect(self, websocket: WebSocket, rooms: list[ChatRoom]):
        for room in rooms:
            if websocket in self.connections.get(room.id, []):
                self.connections[room.id].remove(websocket)
                if len(self.connections[room.id]) == 0:  # 清理空房間
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
