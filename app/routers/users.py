from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from app.database import delete_image_from_supabase, get_db, load_query, upload_image_to_supabase
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
        raise HTTPException(status_code=400, detail="??? ???? ??? ???.")

    cur = db.cursor(dictionary=True)
    if clean_username != current_user["user_username"]:
        cur.execute(load_query("users.sql", "check_username_duplicate"), (clean_username,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="?? ?? ?? ??????.")

    old_profile_url = current_user["user_profile_url"]
    new_profile_url = old_profile_url
    uploaded_new_profile = False
    if profile_image and profile_image.filename:
        new_profile_url = upload_image_to_supabase(profile_image, folder="profiles")
        uploaded_new_profile = True

    cur.execute(
        load_query("users.sql", "update_user_profile"),
        (clean_name, clean_username, bio, new_profile_url, current_user["user_id"]),
    )
    db.commit()

    if uploaded_new_profile and old_profile_url and old_profile_url != new_profile_url:
        delete_image_from_supabase(old_profile_url)
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
    cur.execute(load_query("users.sql", "get_user_password"), (current_user["user_id"],))
    row = cur.fetchone()
    if row["user_password"] != hash_password(data.current_password):
        raise HTTPException(status_code=400, detail="?? ????? ???? ????.")

    cur.execute(
        load_query("users.sql", "update_user_password"),
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
        load_query("users.sql", "search_users"),
        (like_pattern, like_pattern),
    )
    return {"items": [format_user_summary(u) for u in cur.fetchall()]}


def get_profile_payload(cur, target_user: dict, viewer_id: int) -> dict:
    target_id = target_user["user_id"]
    cur.execute(load_query("users.sql", "count_user_posts"), (target_id,))
    post_count = cur.fetchone()["cnt"]

    cur.execute(load_query("users.sql", "count_user_followers"), (target_id,))
    follower_count = cur.fetchone()["cnt"]

    cur.execute(load_query("users.sql", "count_user_following"), (target_id,))
    following_count = cur.fetchone()["cnt"]

    followed_by_me = False
    if viewer_id != target_id:
        cur.execute(
            load_query("users.sql", "check_is_following"),
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
    cur.execute(load_query("users.sql", "get_user_by_username"), (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="???? ?? ??????.")
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
    cur.execute(load_query("users.sql", "get_user_id_by_username"), (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="???? ?? ??????.")

    params = [current_user["user_id"], current_user["user_id"], target["user_id"]]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND p.post_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    sql = load_query("users.sql", "get_user_posts").format(where_cursor=where_cursor)
    cur.execute(sql, tuple(params))
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
    cur.execute(load_query("users.sql", "get_user_by_username"), (username,))
    target = cur.fetchone()
    if not target or target["user_id"] == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="??? ??? ?????.")

    cur.execute(
        load_query("users.sql", "insert_follow"),
        (current_user["user_id"], target["user_id"]),
    )
    db.commit()
    return get_profile_payload(cur, target, current_user["user_id"])


@router.delete("/users/{username}/follow")
def unfollow_user(username: str, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute(load_query("users.sql", "get_user_by_username"), (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="???? ?? ??????.")

    cur.execute(
        load_query("users.sql", "delete_follow"),
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
    cur.execute(load_query("users.sql", "get_user_id_by_username"), (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="???? ?? ??????.")

    params = [target["user_id"]]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND u.user_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    sql = load_query("users.sql", "get_followers").format(where_cursor=where_cursor)
    cur.execute(sql, tuple(params))
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
    cur.execute(load_query("users.sql", "get_user_id_by_username"), (username,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="???? ?? ??????.")

    params = [target["user_id"]]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND u.user_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    sql = load_query("users.sql", "get_following").format(where_cursor=where_cursor)
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    has_next = len(rows) > limit
    rows = rows[:limit]
    items = [format_user_summary(u) for u in rows]
    next_cursor = items[-1]["id"] if has_next and items else None
    return {"items": items, "next_cursor": next_cursor}
