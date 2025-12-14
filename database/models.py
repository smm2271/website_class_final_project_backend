# models.py
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Index, select
from datetime import datetime
from uuid import UUID, uuid4
import pytz


# -----------------------------
# 1. Users 表
# -----------------------------
class User(SQLModel, table=True):
    __tablename__ = "Users"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(max_length=20, unique=True, nullable=False, index=True)
    username: str = Field(max_length=20, nullable=False)
    hash_password: str = Field(max_length=255, nullable=False)
    salt: str = Field(max_length=255, nullable=False)

    # 關係：發送的訊息
    sent_messages: List["Message"] = Relationship(back_populates="author")
    # 關係：加入的聊天室
    chatrooms: List["ChatRoomPivot"] = Relationship(back_populates="user")
    # 關係：已讀的訊息
    read_messages: List["MessageRead"] = Relationship(back_populates="user")


# -----------------------------
# 2. ChatRoomList 表
# -----------------------------
class ChatRoom(SQLModel, table=True):
    __tablename__ = "ChatRoomList"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.utc))
    name: Optional[str] = Field(default=None, max_length=50)

    # 關係：成員
    members: List["ChatRoomPivot"] = Relationship(back_populates="chatroom")
    # 關係：訊息
    messages: List["Message"] = Relationship(back_populates="chatroom")


# -----------------------------
# 3. ChatRoom_pivot 中介表（多對多）
# -----------------------------
class ChatRoomPivot(SQLModel, table=True):
    __tablename__ = "ChatRoom_pivot"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chatroom_id: UUID = Field(foreign_key="ChatRoomList.id", nullable=False)
    user_id: UUID = Field(foreign_key="Users.id", nullable=False)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(pytz.utc))

    # 關係
    chatroom: ChatRoom = Relationship(back_populates="members")
    user: User = Relationship(back_populates="chatrooms")

    # 複合唯一索引：一人只能加入一次
    __table_args__ = (
        Index("uniq_chatroom_user", "chatroom_id", "user_id", unique=True),
    )


# -----------------------------
# 4. Messages 表
# -----------------------------
class Message(SQLModel, table=True):
    __tablename__ = "Messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chatroom_id: UUID = Field(foreign_key="ChatRoomList.id", nullable=False)
    author_id: UUID = Field(foreign_key="Users.id", nullable=False)
    content: str = Field(nullable=False)
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.utc))

    # 關係
    chatroom: ChatRoom = Relationship(back_populates="messages")
    author: User = Relationship(back_populates="sent_messages")
    # 誰讀了這則訊息
    read_by: List["MessageRead"] = Relationship(back_populates="message")

    # 索引優化
    __table_args__ = (
        Index("idx_messages_chatroom_time", "chatroom_id", "created_at"),
        Index("idx_messages_author", "author_id"),
    )


# -----------------------------
# 5. MessageReads 中介表（已讀狀態）
# -----------------------------
class MessageRead(SQLModel, table=True):
    __tablename__ = "MessageReads"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    message_id: UUID = Field(foreign_key="Messages.id", nullable=False)
    user_id: UUID = Field(foreign_key="Users.id", nullable=False)
    read_at: datetime = Field(default_factory=lambda: datetime.now(pytz.utc), nullable=False)

    # 關係
    message: Message = Relationship(back_populates="read_by")
    user: User = Relationship(back_populates="read_messages")

    # 複合唯一：一人一訊息只記一次
    __table_args__ = (
        Index("uniq_message_user_read", "message_id", "user_id", unique=True),
        Index("idx_user_reads_time", "user_id", "read_at"),
        Index("idx_message_reads", "message_id"),
    )
