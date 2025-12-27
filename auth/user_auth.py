from database.service import get_user_by_id
from jose import JWTError, jwt
import os
from database.models import User
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

if os.getenv("SECRET_KEY"):
    SECRET_KEY = os.getenv("SECRET_KEY").encode()
else:
    SECRET_KEY = os.urandom(32)
    
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 3


def verify_token(token: str | None) -> User | None:
    if not token:
        return None
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not (user_id := payload.get("sub")):
            return None
            
        return get_user_by_id(user_id)

    except (JWTError, ValueError): # 捕捉具體可能的錯誤
        return None


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.now(timezone.utc) +
                     timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.now(timezone.utc) +
                     timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str | None):
    return verify_token(token)
