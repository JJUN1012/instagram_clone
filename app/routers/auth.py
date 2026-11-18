import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from app.database import get_db

router = APIRouter(prefix="/api/v1")


class SignupRequest(BaseModel):
    username: str | None = None
    user_id: str | None = None
    name: str
    password: str


class LoginRequest(BaseModel):
    username: str | None = None
    user_id: str | None = None
    password: str


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_current_user(request: Request, db=Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT u.user_id, u.user_username, u.user_name, u.user_bio, u.user_profile_url, s.session_expires_at
        FROM session s
        JOIN user u ON s.user_id = u.user_id
        WHERE s.session_id = %s
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    if not row or row["session_expires_at"] < datetime.now():
        return None
    return row


def require_user(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return current_user


@router.post("/auth/signup")
def signup(data: SignupRequest, response: Response, db=Depends(get_db)):
    username = (data.username or data.user_id or "").strip()
    name = (data.name or username).strip()
    password = data.password

    if not username or not password:
        response.status_code = 400
        return {"success": False, "error": {"code": "INVALID_INPUT", "message": "아이디와 비밀번호를 모두 입력해주세요."}}

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT user_id FROM user WHERE user_username = %s", (username,))
    if cursor.fetchone():
        response.status_code = 409
        return {"success": False, "error": {"code": "DUPLICATE_USER", "message": "이미 사용 중인 아이디입니다."}}

    cursor.execute(
        "INSERT INTO user (user_username, user_name, user_password) VALUES (%s, %s, %s)",
        (username, name, hash_password(password)),
    )
    db.commit()
    return {"success": True, "redirect_url": "/login"}


@router.post("/auth/login")
def login(data: LoginRequest, response: Response, db=Depends(get_db)):
    username = (data.username or data.user_id or "").strip()
    password = data.password

    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT user_id, user_username, user_name, user_password FROM user WHERE user_username = %s",
        (username,),
    )
    user = cursor.fetchone()

    if not user or user["user_password"] != hash_password(password):
        response.status_code = 401
        return {
            "success": False,
            "error": {"code": "INVALID_CREDENTIALS", "message": "아이디 또는 비밀번호가 올바르지 않습니다."},
        }

    session_id = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(days=30)

    cursor.execute(
        "INSERT INTO session (session_id, user_id, session_expires_at) VALUES (%s, %s, %s)",
        (session_id, user["user_id"], expires_at),
    )
    db.commit()

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=30 * 24 * 60 * 60,
        samesite="lax",
    )
    return {
        "success": True,
        "redirect_url": "/timeline",
        "user": {"username": user["user_username"], "name": user["user_name"]},
    }


@router.post("/auth/logout")
def logout(request: Request, response: Response, db=Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        cursor = db.cursor()
        cursor.execute("DELETE FROM session WHERE session_id = %s", (session_id,))
        db.commit()
    response.delete_cookie("session_id")
    return {"success": True, "redirect_url": "/login"}