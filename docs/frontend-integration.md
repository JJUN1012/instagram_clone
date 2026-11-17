# 프론트엔드 검토 및 FastAPI 연결

이 프론트엔드는 `main`의 `0ad82e2`에서 작업을 시작했습니다. 미리보기는 별도 FastAPI 서버이며 다시 실행하면 샘플 상태가 초기화됩니다.

## 로컬 화면 열기

프로젝트 루트에서 실행합니다.

```powershell
py -m pip install fastapi uvicorn jinja2 python-multipart itsdangerous
py -m uvicorn scripts.frontend_preview:app --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000/`에 접속합니다. 샘플 계정은 `demo` / `demo1234`입니다. 가입한 계정은 이번 서버 실행 동안만 사용할 수 있습니다.

## 팀 FastAPI 앱에 연결

`app/main.py`에서 아래처럼 정적 파일과 페이지 라우터를 등록합니다. 기존 정적 파일 마운트가 있다면 이름을 `frontend_assets`로 맞춰 한 번만 등록합니다. HTML 페이지와 API는 같은 주소와 포트에서 제공하고, API 라우터만 `/api/v1` 아래에 등록합니다. 예를 들어 브라우저는 `GET /timeline`으로 HTML을 받은 뒤 `GET /api/v1/users/me`로 로그인 사용자와 하단 프로필 사진을 확인하고, `GET /api/v1/feed?limit=20`으로 게시물 목록을 불러옵니다.

```python
from fastapi.staticfiles import StaticFiles
from app.routers.frontend import APP_DIR, router as frontend_router

app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="frontend_assets")
app.include_router(frontend_router)
```

## API 연결 표

2주차 PDF의 `/api/v1` 규격과 `username` 기반 프로필 경로를 적용했습니다. 예시였던 값과 추가로 정한 값은 백엔드와 연결할 때 확인합니다.

| 화면·동작 | 브라우저가 보내는 요청 | FastAPI 응답과 화면 반영 |
|---|---|---|
| 로그인 | `POST /auth/login`, JSON `{username,password}` | `200`과 `{user}`, HttpOnly 세션 쿠키 설정 → 타임라인 |
| 회원가입 | `POST /auth/signup`, JSON `{username,password,name}` | `201`과 `{user}` → 로그인 |
| 내 계정 확인 | `GET /users/me` | `200`과 사용자 객체 자체 → 사용자 사진·본인 여부 표시 |
| 로그아웃 | `POST /auth/logout` | 세션 무효화 및 쿠키 삭제, `204` → 로그인 |
| 비밀번호 변경 | `PATCH /users/me/password`, JSON `{current_password,new_password}` | `204` → 설정 |
| 프로필 편집 | `PATCH /users/me`, multipart `name,username,bio`, 선택 `profile_image` | `200`과 갱신된 사용자 → 내 프로필 재조회 |
| 피드 | `GET /feed?limit=20` | `200`과 게시물 목록 → 내 게시물과 팔로잉 사용자의 게시물 표시 |
| 게시물 상세 | `GET /posts/{post_id}` | `200`과 게시물 객체 → 사진·본문·좋아요 상태 표시. 댓글은 별도로 조회 |
| 게시물 작성·삭제 | `POST /posts`, multipart `content`와 동일한 이름의 반복 필드 `images`. 삭제는 `DELETE /posts/{post_id}` | 작성 `201`과 게시물 → 타임라인. 본인 게시물 삭제 `204` → 화면에서 제거 |
| 좋아요·취소 | `POST` 또는 `DELETE /posts/{post_id}/likes` | `200`과 `{like_count,liked_by_me}` → 하트와 수 갱신. 성공 응답이 `204`면 상세를 재조회 |
| 댓글 조회·작성 | `GET /posts/{post_id}/comments`, 작성은 같은 경로에 `POST`와 JSON `{content}` | 조회 `200`과 댓글 목록. 작성 `201`과 댓글 객체 자체 → 화면에 추가 |
| 댓글 삭제 | `DELETE /comments/{comment_id}` | 본인 댓글 삭제 `204` → 화면에서 제거 |
| 계정 검색 | `GET /search/users?q=seojin` | `200`과 `{items}`. 결과를 선택하면 `/users/{username}`으로 이동 |
| 프로필 | `GET /users/{username}`, `GET /users/{username}/posts` | `200`과 각각 `{user,counts,followed_by_me}`, 게시물 목록 → 프로필·격자 |
| 팔로워·팔로잉 | `GET /users/{username}/followers`, `GET /users/{username}/following` | `200`과 사용자 목록. 탭 숫자는 프로필 응답의 `counts` 사용 |
| 팔로우·취소 | `POST` 또는 `DELETE /users/{username}/follow` | `200`과 `{followed_by_me,counts}` → 버튼·팔로워 수 갱신. 성공 응답이 `204`면 프로필을 재조회 |

위 요청에는 모두 `/api/v1`을 붙입니다. HTML 화면 경로는 `/login`, `/signup`, `/timeline`, `/search`, `/me`, `/users/{username}`과 그 하위 팔로우 화면, `/users/me/edit`, `/posts/upload`, `/posts/{post_id}`, `/posts/{post_id}/comments`, `/setting`, `/setting/password`입니다.

### 데이터 형태

- 계정 검색은 로그인 상태에서 `user.user_username`을 대소문자 구분 없이 부분 일치로 찾습니다. 본인 계정은 결과에서 제외하고, 정확히 일치하는 아이디 → 검색어로 시작하는 아이디 → 나머지 부분 일치 순으로 최대 20건을 반환합니다. 항목은 `{id,username,name,profile_image_url}`이고 빈 검색어 또는 결과가 없으면 `{"items":[]}`입니다. 별도 경로인 `/api/v1/search/users`를 사용합니다.
- 사용자 객체는 `{id,username,name,bio,profile_image_url}`입니다. 사진이 없으면 `profile_image_url: null`입니다. 개인 프로필 화면의 링크에는 `username`을 쓰며, `me`는 고정 경로입니다. 백엔드는 세션 사용자와 URL의 대상 사용자·게시물을 구분합니다.
- 게시물 객체는 `{id,author,content,created_at,like_count,comment_count,liked_by_me,image_urls}`입니다. 사진 여러 장은 업로드 순서대로 `image_urls`에 담습니다. 현재 프론트는 단일 `image_url`도 표시할 수 있습니다. 피드가 팔로우하지 않은 작성자를 포함한다면 `author.followed_by_me`를 제공합니다.
- 댓글 객체는 `{id,author,content,created_at}`입니다. DB의 `comment_content`는 API의 `content`로 변환합니다. 댓글 목록 순서는 최신 ID 우선입니다.
- 페이지로 나누는 목록의 응답은 `{items,next_cursor}`입니다. 더 보기에서 서버가 준 커서를 전달하며 마지막 페이지의 커서는 `null`입니다. 날짜는 ISO 8601 UTC, ID와 집계 값은 정수, 좋아요와 팔로우 상태는 불리언입니다.
- 로그인 응답에 세션 쿠키를 설정합니다. 댓글·좋아요·팔로우의 실행 사용자는 쿠키 세션에서 확인합니다. 비밀번호 확인 필드는 프론트에서 비교하고 가입·변경 요청에는 실제 비밀번호 필드만 전달합니다.
- 사진 요청은 `FormData`로 전송합니다. 게시물 사진은 최대 10장이고 캡션은 최대 2,000자, 댓글은 최대 1,000자입니다. 게시물 사진은 브라우저에서 중앙을 정사각형으로 자르고 1080×1080 픽셀 파일로 변환합니다. 미리보기와 업로드는 같은 변환 파일을 사용합니다. 백엔드는 수신한 파일의 형식과 크기를 검증하고, 이미지 저장과 권한 확인을 처리합니다.
- 오류 응답 예시는 `{"error":{"code":"POST_NOT_FOUND","message":"게시물을 찾을 수 없어요."}}`입니다. `401`은 로그인 필요 또는 인증 실패, `403`은 권한 없음, `404`는 대상 없음, `409`는 아이디 중복, `422`는 입력 검증 실패에 사용합니다.

## 댓글·좋아요 쿼리 연결

`sql/queries/comments.sql`과 `sql/queries/post_likes.sql`의 각 문장은 백엔드에서 개별 실행하는 PyMySQL용 쿼리입니다. `%s` 자리에 값을 문자열로 합치지 말고 별도로 전달합니다. 작성자와 좋아요 사용자는 로그인 세션에서 확인합니다. 댓글 생성과 생성된 댓글 조회는 같은 연결에서 실행하고 성공 시 커밋합니다. 목록에 다음 페이지가 있는지 확인하려면 요청 수량보다 한 건 더 조회한 뒤 초과 행을 반환에서 제외합니다.
