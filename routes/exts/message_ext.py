from fastapi import WebSocket, WebSocketDisconnect
from database.models import User
from typing import Dict, List
from uuid import UUID
from database.service import ChatRoomService, MessageService, get_user_by_id
from database.database import get_session_context


class ConnectManager:
    def __init__(self):
        # chatroom_id -> list[WebSocket]
        self.connections: Dict[UUID, List[WebSocket]] = {}

    async def add_connect(self, websocket: WebSocket, user: User):
        await websocket.accept()

        # 使用者目前所在的聊天室（只用來管理連線）
        with get_session_context() as session:
            chat_service = ChatRoomService(session)
            rooms = chat_service.get_chat_rooms_by_user(user)

        for room in rooms:
            connections = self.connections.setdefault(room.id, [])
            if websocket not in connections:
                connections.append(websocket)

        try:
            while True:
                data: dict = await websocket.receive_json()
                action_type = data.get("action_type")
                print(f"Action type: {action_type}, data: {data}")
                # ========================
                # 發送訊息（只通知）
                # ========================
                if action_type == "send_message":
                    room_id = UUID(data["chatroom_id"])
                    content = data["content"]
                    print(
                        f"Received message for room {room_id}: {content}, from user {user.id}")
                    with get_session_context() as session:
                        chat_service = ChatRoomService(session)
                        message_service = MessageService(session)
                        room = chat_service.get_chat_room_by_id(room_id)
                        if not room:
                            await websocket.send_json({"error": "room not exists"})
                            continue
                        new_message = message_service.create_message(
                            user, room, content)
                        author = get_user_by_id(session, new_message.author_id)
                        response_messages = [{
                            "id": str(new_message.id),
                            "author_name": author.username if author else "Unknown",
                            "content": new_message.content,
                            "created_at": str(new_message.created_at),
                            "is_read": True  # sender已讀
                        }]

                    for ws in self.connections.get(room_id, []):
                        await ws.send_json({
                            "type": "message_list",
                            "chatroom_id": str(room_id),
                            "messages": response_messages
                        })

                    continue

                # ========================
                # client 主動拉訊息
                # ========================
                if action_type == "get_message":
                    room_id = UUID(data["chatroom_id"])
                    limit = data.get("limit", 50)
                    before = data.get("before_created_at")

                    room = chat_service.get_chat_room_by_id(room_id)
                    if not room:
                        await websocket.send_json({"error": "room not exists"})
                        continue
                    with get_session_context() as session:
                        message_service = MessageService(session)
                        messages = message_service.get_messages_by_room(
                            room_id=room_id,
                            user_id=user.id,
                            limit=limit,
                            before_created_at=before
                        )
                        # 直接使用 DTO 中的 author_name，避免每則訊息額外查詢作者（N+1）
                        response_messages = []
                        for m in messages:
                            response_messages.append({
                                "id": str(m.id),
                                "author_name": m.author_name,
                                "content": m.content,
                                "created_at": str(m.created_at),
                                "is_read": m.is_read
                            })
                    print(
                        f"Sending {len(messages)} messages to user {user.id} for room {room_id}")
                    await websocket.send_json({
                        "type": "message_list",
                        "chatroom_id": str(room_id),
                        "messages": response_messages
                    })
                    continue

                # ========================
                # 3一次標記聊天室已讀
                # ========================
                if action_type == "mark_room_read":
                    room_id = UUID(data["chatroom_id"])
                    with get_session_context() as session:
                        MessageService(session).mark_room_as_read(
                            user.id, room_id)
                    continue

                # ========================
                # 加入聊天室
                # ========================
                if action_type == "join_room":
                    try:
                        room_id = UUID(data["chatroom_id"])
                    except Exception:
                        await websocket.send_json({"error": "invalid room id"})
                        continue
                    with get_session_context() as session:
                        chat_service = ChatRoomService(session)
                        room = chat_service.get_chat_room_by_id(room_id)
                        if not room:
                            await websocket.send_json({"error": "room not exists"})
                            continue
                        if user in room.members:
                            continue
                        chat_service.add_user_to_chat_room(user, room)

                    connections = self.connections.setdefault(room_id, [])
                    if websocket not in connections:
                        connections.append(websocket)
                    continue

                # ========================
                # 離開聊天室
                # ========================
                if action_type == "leave_room":
                    room_id = UUID(data["chatroom_id"])

                    if room_id in self.connections:
                        if websocket in self.connections[room_id]:
                            self.connections[room_id].remove(websocket)
                        if not self.connections[room_id]:
                            self.connections.pop(room_id)

                    with get_session_context() as session:
                        chat_service = ChatRoomService(session)
                        room = chat_service.get_chat_room_by_id(room_id)
                        if room:
                            chat_service.remove_user_from_chat_room(user, room)
                    continue

                # ========================
                # 主動斷線
                # ========================
                if action_type == "disconnect":
                    break

                print(f"Unknown action type: {action_type}")

        except WebSocketDisconnect:
            pass
        finally:
            self.disconnect(websocket)

    def disconnect(self, websocket: WebSocket):
        for room_id in list(self.connections.keys()):
            if websocket in self.connections[room_id]:
                self.connections[room_id].remove(websocket)
                if not self.connections[room_id]:
                    self.connections.pop(room_id)
