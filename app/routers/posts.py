from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from app.database import delete_image_from_supabase, get_db, load_query, upload_image_to_supabase
from app.routers.auth import require_user

router = APIRouter(prefix="/api/v1")


def format_post(row: dict, image_urls: list[str]) -> dict:
    created = row["post_created_time"]
    return {
        "id": row["post_id"],
        "content": row["post_content"] or "",
        "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created),
        "image_urls": image_urls,
        "image_url": image_urls[0] if image_urls else None,
        "like_count": int(row["like_count"]),
        "comment_count": int(row["comment_count"]),
        "liked_by_me": bool(row["liked_by_me"]),
        "author": {
            "id": row["user_id"],
            "username": row["user_username"],
            "name": row["user_name"],
            "profile_image_url": row["user_profile_url"],
            "followed_by_me": bool(row.get("followed_by_me", False)),
        },
    }


def fetch_post_images(cursor, post_ids: list[int]) -> dict[int, list[str]]:
    if not post_ids:
        return {}
    placeholders = ",".join(["%s"] * len(post_ids))
    sql = load_query("posts.sql", "get_post_images").format(placeholders=placeholders)
    cursor.execute(sql, tuple(post_ids))
    mapping: dict[int, list[str]] = {pid: [] for pid in post_ids}
    for r in cursor.fetchall():
        mapping[r["post_id"]].append(r["post_image_url"])
    return mapping


@router.get("/feed")
def get_feed(
    limit: int = Query(20, ge=1, le=50),
    cursor: int | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    cur = db.cursor(dictionary=True)
    uid = current_user["user_id"]
    params = [uid, uid, uid, uid]
    where_clause = ""
    if cursor is not None:
        where_clause = "AND p.post_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    sql = load_query("posts.sql", "get_feed").format(where_clause=where_clause)
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    has_next = len(rows) > limit
    rows = rows[:limit]
    images_map = fetch_post_images(cur, [r["post_id"] for r in rows])

    items = [format_post(r, images_map.get(r["post_id"], [])) for r in rows]
    next_cursor = items[-1]["id"] if has_next and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/posts")
def create_post(
    content: str = Form(""),
    images: list[UploadFile] = File(...),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    if not images:
        raise HTTPException(status_code=400, detail="??? 1? ?? ??? ???.")
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="??? ?? 10??? ???? ? ????.")

    uploaded_urls = [upload_image_to_supabase(img, folder="posts") for img in images]

    cur = db.cursor()
    cur.execute(
        load_query("posts.sql", "insert_post"),
        (content, current_user["user_id"]),
    )
    new_post_id = cur.lastrowid

    insert_img_sql = load_query("posts.sql", "insert_post_image")
    for url in uploaded_urls:
        cur.execute(insert_img_sql, (url, new_post_id))
    db.commit()
    return {"success": True, "id": new_post_id}


@router.get("/posts/{post_id}")
def get_post_detail(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute(
        load_query("posts.sql", "get_post_detail"),
        (current_user["user_id"], current_user["user_id"], post_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="???? ?? ? ????.")

    images_map = fetch_post_images(cur, [post_id])
    return format_post(row, images_map.get(post_id, []))


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute(load_query("posts.sql", "get_post_owner"), (post_id,))
    post = cur.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="???? ?? ? ????.")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="?? ???? ??? ? ????.")

    images_map = fetch_post_images(cur, [post_id])
    image_urls = images_map.get(post_id, [])

    cur.execute(load_query("posts.sql", "delete_post_images"), (post_id,))
    cur.execute(load_query("posts.sql", "delete_post_likes"), (post_id,))
    cur.execute(load_query("posts.sql", "delete_post_comments"), (post_id,))
    cur.execute(load_query("posts.sql", "delete_post"), (post_id,))
    db.commit()

    for url in image_urls:
        delete_image_from_supabase(url)
    return {"success": True}
