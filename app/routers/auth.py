import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from app.database import get_db, load_query

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
    cursor.execute(load_query("auth.sql", "get_session_user"), (session_id,))
    row = cursor.fetchone()
    if not row or row["session_expires_at"] < datetime.now():
        return None
    return row


def require_user(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="???? ?????.")
    return current_user


@router.post("/auth/signup")
def signup(data: SignupRequest, response: Response, db=Depends(get_db)):
    username = (data.username or data.user_id or "").strip()
    name = (data.name or username).strip()
    password = data.password

    if not username or not password:
        response.status_code = 400
        return {"success": False, "error": {"code": "INVALID_INPUT", "message": "???? ????? ?? ??????."}}

    cursor = db.cursor(dictionary=True)
    cursor.execute(load_query("auth.sql", "check_username_exists"), (username,))
    if cursor.fetchone():
        response.status_code = 409
        return {"success": False, "error": {"code": "DUPLICATE_USER", "message": "?? ?? ?? ??????."}}

    cursor.execute(
        load_query("auth.sql", "insert_user"),
        (username, name, hash_password(password)),
    )
    db.commit()
    return {"success": True, "redirect_url": "/login"}


@router.post("/auth/login")
def login(data: LoginRequest, response: Response, db=Depends(get_db)):
    username = (data.username or data.user_id or "").strip()
    password = data.password

    cursor = db.cursor(dictionary=True)
    cursor.execute(load_query("auth.sql", "get_user_for_login"), (username,))
    user = cursor.fetchone()

    if not user or user["user_password"] != hash_password(password):
        response.status_code = 401
        return {
            "success": False,
            "error": {"code": "INVALID_CREDENTIALS", "message": "??? ?? ????? ???? ????."},
        }

    session_id = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(days=30)

    cursor.execute(
        load_query("auth.sql", "insert_session"),
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
        cursor.execute(load_query("auth.sql", "delete_session"), (session_id,))
        db.commit()
    response.delete_cookie("session_id")
    return {"success": True, "redirect_url": "/login"}
