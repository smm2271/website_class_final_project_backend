from auth.user_auth import get_current_user, create_access_token, create_refresh_token, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from database.service import get_user_by_user_id, create_user
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse, RedirectResponse
from database.database import get_session
from auth.user_factory import get_a_new_user, verify_user_password
from sqlmodel import Session
import pydantic
import os

# 控制 cookie 的 secure 屬性（開發時預設 False，生產環境請設定環境變數 COOKIE_SECURE=true）
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

class UserResponseModel(pydantic.BaseModel):
    id: str
    user_id: str
    username: str

class UserLoginForm(pydantic.BaseModel):
    user_id: str
    password: str

class UserRegisterForm(pydantic.BaseModel):
    user_id: str
    username: str
    password: str

router = APIRouter()


@router.post("/login", response_model=UserResponseModel)
def login_user(user: UserLoginForm, session: Session = Depends(get_session)):
    db_user = get_user_by_user_id(session, user.user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not verify_user_password(db_user, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    access_token = create_access_token({"sub": str(db_user.id)})
    refresh_token = create_refresh_token({"sub": str(db_user.id)})
    
    cookie_samesite = "none" if COOKIE_SECURE else "lax"
    cookie_secure = COOKIE_SECURE

    resp = JSONResponse(content={"id": str(db_user.id), "user_id": db_user.user_id, "username": db_user.username}, status_code=status.HTTP_200_OK)
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    resp.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path="/",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return resp

@router.post("/logout")
def logout_user():
    # Compute cookie attributes consistently with login
    cookie_samesite = "none" if COOKIE_SECURE else "lax"
    cookie_secure = COOKIE_SECURE

    # Clear cookies by setting empty value and max_age=0 with same attributes
    resp = JSONResponse(content={"message": "Logged out successfully"}, status_code=status.HTTP_200_OK)
    resp.set_cookie(key="access_token", value="", max_age=0, httponly=True, secure=cookie_secure, samesite=cookie_samesite, path="/")
    resp.set_cookie(key="refresh_token", value="", max_age=0, httponly=True, secure=cookie_secure, samesite=cookie_samesite, path="/")
    return resp

@router.post("/refresh-token")
def refresh_token(request: Request):
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided")

    user = get_current_user(refresh_token_cookie)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token_new = create_refresh_token({"sub": str(user.id)})

    cookie_samesite = "none" if COOKIE_SECURE else "lax"
    cookie_secure = COOKIE_SECURE

    resp = JSONResponse(content={"message": "Token refreshed successfully"}, status_code=status.HTTP_200_OK)
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    resp.set_cookie(
        key="refresh_token",
        value=refresh_token_new,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path="/",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return resp


@router.post("/register", response_model=UserResponseModel)
def register_user(user: UserRegisterForm, session: Session = Depends(get_session)):
    db_user = get_user_by_user_id(session, user.user_id)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    new_user = get_a_new_user(user.user_id, user.username, user.password)
    created = create_user(session, new_user)
    return JSONResponse(content={"id": str(created.id), "user_id": created.user_id, "username": created.username}, status_code=status.HTTP_201_CREATED)