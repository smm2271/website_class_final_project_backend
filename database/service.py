from sqlmodel import select, Session

from database.models import User, ChatRoom, ChatRoomPivot, Message, MessageRead


# user service: use the provided session (do NOT open new sessions here).
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