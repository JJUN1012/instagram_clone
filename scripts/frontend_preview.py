"""Local UI review server. All state is temporary and uses sample data."""

from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from secrets import token_urlsafe

from fastapi import APIRouter, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routers.frontend import APP_DIR, router as frontend_router

app = FastAPI(title="Instagram frontend preview")
app.add_middleware(SessionMiddleware, secret_key=token_urlsafe(32))
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="frontend_assets")
app.mount("/preview-images", StaticFiles(directory=Path(__file__).with_name("frontend_demo_images")))
app.include_router(frontend_router)
api = APIRouter(prefix="/api/v1")

users = {
    1: {"id": 1, "username": "demo", "name": "운", "bio": "일상의 장면을 모아요.", "profile_image_url": None},
    2: {"id": 2, "username": "seojin", "name": "서진", "bio": "제주에서 사진을 찍어요.", "profile_image_url": None},
    3: {"id": 3, "username": "yuna", "name": "유나", "bio": "커피와 산책.", "profile_image_url": None},
}
passwords = {1: "demo1234"}
following = {(1, 2), (1, 3), (2, 1)}
posts = {
    1: {"id": 1, "author_id": 1, "content": "초록이 짙어지는 계절, 천천히 걸었어요.",
        "image_urls": ["/preview-images/trail.webp"], "created_at": "2026-11-14T03:20:00Z"},
    2: {"id": 2, "author_id": 3, "content": "비가 오는 날엔 창가 자리가 제일 좋아요.",
        "image_urls": ["/preview-images/seoul.webp"], "created_at": "2026-11-15T04:20:00Z"},
    3: {"id": 3, "author_id": 2, "content": "이른 아침, 바람이 불어오는 제주 바다.",
        "image_urls": ["/preview-images/jeju.webp", "/preview-images/trail.webp"],
        "created_at": "2026-11-16T22:17:00Z"},
}
likes = {(2, 3), (3, 3), (1, 2)}
comments = {
    1: {"id": 1, "post_id": 3, "author_id": 3, "content": "빗소리 대신 파도 소리가 들리는 것 같아요.",
        "created_at": "2026-11-17T01:00:00Z"},
    2: {"id": 2, "post_id": 3, "author_id": 1, "content": "다음 제주 여행에 꼭 가봐야겠네요!",
        "created_at": "2026-11-17T01:30:00Z"},
}
user_ids = count(4)
post_ids = count(4)
comment_ids = count(3)
media = {}
image_types = {"image/jpeg", "image/png", "image/webp"}


class PreviewError(Exception):
    def __init__(self, status_code, code, message):
        self.status_code = status_code
        self.code = code
        self.message = message


@app.exception_handler(PreviewError)
async def preview_error(request, exc):
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}},
        status_code=exc.status_code,
    )


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current_user(request: Request):
    user = users.get(request.session.get("user_id"))
    if user is None:
        raise PreviewError(401, "LOGIN_REQUIRED", "로그인해 주세요.")
    return user


def find_user(username):
    user = next((value for value in users.values() if value["username"] == username), None)
    if user is None:
        raise PreviewError(404, "USER_NOT_FOUND", "사용자를 찾을 수 없어요.")
    return user


def find_post(post_id):
    if post_id not in posts:
        raise PreviewError(404, "POST_NOT_FOUND", "게시물을 찾을 수 없어요.")
    return posts[post_id]


def check_username(username, owner=None):
    if not username or len(username) > 50 or any(char in username for char in "/?#"):
        raise PreviewError(422, "INVALID_USERNAME", "사용할 수 없는 아이디예요.")
    if username.casefold() == "me" or any(
        user["username"].casefold() == username.casefold() and user["id"] != owner
        for user in users.values()
    ):
        raise PreviewError(409, "USERNAME_TAKEN", "이미 사용 중인 아이디예요.")


def like_state(post_id, user_id):
    return {
        "like_count": sum(target == post_id for _, target in likes),
        "liked_by_me": (user_id, post_id) in likes,
    }


def post_data(post, user_id):
    data = {key: value for key, value in post.items() if key != "author_id"}
    data["author"] = users[post["author_id"]]
    data["comment_count"] = sum(comment["post_id"] == post["id"] for comment in comments.values())
    return {**data, **like_state(post["id"], user_id)}


def comment_data(comment):
    return {
        "id": comment["id"], "author": users[comment["author_id"]],
        "content": comment["content"], "created_at": comment["created_at"],
    }


def page(rows, limit, cursor):
    limit = max(1, min(limit, 100))
    ordered = sorted(rows, key=lambda row: row["id"], reverse=True)
    if cursor is not None:
        ordered = [row for row in ordered if row["id"] < cursor]
    items = ordered[:limit]
    return {"items": items, "next_cursor": str(items[-1]["id"]) if len(ordered) > limit else None}


async def read_image(upload):
    if upload.content_type not in image_types:
        raise PreviewError(415, "IMAGE_TYPE", "JPEG, PNG, WebP 사진을 선택해 주세요.")
    data = await upload.read(10 * 1024 * 1024 + 1)
    if not data or len(data) > 10 * 1024 * 1024:
        raise PreviewError(422, "IMAGE_SIZE", "사진은 한 장에 10MB까지 올릴 수 있어요.")
    return data, upload.content_type


def store_image(photo):
    key = token_urlsafe(12)
    media[key] = photo
    return "/preview-media/" + key


@app.get("/preview-media/{key}")
async def preview_media(key: str):
    if key not in media:
        return Response(status_code=404)
    data, mime_type = media[key]
    return Response(data, media_type=mime_type, headers={"X-Content-Type-Options": "nosniff"})


@app.get("/")
async def root(request: Request):
    return RedirectResponse("/timeline" if request.session.get("user_id") else "/login")


@api.post("/auth/login")
async def login(request: Request, body: dict):
    user = next((item for item in users.values() if item["username"] == body.get("username")), None)
    if user is None or passwords.get(user["id"]) != body.get("password"):
        raise PreviewError(401, "INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않아요.")
    request.session["user_id"] = user["id"]
    return {"user": user}


@api.post("/auth/signup", status_code=201)
async def signup(body: dict):
    username = str(body.get("username", "")).strip()
    check_username(username)
    name = str(body.get("name", "")).strip()
    password = str(body.get("password", ""))
    if not name or len(name) > 50 or not password:
        raise PreviewError(422, "INVALID_INPUT", "이름과 비밀번호를 확인해 주세요.")
    user_id = next(user_ids)
    user = {"id": user_id, "username": username, "name": name, "bio": "", "profile_image_url": None}
    users[user_id] = user
    passwords[user_id] = password
    return {"user": user}


@api.post("/auth/logout", status_code=204)
async def logout(request: Request):
    request.session.clear()


@api.get("/users/me")
async def me(request: Request):
    return current_user(request)


@api.patch("/users/me")
async def edit(
    request: Request, username: str = Form(), name: str = Form(), bio: str = Form(default=""),
    profile_image: UploadFile | None = File(default=None),
):
    user = current_user(request)
    photo = await read_image(profile_image) if profile_image else None
    check_username(username, user["id"])
    if not name.strip() or len(name) > 50 or len(bio) > 250:
        raise PreviewError(422, "INVALID_INPUT", "이름 또는 소개 길이를 확인해 주세요.")
    user.update({"username": username, "name": name, "bio": bio})
    if photo:
        user["profile_image_url"] = store_image(photo)
    return user


@api.patch("/users/me/password", status_code=204)
async def change_password(request: Request, body: dict):
    user_id = current_user(request)["id"]
    if passwords[user_id] != body.get("current_password"):
        raise PreviewError(400, "INVALID_PASSWORD", "현재 비밀번호를 확인해 주세요.")
    if not body.get("new_password"):
        raise PreviewError(422, "INVALID_INPUT", "새 비밀번호를 입력해 주세요.")
    passwords[user_id] = body["new_password"]


def profile_data(target, viewer):
    user_id = target["id"]
    return {
        "user": target,
        "counts": {
            "post_count": sum(post["author_id"] == user_id for post in posts.values()),
            "follower_count": sum(followee == user_id for _, followee in following),
            "following_count": sum(follower == user_id for follower, _ in following),
        },
        "followed_by_me": (viewer["id"], user_id) in following,
    }


@api.get("/search/users")
async def search_users(request: Request, q: str = Query(default="", max_length=50)):
    viewer = current_user(request)
    term = q.strip().casefold()
    if not term:
        return {"items": []}

    matches = []
    for user in users.values():
        username = user["username"].casefold()
        if user["id"] == viewer["id"] or term not in username:
            continue
        rank = (username != term, not username.startswith(term), username)
        result = {key: user[key] for key in ("id", "username", "name", "profile_image_url")}
        matches.append((rank, result))
    matches.sort(key=lambda match: match[0])
    return {"items": [result for _, result in matches[:20]]}


@api.get("/users/{username}")
async def profile(request: Request, username: str):
    return profile_data(find_user(username), current_user(request))


@api.get("/users/{username}/posts")
async def profile_posts(request: Request, username: str, limit: int = 20, cursor: int | None = None):
    viewer = current_user(request)
    owner = find_user(username)
    return page((post_data(post, viewer["id"]) for post in posts.values() if post["author_id"] == owner["id"]), limit, cursor)


@api.get("/users/{username}/followers")
async def followers(request: Request, username: str, limit: int = 20, cursor: int | None = None):
    current_user(request)
    target = find_user(username)["id"]
    return page((users[follower] for follower, followee in following if followee == target), limit, cursor)


@api.get("/users/{username}/following")
async def following_list(request: Request, username: str, limit: int = 20, cursor: int | None = None):
    current_user(request)
    target = find_user(username)["id"]
    return page((users[followee] for follower, followee in following if follower == target), limit, cursor)


@api.api_route("/users/{username}/follow", methods=["POST", "DELETE"])
async def follow(request: Request, username: str):
    viewer = current_user(request)
    target = find_user(username)
    if viewer["id"] == target["id"]:
        raise PreviewError(400, "SELF_FOLLOW", "자기 자신은 팔로우할 수 없어요.")
    pair = viewer["id"], target["id"]
    if request.method == "POST":
        following.add(pair)
    else:
        following.discard(pair)
    return profile_data(target, viewer)


@api.get("/feed")
async def feed(request: Request, limit: int = 20, cursor: int | None = None):
    user_id = current_user(request)["id"]
    visible = {user_id, *(followee for follower, followee in following if follower == user_id)}
    return page((post_data(post, user_id) for post in posts.values() if post["author_id"] in visible), limit, cursor)


@api.post("/posts", status_code=201)
async def create_post(request: Request, content: str = Form(default=""), images: list[UploadFile] = File()):
    author = current_user(request)
    if not 1 <= len(images) <= 10 or len(content) > 2000:
        raise PreviewError(422, "INVALID_POST", "사진 개수나 캡션 길이를 확인해 주세요.")
    photos = [await read_image(upload) for upload in images]
    post_id = next(post_ids)
    post = {"id": post_id, "author_id": author["id"], "content": content,
            "image_urls": [store_image(photo) for photo in photos], "created_at": now()}
    posts[post_id] = post
    return post_data(post, author["id"])


@api.get("/posts/{post_id}")
async def get_post(request: Request, post_id: int):
    return post_data(find_post(post_id), current_user(request)["id"])


@api.delete("/posts/{post_id}", status_code=204)
async def delete_post(request: Request, post_id: int):
    user_id = current_user(request)["id"]
    if find_post(post_id)["author_id"] != user_id:
        raise PreviewError(403, "FORBIDDEN", "게시물을 삭제할 권한이 없어요.")
    post = posts.pop(post_id)
    for image_url in post["image_urls"]:
        if image_url.startswith("/preview-media/"):
            media.pop(image_url.rsplit("/", 1)[1], None)
    for comment_id in [key for key, item in comments.items() if item["post_id"] == post_id]:
        del comments[comment_id]
    likes.difference_update([pair for pair in likes if pair[1] == post_id])


@api.api_route("/posts/{post_id}/likes", methods=["POST", "DELETE"])
async def like(request: Request, post_id: int):
    user_id = current_user(request)["id"]
    find_post(post_id)
    if request.method == "POST":
        likes.add((user_id, post_id))
    else:
        likes.discard((user_id, post_id))
    return like_state(post_id, user_id)


@api.get("/posts/{post_id}/comments")
async def list_comments(request: Request, post_id: int, limit: int = 20, cursor: int | None = None):
    current_user(request)
    find_post(post_id)
    return page((comment_data(item) for item in comments.values() if item["post_id"] == post_id), limit, cursor)


@api.post("/posts/{post_id}/comments", status_code=201)
async def create_comment(request: Request, post_id: int, body: dict):
    user_id = current_user(request)["id"]
    find_post(post_id)
    content = body.get("content")
    if not isinstance(content, str) or not content.strip() or len(content.strip()) > 1000:
        raise PreviewError(422, "INVALID_COMMENT", "댓글은 1,000자 이내로 작성해 주세요.")
    comment_id = next(comment_ids)
    comment = {"id": comment_id, "post_id": post_id, "author_id": user_id,
               "content": content.strip(), "created_at": now()}
    comments[comment_id] = comment
    return comment_data(comment)


@api.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(request: Request, comment_id: int):
    user_id = current_user(request)["id"]
    if comment_id not in comments:
        raise PreviewError(404, "COMMENT_NOT_FOUND", "댓글을 찾을 수 없어요.")
    if comments[comment_id]["author_id"] != user_id:
        raise PreviewError(403, "FORBIDDEN", "댓글을 삭제할 권한이 없어요.")
    del comments[comment_id]


app.include_router(api)
