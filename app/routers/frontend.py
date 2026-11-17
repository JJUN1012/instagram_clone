"""HTML entry points for the Instagram frontend."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parents[1]
router = APIRouter()
templates = Jinja2Templates(directory=APP_DIR / "templates")

PAGE_ROUTES = (
    ("/login", "login", "로그인"),
    ("/signup", "signup", "회원가입"),
    ("/timeline", "feed", "홈"),
    ("/me", "profile", "내 프로필"),
    ("/users/me/edit", "edit", "프로필 편집"),
    ("/users/{username}/followers", "followers", "팔로워"),
    ("/users/{username}/following", "following", "팔로잉"),
    ("/users/{username}", "profile", "프로필"),
    ("/posts/upload", "upload", "새 게시물"),
    ("/posts/{post_id}/comments", "comments", "댓글"),
    ("/posts/{post_id}", "post", "게시물"),
    ("/setting", "settings", "설정"),
    ("/setting/password", "password", "비밀번호 변경"),
)


def page_handler(screen: str, title: str):
    def render(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="frontend.html",
            context={
                "screen": screen,
                "title": title,
                "username": request.path_params.get("username", ""),
                "post_id": request.path_params.get("post_id", ""),
            },
        )

    return render


for path, screen, title in PAGE_ROUTES:
    router.add_api_route(
        path, page_handler(screen, title), methods=["GET"],
        name=screen + ("_by_username" if screen == "profile" and "{" in path else ""),
        response_class=HTMLResponse, include_in_schema=False,
    )
