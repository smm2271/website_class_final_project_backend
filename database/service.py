from sqlmodel import select, Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from dataclasses import dataclass
from typing import List
from database.models import User, ChatRoom, ChatRoomPivot, Message, MessageRead
from datetime import datetime
from zoneinfo import ZoneInfo

class ChatRoomService:
    def __init__(self, session: Session):
        self.session = session

    def create_chat_room(self, chat_room: ChatRoom) -> ChatRoom:
        self.session.add(chat_room)
        self.session.commit()
        self.session.refresh(chat_room)
        return chat_room

    def get_chat_room_by_id(self, chat_room_id: UUID) -> ChatRoom | None:
        statement = select(ChatRoom).where(ChatRoom.id == chat_room_id)
        result = self.session.exec(statement).first()
        return result

    def get_users_in_chat_room(self, chat_room: ChatRoom) -> list[User]:
        statement = select(User).join(ChatRoomPivot).where(
            ChatRoomPivot.chatroom_id == chat_room.id
        )
        results = self.session.exec(statement).all()
        return results

    def add_user_to_chat_room(self, user: User, chat_room: ChatRoom) -> None:
        pivot = ChatRoomPivot(user_id=user.id, chatroom_id=chat_room.id)
        self.session.add(pivot)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
        else:
            self.session.refresh(pivot)

    def remove_user_from_chat_room(self, user: User, chat_room: ChatRoom) -> None:
        statement = select(ChatRoomPivot).where(
            ChatRoomPivot.user_id == user.id,
            ChatRoomPivot.chatroom_id == chat_room.id
        )
        pivot = self.session.exec(statement).first()
        if pivot:
            self.session.delete(pivot)
            self.session.commit()

            remaining_users_statement = select(ChatRoomPivot).where(
                ChatRoomPivot.chatroom_id == chat_room.id
            )
            remaining_pivots = self.session.exec(remaining_users_statement).all()
            if not remaining_pivots:
                messages_statement = select(Message).where(
                    Message.chatroom_id == chat_room.id
                )
                messages = self.session.exec(messages_statement).all()
                for message in messages:
                    self.session.delete(message)

                self.session.delete(chat_room)
                self.session.commit()

    def get_chat_rooms_by_user(self, user: User) -> list[ChatRoom]:
        statement = select(ChatRoom).join(ChatRoomPivot).where(
            ChatRoomPivot.user_id == user.id
        )
        results = self.session.exec(statement).all()
        return results


class MessageService:
    def __init__(self, session: Session):
        self.session = session

    @dataclass
    class MessageDTO:
        id: UUID
        author_id: UUID
        author_name: str
        chatroom_id: UUID
        content: str
        created_at: any
        is_read: bool

    def create_message(self, user: User, chat_room: ChatRoom, content: str) -> Message:
        message = Message(
            author_id=user.id,
            chatroom_id=chat_room.id,
            content=content,
            created_at=datetime.now(tz=ZoneInfo("Asia/Taipei"))
        )
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)

        self.add_message_read_record(message, chat_room)
        return message

    def get_message_by_id(self, message_id: UUID) -> Message | None:
        statement = select(Message).where(Message.id == message_id)
        result = self.session.exec(statement).first()
        return result

    def get_messages_in_chat_room(self, chat_room: ChatRoom) -> list[Message]:
        statement = select(Message).where(
            Message.chatroom_id == chat_room.id,
            Message.is_deleted == False
        ).order_by(Message.created_at)
        results = self.session.exec(statement).all()
        return results

    def get_messages_by_room(
        self,
        room_id,
        user_id,
        limit=50,
        before_created_at=None
    ):
        is_read_subq = (
            select(MessageRead.id)
            .where(
                MessageRead.message_id == Message.id,
                MessageRead.user_id == user_id
            )
            .exists()
        )

        # 使用 JOIN 一次取出作者名稱，避免在迭代中每則訊息查詢作者造成 N+1
        query = (
            self.session.query(
                Message,
                User.username.label("author_name"),
                is_read_subq.label("is_read")
            )
            .join(User, Message.author_id == User.id)
            .filter(
                Message.chatroom_id == room_id,
                Message.is_deleted.is_(False)
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )

        if before_created_at:
            query = query.filter(Message.created_at < before_created_at)

        rows = query.all()
        dto_list: List[MessageService.MessageDTO] = []
        for msg, author_name, is_read in rows:
            dto_list.append(MessageService.MessageDTO(
                id=msg.id,
                author_id=msg.author_id,
                author_name=author_name,
                chatroom_id=msg.chatroom_id,
                content=msg.content,
                created_at=msg.created_at,
                is_read=bool(is_read)
            ))
        return dto_list

    def delete_message(self, message: Message) -> None:
        message.is_deleted = True
        self.session.add(message)
        self.session.commit()

    def add_message_read_record(self, message: Message, room: ChatRoom):
        users = ChatRoomService(self.session).get_users_in_chat_room(room)
        for user in users:
            message_read = MessageRead(user_id=user.id, message_id=message.id)
            self.session.add(message_read)
        self.session.commit()

    def mark_message_as_read(self, user: User, message: Message) -> MessageRead:
        message_read = MessageRead(user_id=user.id, message_id=message.id)
        self.session.add(message_read)
        self.session.commit()
        self.session.refresh(message_read)
        return message_read

    def mark_room_as_read(self, user_id, room_id):
        unread_messages = (
            self.session.query(Message.id)
            .filter(
                Message.chatroom_id == room_id,
                Message.author_id != user_id,
                ~self.session.query(MessageRead)
                .filter(
                    MessageRead.user_id == user_id,
                    MessageRead.message_id == Message.id
                )
                .exists()
            )
        )

        self.session.bulk_save_objects([
            MessageRead(user_id=user_id, message_id=mid)
            for (mid,) in unread_messages
        ])
        self.session.commit()

    def get_read_status(self, message_id: UUID, user_id: UUID) -> MessageRead | None:
        statement = select(MessageRead).where(
            MessageRead.message_id == message_id,
            MessageRead.user_id == user_id
        )
        result = self.session.exec(statement).first()
        return result

# user service
def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    statement = select(User).where(User.id == user_id)
    return session.exec(statement).first()

def get_user_by_user_id(session: Session, user_id: str) -> User | None:
    statement = select(User).where(User.user_id == user_id)
    return session.exec(statement).first()


def create_user(session: Session, user: User) -> User:
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_user(session: Session, user: User) -> User:
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, user: User) -> None:
    session.delete(user)
    session.commit()


# message service


def create_message(session: Session, user: User, chat_room: ChatRoom, content: str) -> Message:
    return MessageService(session).create_message(user, chat_room, content)


def get_message_by_id(session: Session, message_id: UUID) -> Message | None:
    return MessageService(session).get_message_by_id(message_id)


def get_messages_in_chat_room(session: Session, chat_room: ChatRoom) -> list[Message]:
    return MessageService(session).get_messages_in_chat_room(chat_room)


def get_messages_by_room(
    session,
    room_id,
    user_id,
    limit=50,
    before_created_at=None
):
    return MessageService(session).get_messages_by_room(
        room_id=room_id,
        user_id=user_id,
        limit=limit,
        before_created_at=before_created_at
    )


def delete_message(session: Session, message: Message) -> None:
    MessageService(session).delete_message(message)


# read message service
def add_message_read_record(session: Session, message: Message, room: ChatRoom):
    MessageService(session).add_message_read_record(message, room)


def mark_message_as_read(session: Session, user: User, message: Message) -> MessageRead:
    return MessageService(session).mark_message_as_read(user, message)


def mark_room_as_read(session, user_id, room_id):
    return MessageService(session).mark_room_as_read(user_id, room_id)


def get_read_messages_by_user_in_chat_room(session: Session, user: User, chat_room: ChatRoom) -> list[MessageRead]:
    statement = select(MessageRead).join(Message).where(
        MessageRead.user_id == user.id,
        Message.chatroom_id == chat_room.id
    )
    # 獲取前50則
    results = session.exec(statement).limit(50).all()
    return results

# chat room service


def create_chat_room(session: Session, chat_room: ChatRoom) -> ChatRoom:
    return ChatRoomService(session).create_chat_room(chat_room)


def get_chat_room_by_id(session: Session, chat_room_id: UUID) -> ChatRoom | None:
    return ChatRoomService(session).get_chat_room_by_id(chat_room_id)


def get_users_in_chat_room(session: Session, chat_room: ChatRoom) -> list[User]:
    return ChatRoomService(session).get_users_in_chat_room(chat_room)


def add_user_to_chat_room(session: Session, user: User, chat_room: ChatRoom) -> None:
    ChatRoomService(session).add_user_to_chat_room(user, chat_room)


def remove_user_from_chat_room(session: Session, user: User, chat_room: ChatRoom) -> None:
    ChatRoomService(session).remove_user_from_chat_room(user, chat_room)


def get_chat_rooms_by_user(session: Session, user: User) -> list[ChatRoom]:
    return ChatRoomService(session).get_chat_rooms_by_user(user)
