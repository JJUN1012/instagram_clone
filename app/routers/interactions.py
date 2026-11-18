from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.database import get_db
from app.routers.auth import require_user

router = APIRouter(prefix="/api/v1")


class CommentRequest(BaseModel):
    content: str


@router.post("/posts/{post_id}/likes")
def like_post(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor()
    cur.execute(
        "INSERT IGNORE INTO post_likes (user_id, post_id, created_time) VALUES (%s, %s, NOW())",
        (current_user["user_id"], post_id),
    )
    db.commit()

    cur.execute("SELECT COUNT(*) FROM post_likes WHERE post_id = %s", (post_id,))
    like_count = cur.fetchone()[0]
    return {"liked_by_me": True, "like_count": like_count}


@router.delete("/posts/{post_id}/likes")
def unlike_post(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor()
    cur.execute(
        "DELETE FROM post_likes WHERE user_id = %s AND post_id = %s",
        (current_user["user_id"], post_id),
    )
    db.commit()

    cur.execute("SELECT COUNT(*) FROM post_likes WHERE post_id = %s", (post_id,))
    like_count = cur.fetchone()[0]
    return {"liked_by_me": False, "like_count": like_count}


@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: int,
    limit: int = Query(20, ge=1, le=50),
    cursor: int | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    cur = db.cursor(dictionary=True)
    params = [post_id]
    where_cursor = ""
    if cursor is not None:
        where_cursor = "AND c.comment_id < %s"
        params.append(cursor)
    params.append(limit + 1)

    cur.execute(
        f"""
        SELECT c.comment_id, c.comment_content, c.comment_created_time,
               u.user_id, u.user_username, u.user_name, u.user_profile_url
        FROM comment c
        JOIN user u ON c.user_id = u.user_id
        WHERE c.post_id = %s {where_cursor}
        ORDER BY c.comment_id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    has_next = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "id": r["comment_id"],
            "content": r["comment_content"],
            "created_at": r["comment_created_time"].isoformat()
            if hasattr(r["comment_created_time"], "isoformat")
            else str(r["comment_created_time"]),
            "author": {
                "id": r["user_id"],
                "username": r["user_username"],
                "name": r["user_name"],
                "profile_image_url": r["user_profile_url"],
            },
        }
        for r in rows
    ]
    next_cursor = items[-1]["id"] if has_next and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    data: CommentRequest,
    db=Depends(get_db),
    current_user=Depends(require_user),
):
    content = data.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="댓글 내용을 입력해 주세요.")

    cur = db.cursor(dictionary=True)
    cur.execute(
        "INSERT INTO comment (user_id, post_id, comment_content, comment_created_time) VALUES (%s, %s, %s, NOW())",
        (current_user["user_id"], post_id, content),
    )
    new_id = cur.lastrowid
    db.commit()

    cur.execute("SELECT comment_created_time FROM comment WHERE comment_id = %s", (new_id,))
    created = cur.fetchone()["comment_created_time"]

    return {
        "id": new_id,
        "content": content,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created),
        "author": {
            "id": current_user["user_id"],
            "username": current_user["user_username"],
            "name": current_user["user_name"],
            "profile_image_url": current_user["user_profile_url"],
        },
    }


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM comment WHERE comment_id = %s", (comment_id,))
    comment = cur.fetchone()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if comment["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="본인 댓글만 삭제할 수 있습니다.")

    cur.execute("DELETE FROM comment WHERE comment_id = %s", (comment_id,))
    db.commit()
    return {"success": True}