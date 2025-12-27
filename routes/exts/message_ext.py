from fastapi import WebSocket, WebSocketDisconnect
from database.models import ChatRoom, User
from typing import Dict, List
from uuid import UUID
from database.service import (
    create_message, mark_message_as_read, get_message_by_id,
    add_user_to_chat_room, remove_user_from_chat_room,
    get_chat_room_by_id, get_chat_rooms_by_user
)
from database.database import get_session


class ConnectManager:
    def __init__(self):
        self.connections: Dict[UUID, List[WebSocket]] = {}

    async def add_connect(self, websocket: WebSocket, user: User):
        await websocket.accept()
        with get_session() as session:
            rooms = get_chat_rooms_by_user(session, user)

        for room in rooms:
            room_id = room.id
            if room_id not in self.connections:
                self.connections[room_id] = []
            self.connections[room_id].append(websocket)
            await self.broadcast(room_id, {
                "type": "presence",
                "status": "online",
                "user_id": str(user.id),
                "username": user.username
            })

        try:
            while True:
                data: dict = await websocket.receive_json()
                action_type = data.get("action_type")

                if action_type == "send_message":
                    await self._handle_send_message(websocket, user, data)
                elif action_type == "mark_read":
                    await self._handle_mark_read(user, data)
                elif action_type == "join_room":
                    await self._handle_join_room(websocket, user, data)
                elif action_type == "leave_room":
                    await self._handle_leave_room(websocket, user, data)
                elif action_type == "disconnect":
                    await self.disconnect(websocket, user, rooms)
                    break
                else:
                    print(f"Received unknown action type: {action_type}")

        except WebSocketDisconnect:
            await self.disconnect(websocket, user, rooms)

    async def _handle_send_message(self, websocket: WebSocket, user: User, data: dict):
        room_id = UUID(data.get("chatroom_id"))
        content = data.get("content")
        with get_session() as session:
            room = get_chat_room_by_id(session, room_id)
            if not room:
                await websocket.send_json({"error": "room not exists"})
                return
            message = create_message(session=session, user=user, chat_room=room, content=content)

        await self.broadcast(room.id, {
            "message_id": str(message.id),
            "user_id": str(user.id),
            "chatroom_id": str(room.id),
            "content": message.content,
            "timestamp": str(message.created_at)
        })

    async def _handle_mark_read(self, user: User, data: dict):
        message_id = UUID(data.get("message_id"))
        with get_session() as session:
            message = get_message_by_id(session, message_id)
            if message:
                mark_message_as_read(session, user, message)

    async def _handle_join_room(self, websocket: WebSocket, user: User, data: dict):
        room_id = UUID(data.get("chatroom_id"))
        with get_session() as session:
            room = get_chat_room_by_id(session, room_id)
            if not room:
                await websocket.send_json({"error": "room not exists"})
                return
            add_user_to_chat_room(session, user, room)

        if room_id not in self.connections:
            self.connections[room_id] = []
        self.connections[room_id].append(websocket)

        await self.broadcast(room_id, {
            "type": "system",
            "message": f"User {user.username} has joined the room."
        })

    async def _handle_leave_room(self, websocket: WebSocket, user: User, data: dict):
        room_id = UUID(data.get("chatroom_id"))
        if room_id in self.connections and websocket in self.connections[room_id]:
            self.connections[room_id].remove(websocket)
            if not self.connections[room_id]:
                del self.connections[room_id]

        with get_session() as session:
            room = get_chat_room_by_id(session, room_id)
            if room:
                remove_user_from_chat_room(session, user, room)

        await self.broadcast(room_id, {
            "type": "system",
            "message": f"User {user.username} has left the room."
        })

    async def disconnect(self, websocket: WebSocket, user: User, rooms: list[ChatRoom]):
        for room in rooms:
            room_id = room.id
            if room_id in self.connections and websocket in self.connections[room_id]:
                self.connections[room_id].remove(websocket)
                if not self.connections[room_id]:
                    del self.connections[room_id]

                await self.broadcast(room_id, {
                    "type": "presence",
                    "status": "offline",
                    "user_id": str(user.id),
                    "username": user.username
                })

    async def broadcast(self, room_id: UUID, message: dict):
        websockets = self.connections.get(room_id, [])
        for websocket in websockets:
            await websocket.send_json(message)

    async def send_message_to_room(self, user: User, context: str, room: ChatRoom):
        with get_session() as session:
            message = create_message(
                session=session, user=user, chat_room=room, content=context)

        await self.broadcast(room.id, {
            "message_id": str(message.id),
            "user_id": str(user.id),
            "chatroom_id": str(room.id),
            "content": message.content,
            "timestamp": str(message.created_at)
        })
