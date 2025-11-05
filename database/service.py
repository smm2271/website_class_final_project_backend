from sqlalchemy.orm import Session
import hashlib
from database import models


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def get_user_by_id(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.user_id == user_id).first()


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, user_id: str, username: str, password: str):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    db_user = models.User(user_id=user_id, username=username,
                          hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def update_user(db: Session, user_id: str, new_username: str = None, new_password: str = None):
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    if new_username:
        user.username = new_username
    if new_password:
        user.hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: str):
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    db.delete(user)
    db.commit()
    return user