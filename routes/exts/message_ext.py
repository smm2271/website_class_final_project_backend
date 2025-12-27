import asyncio
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

    ROOM_NOT_EXISTS = {"error": "room not exists"}
    
    async def add_connect(self, websocket: WebSocket, user: User):
        """
        主連線進入點，負責分派不同的 action_type 到對應的處理器
        """
        await websocket.accept()
        # 初始化連線邏輯現在也封裝在內部
        await self._initialize_connections(websocket, user)

        handlers = {
            "send_message": self._handle_send_message,
            "get_message": self._handle_get_message,
            "mark_room_read": self._handle_mark_room_read,
            "join_room": self._handle_join_room,
            "leave_room": self._handle_leave_room
        }

        try:
            while True:
                data: dict = await websocket.receive_json()
                action_type = data.get("action_type")
                
                if action_type == "disconnect":
                    break
                
                handler = handlers.get(action_type)
                if handler:
                    # 統一使用 await 調用，架構非常整潔
                    await handler(websocket, user, data)
                else:
                    print(f"Unknown action type: {action_type}")

        except WebSocketDisconnect:
            pass
        finally:
            self.disconnect(websocket)

    async def _initialize_connections(self, websocket: WebSocket, user: User):
        """初始化使用者所屬聊天室的連線管理"""
        def get_rooms():
            with get_session_context() as session:
                return ChatRoomService(session).get_chat_rooms_by_user(user)
        
        rooms = await asyncio.to_thread(get_rooms)  # 使用 to_thread 避免阻塞
        for room in rooms:
            self.connections.setdefault(room.id, []).append(websocket)

    async def _handle_send_message(self, websocket: WebSocket, user: User, data: dict):
        """處理發送訊息"""
        room_id = UUID(data["chatroom_id"])
        content = data["content"]
        
        def process_db():
            with get_session_context() as session:
                chat_service = ChatRoomService(session)
                message_service = MessageService(session)
                room = chat_service.get_chat_room_by_id(room_id)
                if not room:
                    return None
                new_msg = message_service.create_message(user, room, content)
                author = get_user_by_id(session, new_msg.author_id)
                return new_msg, author

        result = await asyncio.to_thread(process_db)
        if not result:
            await websocket.send_json(self.ROOM_NOT_EXISTS)
            return

        new_message, author = result
        response_payload = {
            "type": "message_list",
            "chatroom_id": str(room_id),
            "messages": [{
                "id": str(new_message.id),
                "author_name": author.username if author else "Unknown",
                "content": new_message.content,
                "created_at": str(new_message.created_at),
                "is_read": True
            }]
        }

        for ws in self.connections.get(room_id, []):
            await ws.send_json(response_payload)

    async def _handle_get_message(self, websocket: WebSocket, user: User, data: dict):
        """處理獲取歷史訊息"""
        room_id = UUID(data["chatroom_id"])
        limit = data.get("limit", 50)
        before = data.get("before_created_at")

        def fetch_msgs():
            with get_session_context() as session:
                chat_service = ChatRoomService(session)
                if not chat_service.get_chat_room_by_id(room_id):
                    return None
                return MessageService(session).get_messages_by_room(
                    room_id=room_id, user_id=user.id, limit=limit, before_created_at=before
                )

        messages = await asyncio.to_thread(fetch_msgs)
        if messages is None:
            await websocket.send_json(self.ROOM_NOT_EXISTS)
            return

        await websocket.send_json({
            "type": "message_list",
            "chatroom_id": str(room_id),
            "messages": [{"id": str(m.id), "author_name": m.author_name, "content": m.content, 
                          "created_at": str(m.created_at), "is_read": m.is_read} for m in messages]
        })

    async def _handle_mark_room_read(self, _websocket: WebSocket, user: User, data: dict):
        """處理標記聊天室為已讀"""
        room_id = UUID(data["chatroom_id"])
        def do_mark():
            with get_session_context() as session:
                MessageService(session).mark_room_as_read(user.id, room_id)
        
        await asyncio.to_thread(do_mark)

    async def _handle_join_room(self, websocket: WebSocket, user: User, data: dict):
        """處理加入新聊天室"""
        try:
            room_id = UUID(data["chatroom_id"])
        except (ValueError, KeyError):
            await websocket.send_json({"error": "invalid room id"})
            return

        def do_join():
            with get_session_context() as session:
                chat_service = ChatRoomService(session)
                room = chat_service.get_chat_room_by_id(room_id)
                if not room: return False
                if user not in room.members:
                    chat_service.add_user_to_chat_room(user, room)
                return True

        if await asyncio.to_thread(do_join):
            self.connections.setdefault(room_id, []).append(websocket)
        else:
            await websocket.send_json(self.ROOM_NOT_EXISTS)

    async def _handle_leave_room(self, websocket: WebSocket, user: User, data: dict):
        """處理離開聊天室"""
        room_id = UUID(data["chatroom_id"])
        if room_id in self.connections and websocket in self.connections[room_id]:
            self.connections[room_id].remove(websocket)
            if not self.connections[room_id]: self.connections.pop(room_id)

        def do_leave():
            with get_session_context() as session:
                chat_service = ChatRoomService(session)
                room = chat_service.get_chat_room_by_id(room_id)
                if room: chat_service.remove_user_from_chat_room(user, room)

        await asyncio.to_thread(do_leave)

    def disconnect(self, websocket: WebSocket):
        """清理連線"""
        rooms_to_cleanup = [rid for rid, ws_list in self.connections.items() if websocket in ws_list]
        for rid in rooms_to_cleanup:
            self.connections[rid].remove(websocket)
            if not self.connections[rid]: self.connections.pop(rid, None)