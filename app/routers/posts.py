from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from app.database import get_db, upload_image_to_supabase
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
    cursor.execute(
        f"SELECT post_id, post_image_url FROM post_image WHERE post_id IN ({placeholders}) ORDER BY post_image_id ASC",
        tuple(post_ids),
    )
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
    params = [current_user["user_id"], current_user["user_id"]]
    where_clause = ""
    if cursor is not None:
        where_clause = "WHERE p.post_id < %s"
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
        {where_clause}
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


@router.post("/posts")
def create_post(
    content: str = Form(""),
    images: list[UploadFile] = File(...),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    if not images:
        raise HTTPException(status_code=400, detail="사진을 한 장 이상 선택해 주세요.")
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="사진은 최대 10장까지 업로드할 수 있습니다.")

    uploaded_urls = [upload_image_to_supabase(img, folder="posts") for img in images]

    cur = db.cursor()
    cur.execute(
        "INSERT INTO post (post_content, post_created_time, user_id) VALUES (%s, NOW(), %s)",
        (content, current_user["user_id"]),
    )
    new_post_id = cur.lastrowid

    for url in uploaded_urls:
        cur.execute(
            "INSERT INTO post_image (post_image_url, post_id) VALUES (%s, %s)",
            (url, new_post_id),
        )
    db.commit()
    return {"success": True, "id": new_post_id}


@router.get("/posts/{post_id}")
def get_post_detail(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute(
        """
        SELECT 
            p.post_id, p.post_content, p.post_created_time,
            u.user_id, u.user_username, u.user_name, u.user_profile_url,
            (SELECT COUNT(*) FROM post_likes WHERE post_id = p.post_id) AS like_count,
            (SELECT COUNT(*) FROM comment WHERE post_id = p.post_id) AS comment_count,
            EXISTS(SELECT 1 FROM post_likes WHERE post_id = p.post_id AND user_id = %s) AS liked_by_me,
            EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = u.user_id) AS followed_by_me
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        WHERE p.post_id = %s
        """,
        (current_user["user_id"], current_user["user_id"], post_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    images_map = fetch_post_images(cur, [post_id])
    return format_post(row, images_map.get(post_id, []))


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM post WHERE post_id = %s", (post_id,))
    post = cur.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="본인 게시글만 삭제할 수 있습니다.")

    cur.execute("DELETE FROM post_image WHERE post_id = %s", (post_id,))
    cur.execute("DELETE FROM post_likes WHERE post_id = %s", (post_id,))
    cur.execute("DELETE FROM comment WHERE post_id = %s", (post_id,))
    cur.execute("DELETE FROM post WHERE post_id = %s", (post_id,))
    db.commit()
    return {"success": True}