# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# PostgreSQL 連線字串格式：
# postgresql://<使用者>:<密碼>@<主機>:<埠號>/<資料庫名稱>

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:your_password@localhost:5432/fastapi_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
