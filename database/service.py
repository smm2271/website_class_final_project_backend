from sqlmodel import select, Session
from uuid import UUID

from database.models import User, ChatRoom, ChatRoomPivot, Message, MessageRead


# user service
def get_user_by_user_id(session: Session, user_id: str) -> User | None:
    statement = select(User).where(User.user_id == user_id)
    result = session.exec(statement).first()
    return result


def get_user_by_id(session: Session, user_uuid: UUID) -> User | None:
    statement = select(User).where(User.id == user_uuid)
    result = session.exec(statement).first()
    return result


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


def is_user_valid(session: Session, user_id: str, password: str) -> bool:
    statement = select(User).where(User.user_id == user_id,
                                   User.hash_password == password)
    result = session.exec(statement).first()
    return (True if result else False)

# message service


def create_message(session: Session, user: User, chat_room: ChatRoom, content: str) -> Message:
    message = Message(
        user_id=user.id,
        chatroom_id=chat_room.id,
        content=content
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    add_message_read_record(session, user, message, chat_room)
    return message


def get_message_by_id(session: Session, message_id: UUID) -> Message | None:
    statement = select(Message).where(Message.id == message_id)
    result = session.exec(statement).first()
    return result


def get_messages_in_chat_room(session: Session, chat_room: ChatRoom) -> list[Message]:
    statement = select(Message).where(
        Message.chatroom_id == chat_room.id,
        Message.is_deleted == False
    ).order_by(Message.created_at)
    results = session.exec(statement).all()
    return results


def delete_message(session: Session, message: Message) -> None:
    message.is_deleted = True
    session.add(message)
    session.commit()


# read message service
def add_message_read_record(session: Session, message: Message, room: ChatRoom):
    users = get_users_in_chat_room(session, room)
    for user in users:
        message_read = MessageRead(user_id=user.id, message_id=message.id)
        session.add(message_read)
    session.commit()


def mark_message_as_read(session: Session, user: User, message: Message) -> MessageRead:
    message_read = MessageRead(user_id=user.id, message_id=message.id)
    session.add(message_read)
    session.commit()
    session.refresh(message_read)
    return message_read


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
    session.add(chat_room)
    session.commit()
    session.refresh(chat_room)
    return chat_room


def get_chat_room_by_id(session: Session, chat_room_id: UUID) -> ChatRoom | None:
    statement = select(ChatRoom).where(ChatRoom.id == chat_room_id)
    result = session.exec(statement).first()
    return result


def get_users_in_chat_room(session: Session, chat_room: ChatRoom) -> list[User]:
    statement = select(User).join(ChatRoomPivot).where(
        ChatRoomPivot.chatroom_id == chat_room.id)
    results = session.exec(statement).all()
    return results


def add_user_to_chat_room(session: Session, user: User, chat_room: ChatRoom) -> None:
    pivot = ChatRoomPivot(user_id=user.id, chatroom_id=chat_room.id)
    session.add(pivot)
    session.commit()
    session.refresh(pivot)


def remove_user_from_chat_room(session: Session, user: User, chat_room: ChatRoom) -> None:
    statement = select(ChatRoomPivot).where(
        ChatRoomPivot.user_id == user.id,
        ChatRoomPivot.chatroom_id == chat_room.id
    )
    pivot = session.exec(statement).first()
    if pivot:
        session.delete(pivot)
        session.commit()

        # 檢查是否還有用戶在該chatroom，若無則刪除聊天室
        remaining_users_statement = select(ChatRoomPivot).where(
            ChatRoomPivot.chatroom_id == chat_room.id)
        remaining_pivots = session.exec(remaining_users_statement).all()
        if not remaining_pivots:
            # 先刪除該聊天室的所有訊息
            messages_statement = select(Message).where(
                Message.chatroom_id == chat_room.id)
            messages = session.exec(messages_statement).all()
            for message in messages:
                session.delete(message)

            # 再刪除聊天室
            session.delete(chat_room)
            session.commit()


def get_chat_rooms_by_user(session: Session, user: User) -> list[ChatRoom]:
    statement = select(ChatRoom).join(ChatRoomPivot).where(
        ChatRoomPivot.user_id == user.id)
    results = session.exec(statement).all()
    return results
