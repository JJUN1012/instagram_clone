from pathlib import Path
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import auth, interactions, posts, users
from app.routers.auth import get_current_user

app = FastAPI(title="Instagram Clone")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="frontend_assets")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(interactions.router)
app.include_router(users.router)


def render_screen(request: Request, screen: str, title: str, username: str = "", post_id: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="frontend.html",
        context={
            "screen": screen,
            "title": title,
            "username": username,
            "post_id": post_id,
        },
    )


@app.get("/")
def root(current_user=Depends(get_current_user)):
    return RedirectResponse(url="/timeline" if current_user else "/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def page_login(request: Request):
    return render_screen(request, "login", "로그인")


@app.get("/signup", response_class=HTMLResponse)
def page_signup(request: Request):
    return render_screen(request, "signup", "회원가입")


@app.get("/timeline", response_class=HTMLResponse)
def page_timeline(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "feed", "홈")


@app.get("/search", response_class=HTMLResponse)
def page_search(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "search", "검색")


@app.get("/posts/upload", response_class=HTMLResponse)
def page_upload(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "upload", "새 게시물")


@app.get("/posts/{post_id}", response_class=HTMLResponse)
def page_post(post_id: int, request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "post", "게시물", post_id=str(post_id))


@app.get("/posts/{post_id}/comments", response_class=HTMLResponse)
def page_comments(post_id: int, request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "comments", "댓글", post_id=str(post_id))


@app.get("/me", response_class=HTMLResponse)
def page_me(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "profile", current_user["user_username"])


@app.get("/users/me/edit", response_class=HTMLResponse)
def page_edit_profile(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "edit", "프로필 편집")


@app.get("/users/{username}", response_class=HTMLResponse)
def page_user_profile(username: str, request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "profile", username, username=username)


@app.get("/users/{username}/followers", response_class=HTMLResponse)
def page_followers(username: str, request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "followers", "팔로워", username=username)


@app.get("/users/{username}/following", response_class=HTMLResponse)
def page_following(username: str, request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "following", "팔로잉", username=username)


@app.get("/setting", response_class=HTMLResponse)
def page_setting(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "settings", "설정")


@app.get("/setting/password", response_class=HTMLResponse)
def page_password(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return render_screen(request, "password", "비밀번호 변경")