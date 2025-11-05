# models.py
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, unique=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)

