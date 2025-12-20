# database.py
from contextlib import contextmanager
from sqlmodel import SQLModel, create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine
from dotenv import load_dotenv
import os
from sqlmodel import Session
from database.models import User, ChatRoom, ChatRoomPivot, Message, MessageRead

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session_context():
    with Session(engine) as session:
        yield session


def get_session():
    with get_session_context() as session:
        yield session


if __name__ == "__main__":
    create_db_and_tables()
    print("資料庫表格建立完成！")
