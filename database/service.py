from sqlmodel import select, Session

from database.models import User, ChatRoom, ChatRoomPivot, Message, MessageRead


# user service
def get_user_by_user_id(session: Session, user_id: str) -> User | None:
    statement = select(User).where(User.user_id == user_id)
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
    statement = select(User).where(User.user_id == user_id, User.hash_password == password)
    result = session.exec(statement).first()
    return (True if result else False)

# message service
def create_message(session: Session, message: Message) -> Message:
    session.add(message)
    session.commit()
    session.refresh(message)
    return message

def get_messages_in_chat_room(session: Session, chat_room_id: str) -> list[Message]:
    statement = select(Message).where(Message.chatroom_id == chat_room_id, Message.is_deleted == False).order_by(Message.created_at)
    results = session.exec(statement).all()
    return results

def delete_message(session: Session, message_id: str) -> None:
    statement = select(Message).where(Message.id == message_id)
    message = session.exec(statement).first()
    if message:
        message.is_deleted = True
        session.commit()

# read message service
def mark_message_as_read(session: Session, user_id: str, message_id: str)-> MessageRead:
    message_read = MessageRead(user_id=user_id, message_id=message_id)
    session.add(message_read)
    session.commit()
    session.refresh(message_read)
    return message_read

# chat room service
def create_chat_room(session: Session, chat_room: ChatRoom) -> ChatRoom:
    session.add(chat_room)
    session.commit()
    session.refresh(chat_room)
    return chat_room

def get_users_in_chat_room(session: Session, chat_room_id: str) -> list[User]:
    statement = select(User).join(ChatRoomPivot).where(ChatRoomPivot.chat_room_id == chat_room_id)
    results = session.exec(statement).all()
    return results

def add_user_to_chat_room(session: Session, user_id: str, chat_room_id: str) -> ChatRoomPivot:
    pivot = ChatRoomPivot(user_id=user_id, chat_room_id=chat_room_id)
    session.add(pivot)
    session.commit()
    session.refresh(pivot)
    return pivot

def remove_user_from_chat_room(session: Session, user_id: str, chat_room_id: str) -> None:
    statement = select(ChatRoomPivot).where(ChatRoomPivot.user_id == user_id, ChatRoomPivot.chat_room_id == chat_room_id)
    pivot = session.exec(statement).first()
    if pivot:
        session.delete(pivot)
        session.commit()
        # 檢查是否還有用戶在該chatroom，若無則刪除聊天室
        remaining_users_statement = select(ChatRoomPivot).where(ChatRoomPivot.chat_room_id == chat_room_id)
        remaining_pivots = session.exec(remaining_users_statement).all()
        if not remaining_pivots:
            chat_room_statement = select(ChatRoom).where(ChatRoom.id == chat_room_id)
            chat_room = session.exec(chat_room_statement).first()
            if chat_room:
                session.delete(chat_room)
                session.commit()
                # 刪除該聊天室的所有訊息
                messages_statement = select(Message).where(Message.chatroom_id == chat_room_id)
                messages = session.exec(messages_statement).all()
                for message in messages:
                    session.delete(message)
                session.commit()

def get_chat_rooms_by_user(session: Session, user_id: str) -> list[ChatRoom]:
    statement = select(ChatRoom).join(ChatRoomPivot).where(ChatRoomPivot.user_id == user_id)
    results = session.exec(statement).all()
    return results

