from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.database import get_db, load_query
from app.routers.auth import require_user

router = APIRouter(prefix="/api/v1")


class CommentRequest(BaseModel):
    content: str


@router.post("/posts/{post_id}/likes")
def like_post(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor()
    cur.execute(
        load_query("interactions.sql", "insert_post_like"),
        (current_user["user_id"], post_id),
    )
    db.commit()

    cur.execute(load_query("interactions.sql", "count_post_likes"), (post_id,))
    like_count = cur.fetchone()[0]
    return {"liked_by_me": True, "like_count": like_count}


@router.delete("/posts/{post_id}/likes")
def unlike_post(post_id: int, db=Depends(get_db), current_user=Depends(require_user)):
    cur = db.cursor()
    cur.execute(
        load_query("interactions.sql", "delete_post_like"),
        (current_user["user_id"], post_id),
    )
    db.commit()

    cur.execute(load_query("interactions.sql", "count_post_likes"), (post_id,))
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

    sql = load_query("interactions.sql", "list_comments").format(where_cursor=where_cursor)
    cur.execute(sql, tuple(params))
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
        raise HTTPException(status_code=400, detail="?? ??? ??? ???.")

    cur = db.cursor(dictionary=True)
    cur.execute(
        load_query("interactions.sql", "insert_comment"),
        (current_user["user_id"], post_id, content),
    )
    new_id = cur.lastrowid
    db.commit()

    cur.execute(load_query("interactions.sql", "get_comment_created_time"), (new_id,))
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
    cur.execute(load_query("interactions.sql", "get_comment_owner"), (comment_id,))
    comment = cur.fetchone()
    if not comment:
        raise HTTPException(status_code=404, detail="??? ?? ? ????.")
    if comment["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="?? ??? ??? ? ????.")

    cur.execute(load_query("interactions.sql", "delete_comment"), (comment_id,))
    db.commit()
    return {"success": True}
