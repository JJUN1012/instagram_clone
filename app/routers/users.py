from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from app.database import get_db, upload_image_to_supabase
from app.routers.auth import hash_password, require_user
from app.routers.posts import fetch_post_images, format_post

router = APIRouter(prefix="/api/v1")


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def format_user_summary(u: dict) -> dict:
    return {
        "id": u["user_id"],
        "username": u["user_username"],
        "name": u["user_name"],
        "bio": u.get("user_bio") or "",
        "profile_image_url": u.get("user_profile_url"),
    }


@router.get("/users/me")
def get_me(current_user=Depends(require_user)):
    return format_user_summary(current_user)


@router.patch("/users/me")
def update_me(
    name: str = Form(...),
    username: str = Form(...),
    bio: str = Form(""),
    profile_image: UploadFile | None = File(None),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    clean_name = name.strip()
    clean_username = username.strip()
    if not clean_name or not clean_username:
        raise HTTPException(status_code=400, detail="이름과 아이디를 입력해 주세요.")

    cur = db.cursor(dictionary=True)
    if clean_username != current_user["user_username"]:
        cur.execute("SELECT user_id FROM user WHERE user_username = %s", (clean_username,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")

    new_profile_url = current_user["user_profile_url"]
    if profile_image and profile_image.filename:
        new_profile_url = upload_image_to_supabase(profile_image, folder="profiles")

    cur.execute(
        """
        UPDATE user
        SET user_name = %s, user_username = %s, user_bio = %s, user_profile_url = %s
        WHERE user_id = %s
        """,
        (clean_name, clean_username, bio, new_profile_url, current_user["user_id"]),
    )
    db.commit()
    return {
        "id": current_user["user_id"],
        "username": clean_username,
        "name": clean_name,
        "bio": bio,
        "profile_image_url": new_profile_url,
    }


@router.patch("/users/me/password")
def change_password(
    data: PasswordChangeRequest,
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT user_password FROM user WHERE user_id = %s", (current_user["user_id"],))
    row = cur.fetchone()
    if row["user_password"] != hash_password(data.current_password):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 일치하지 않습니다.")

    cur.execute(
        "UPDATE user SET user_password = %s WHERE user_id = %s",
        (hash_password(data.new_password), current_user["user_id"]),
    )
    db.commit()
    return {"success": True}


@router.get("/search/users")
def search_users(
    q: str = Query("", max_length=50),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    keyword = q.strip()
    if not keyword:
        return {"items": []}

    cur = db.cursor(dictionary=True)
    like_pattern = f"%{keyword}%"
    cur.execute(
        """
        SELECT user_id, user_username, user_name, user_bio, user_profile_url
        FROM user
        WHERE user_username LIKE %s OR user_name LIKE %s
        ORDER BY user_username ASC
        LIMIT 30
        """,
        (like_pattern, like_pattern),
    )
    return {"items": [format_user_summary(u) for u in cur.fetchall()]}


def get_profile_payload(cur, target_user: dict, viewer_id: int) -> dict:
    target_id = target_user["user_id"]
    cur.execute("SELECT COUNT(*) AS cnt FROM post WHERE user_id = %s", (target_id,))
    post_count = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) AS cnt FROM follows WHERE followee_id = %s", (target_id,))
    follower_count = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) AS cnt FROM follows WHERE follower_id = %s", (target_id,))
    following_count = cur.fetchone()["cnt"]

    followed_by_me = False
    if viewer_id != target_id:
        cur.execute(
            "SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = %s",
            (viewer_id, target_id),
        )
        followed_by_me = bool(cur.fetchone())

    return {
        "user": format_user_summary(target_user),
        "counts": {
            "post_count": post_count,
            "follower_count": follower_count,
            "following_count": following_count,
        },
        "followed_by_me": followed_by_me,
    }


@router.get("/users/{username}")
def get_user_profile(username: str, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM user WHERE user_username = %s", (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")
    return get_profile_payload(cur, target, current_user["user_id"])


@router.get("/users/{username}/posts")
def get_user_posts(
    username: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: int | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM user WHERE user_username = %s", (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")

    params = [current_user["user_id"], current_user["user_id"], target["user_id"]]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND p.post_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    cur.execute(
        f"""
        SELECT 
            p.post_id, p.post_content, p.post_created_time,
            u.user_id, u.user_username, u.user_name, u.user_profile_url,
            (SELECT COUNT(*) FROM post_likes WHERE post_id = p.post_id) AS like_count,
            (SELECT COUNT(*) FROM comment WHERE post_id = p.post_id) AS comment_count,
            EXISTS(SELECT 1 FROM post_likes WHERE post_id = p.post_id AND user_id = %s) AS liked_by_me,
            EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = u.user_id) AS followed_by_me
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        WHERE p.user_id = %s {where_cursor}
        ORDER BY p.post_id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    has_next = len(rows) > limit
    rows = rows[:limit]
    images_map = fetch_post_images(cur, [r["post_id"] for r in rows])

    items = [format_post(r, images_map.get(r["post_id"], [])) for r in rows]
    next_cursor = items[-1]["id"] if has_next and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/users/{username}/follow")
def follow_user(username: str, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM user WHERE user_username = %s", (username,))
    target = cur.fetchone()
    if not target or target["user_id"] == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="잘못된 팔로우 요청입니다.")

    cur.execute(
        "INSERT IGNORE INTO follows (follower_id, followee_id, follow_time) VALUES (%s, %s, NOW())",
        (current_user["user_id"], target["user_id"]),
    )
    db.commit()
    return get_profile_payload(cur, target, current_user["user_id"])


@router.delete("/users/{username}/follow")
def unfollow_user(username: str, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM user WHERE user_username = %s", (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")

    cur.execute(
        "DELETE FROM follows WHERE follower_id = %s AND followee_id = %s",
        (current_user["user_id"], target["user_id"]),
    )
    db.commit()
    return get_profile_payload(cur, target, current_user["user_id"])


@router.get("/users/{username}/followers")
def get_followers(
    username: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: int | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM user WHERE user_username = %s", (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")

    params = [target["user_id"]]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND u.user_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    cur.execute(
        f"""
        SELECT u.user_id, u.user_username, u.user_name, u.user_bio, u.user_profile_url
        FROM follows f
        JOIN user u ON f.follower_id = u.user_id
        WHERE f.followee_id = %s {where_cursor}
        ORDER BY u.user_id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    has_next = len(rows) > limit
    rows = rows[:limit]
    items = [format_user_summary(u) for u in rows]
    next_cursor = items[-1]["id"] if has_next and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.get("/users/{username}/following")
def get_following(
    username: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: int | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM user WHERE user_username = %s", (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")

    params = [target["user_id"]]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND u.user_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    cur.execute(
        f"""
        SELECT u.user_id, u.user_username, u.user_name, u.user_bio, u.user_profile_url
        FROM follows f
        JOIN user u ON f.followee_id = u.user_id
        WHERE f.follower_id = %s {where_cursor}
        ORDER BY u.user_id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    has_next = len(rows) > limit
    rows = rows[:limit]
    items = [format_user_summary(u) for u in rows]
    next_cursor = items[-1]["id"] if has_next and items else None
    return {"items": items, "next_cursor": next_cursor}