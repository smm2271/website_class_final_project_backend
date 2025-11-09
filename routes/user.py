from auth.user_auth import get_current_user, create_access_token, create_refresh_token
from database.service import get_user_by_user_id, create_user
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse, RedirectResponse
from database.database import get_session
from auth.user_factory import get_a_new_user
from sqlmodel import Session
import pydantic

class UserLoginResponseModel(pydantic.BaseModel):
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

router = APIRouter(prefix="/users")


@router.post("/login", response_model=UserLoginResponseModel)
def login_user(user: UserLoginForm, session: Session = Depends(get_session)):
    db_user = get_user_by_user_id(session, user.user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    access_token = create_access_token({"sub": str(db_user.id)})
    refresh_token = create_refresh_token({"sub": str(db_user.id)})
    resp = JSONResponse(content={"id": str(db_user.id), "user_id": db_user.user_id, "username": db_user.username}, status_code=status.HTTP_200_OK)
    # set cookies on the response object (use httponly for tokens)
    resp.set_cookie(key="access_token", value=access_token, httponly=True)
    resp.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return resp

@router.post("/logout")
def logout_user():
    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(key="access_token")
    resp.delete_cookie(key="refresh_token")
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
    resp = JSONResponse(content={"message": "Token refreshed successfully"}, status_code=status.HTTP_200_OK)
    resp.set_cookie(key="access_token", value=access_token, httponly=True)
    resp.set_cookie(key="refresh_token", value=refresh_token_new, httponly=True)
    return resp


@router.post("/register", response_model=UserLoginResponseModel)
def register_user(user: UserRegisterForm, session: Session = Depends(get_session)):
    db_user = get_user_by_user_id(session, user.user_id)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    new_user = get_a_new_user(user.user_id, user.username, user.password)
    created = create_user(session, new_user)
    return JSONResponse(content={"id": str(created.id), "user_id": created.user_id, "username": created.username}, status_code=status.HTTP_201_CREATED)

