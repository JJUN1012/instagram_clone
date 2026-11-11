import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/db-test")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 100
MYSQL_ERROR_MESSAGES = {
    1044: "instagram 데이터베이스에 대한 계정 권한을 확인해 주세요.",
    1045: "Aiven 사용자 이름과 비밀번호를 확인해 주세요.",
    1049: "Aiven 서비스에 instagram 데이터베이스가 있는지 확인해 주세요.",
    1142: "테스트 테이블의 조회, 추가, 삭제 권한을 확인해 주세요.",
    1146: "관리자 계정으로 aiven_test_setup.sql을 먼저 실행해 주세요.",
}


class DatabaseTestError(Exception):
    pass


@contextmanager
def test_cursor():
    try:
        import pymysql
    except ImportError as error:
        raise DatabaseTestError('py -m pip install "PyMySQL[rsa]"를 실행해 주세요.') from error

    try:
        host = os.environ["INSTAGRAM_APP_HOST"]
        port = int(os.environ["INSTAGRAM_APP_PORT"])
        user = os.environ["INSTAGRAM_APP_USER"]
        password = os.environ["INSTAGRAM_APP_PW"]
        ca_file = Path(os.environ["INSTAGRAM_APP_CA"]).expanduser()
    except KeyError as error:
        raise DatabaseTestError(f".env에 {error.args[0]} 값을 설정해 주세요.") from error
    except ValueError as error:
        raise DatabaseTestError("INSTAGRAM_APP_PORT에는 Aiven 포트 번호를 입력해 주세요.") from error

    if not 1 <= port <= 65535:
        raise DatabaseTestError("INSTAGRAM_APP_PORT에는 Aiven 포트 번호를 입력해 주세요.")
    if not ca_file.is_file():
        raise DatabaseTestError("INSTAGRAM_APP_CA가 Aiven CA 인증서 파일을 가리키는지 확인해 주세요.")

    try:
        with pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="instagram",
            charset="utf8mb4",
            ssl_ca=str(ca_file),
            ssl_verify_cert=True,
            ssl_verify_identity=True,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        ) as connection:
            with connection.cursor() as cursor:
                yield cursor
    except (pymysql.MySQLError, OSError) as error:
        code = error.args[0] if error.args and isinstance(error.args[0], int) else None
        logger.warning("Aiven MySQL test failed (%s, code %s)", type(error).__name__, code)
        message = MYSQL_ERROR_MESSAGES.get(code, "Aiven 주소, 포트, CA 인증서와 네트워크를 확인해 주세요.")
        raise DatabaseTestError(message) from error


def render_db_test(request, *, items=(), error=None, status_code=200):
    return templates.TemplateResponse(
        request=request,
        name="db_test.html",
        context={"items": items, "error": error, "max_name_length": MAX_NAME_LENGTH},
        status_code=status_code,
    )


def database_test_error_page(request: Request, error: DatabaseTestError):
    return render_db_test(request, error=str(error), status_code=503)


@router.get("", response_class=HTMLResponse)
def db_test_page(request: Request):
    with test_cursor() as cursor:
        cursor.execute("SELECT id, name FROM aiven_test_items ORDER BY id DESC")
        items = cursor.fetchall()
    return render_db_test(request, items=items)


@router.post("/items", response_class=RedirectResponse, status_code=303)
def add_db_test_item(request: Request, name: Annotated[str, Form()] = ""):
    name = name.strip()
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        return render_db_test(
            request,
            error=f"항목 이름을 1~{MAX_NAME_LENGTH}자로 입력해 주세요.",
            status_code=400,
        )

    with test_cursor() as cursor:
        cursor.execute("INSERT INTO aiven_test_items (name) VALUES (%s)", (name,))
    return RedirectResponse(request.url_for("db_test_page").path, status_code=303)


@router.post("/items/{item_id}/delete", response_class=RedirectResponse, status_code=303)
def delete_db_test_item(request: Request, item_id: int):
    with test_cursor() as cursor:
        cursor.execute("DELETE FROM aiven_test_items WHERE id = %s", (item_id,))
    return RedirectResponse(request.url_for("db_test_page").path, status_code=303)
