from fastapi import WebSocket, WebSocketDisconnect
from database.models import User
from typing import Dict, List, Any
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
        self._initialize_connections(websocket, user)

        # 定義 action 與處理方法的映射表
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
                    await handler(websocket, user, data)
                else:
                    print(f"Unknown action type: {action_type}")

        except WebSocketDisconnect:
            pass
        finally:
            self.disconnect(websocket)

    def _initialize_connections(self, websocket: WebSocket, user: User):
        """初始化使用者所屬聊天室的連線管理"""
        with get_session_context() as session:
            chat_service = ChatRoomService(session)
            rooms = chat_service.get_chat_rooms_by_user(user)

        for room in rooms:
            connections = self.connections.setdefault(room.id, [])
            if websocket not in connections:
                connections.append(websocket)

    async def _handle_send_message(self, websocket: WebSocket, user: User, data: dict):
        """處理發送訊息"""
        room_id = UUID(data["chatroom_id"])
        content = data["content"]
        
        with get_session_context() as session:
            chat_service = ChatRoomService(session)
            message_service = MessageService(session)
            room = chat_service.get_chat_room_by_id(room_id)
            
            if not room:
                await websocket.send_json(self.ROOM_NOT_EXISTS)
                return

            new_message = message_service.create_message(user, room, content)
            author = get_user_by_id(session, new_message.author_id)
            
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

        # 廣播給該房間內的所有連線
        for ws in self.connections.get(room_id, []):
            await ws.send_json(response_payload)

    async def _handle_get_message(self, websocket: WebSocket, user: User, data: dict):
        """處理獲取歷史訊息"""
        room_id = UUID(data["chatroom_id"])
        limit = data.get("limit", 50)
        before = data.get("before_created_at")

        with get_session_context() as session:
            chat_service = ChatRoomService(session)
            room = chat_service.get_chat_room_by_id(room_id)
            if not room:
                await websocket.send_json(self.ROOM_NOT_EXISTS)
                return

            message_service = MessageService(session)
            messages = message_service.get_messages_by_room(
                room_id=room_id, user_id=user.id, limit=limit, before_created_at=before
            )
            
            response_messages = [{
                "id": str(m.id),
                "author_name": m.author_name,
                "content": m.content,
                "created_at": str(m.created_at),
                "is_read": m.is_read
            } for m in messages]

        await websocket.send_json({
            "type": "message_list",
            "chatroom_id": str(room_id),
            "messages": response_messages
        })

    async def _handle_mark_room_read(self, _websocket: WebSocket, user: User, data: dict):
        """處理標記已讀"""
        room_id = UUID(data["chatroom_id"])
        with get_session_context() as session:
            MessageService(session).mark_room_as_read(user.id, room_id)

    async def _handle_join_room(self, websocket: WebSocket, user: User, data: dict):
        """處理加入新聊天室"""
        try:
            room_id = UUID(data["chatroom_id"])
        except (ValueError, KeyError):
            await websocket.send_json({"error": "invalid room id"})
            return

        with get_session_context() as session:
            chat_service = ChatRoomService(session)
            room = chat_service.get_chat_room_by_id(room_id)
            if not room:
                await websocket.send_json(self.ROOM_NOT_EXISTS)
                return
            
            if user not in room.members:
                chat_service.add_user_to_chat_room(user, room)

        # 更新管理連線
        connections = self.connections.setdefault(room_id, [])
        if websocket not in connections:
            connections.append(websocket)

    async def _handle_leave_room(self, websocket: WebSocket, user: User, data: dict):
        """處理離開聊天室"""
        room_id = UUID(data["chatroom_id"])

        # 移除連線管理
        if room_id in self.connections:
            if websocket in self.connections[room_id]:
                self.connections[room_id].remove(websocket)
            if not self.connections[room_id]:
                self.connections.pop(room_id)

        # 移除資料庫關聯
        with get_session_context() as session:
            chat_service = ChatRoomService(session)
            room = chat_service.get_chat_room_by_id(room_id)
            if room:
                chat_service.remove_user_from_chat_room(user, room)

    def disconnect(self, websocket: WebSocket):
        """清理連線斷開後的資源"""
        rooms_to_cleanup = []
        for room_id, ws_list in self.connections.items():
            if websocket in ws_list:
                ws_list.remove(websocket)
                if not ws_list:
                    rooms_to_cleanup.append(room_id)
        
        for room_id in rooms_to_cleanup:
            self.connections.pop(room_id, None)