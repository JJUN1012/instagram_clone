import os
from functools import lru_cache
from pathlib import Path
from uuid import uuid4
import mysql.connector
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from supabase import create_client

# ???? ??(instagram_clone)? .env ?? ??
BASE_DIR = Path(__file__).resolve().parent.parent
QUERIES_DIR = BASE_DIR / "sql" / "queries"
load_dotenv(BASE_DIR / ".env")

# Supabase Storage ??
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)
bucket = supabase.storage.from_(os.environ["SUPABASE_BUCKET"])

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # ?? 5MB


@lru_cache(maxsize=None)
def _parse_sql_file(filename: str) -> dict[str, str]:
    """sql/queries/*.sql ??? ?? '-- name: ????' ???? ??"""
    sql_path = QUERIES_DIR / filename
    text = sql_path.read_text(encoding="utf-8")
    queries: dict[str, str] = {}
    current_name: str | None = None
    buffer: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if current_name and buffer:
                queries[current_name] = "\n".join(buffer).strip().rstrip(";")
            current_name = stripped.split(":", 1)[1].strip()
            buffer = []
        elif current_name is not None:
            buffer.append(line)

    if current_name and buffer:
        queries[current_name] = "\n".join(buffer).strip().rstrip(";")

    return queries


def load_query(filename: str, query_name: str) -> str:
    """sql/queries/ ??? ??? SQL ??? ???? ??"""
    return _parse_sql_file(filename)[query_name]


def get_db():
    """Aiven MySQL DB ??? ???? ??? ??? ???? ???? ??? ??"""
    conn = mysql.connector.connect(
        host=os.environ["INSTAGRAM_APP_HOST"],
        port=int(os.environ["INSTAGRAM_APP_PORT"]),
        user=os.environ["INSTAGRAM_APP_USER"],
        password=os.environ["INSTAGRAM_APP_PW"],
        database="instagram",
        ssl_ca=str(BASE_DIR / os.environ["INSTAGRAM_APP_CA"]),
    )
    try:
        yield conn
    finally:
        conn.close()


def upload_image_to_supabase(file: UploadFile, folder: str = "posts") -> str:
    """??? ??? ?? ? Supabase Storage? ????? Public URL? ??"""
    content_type = file.content_type or ""
    extension = IMAGE_EXTENSIONS.get(content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail="JPEG, PNG, WebP? ???? ? ????.")

    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="? ?????.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="??? ?? 5MB?? ???? ? ????.")

    path = f"{folder}/{uuid4().hex}{extension}"
    bucket.upload(path, data, file_options={"content-type": content_type})
    return bucket.get_public_url(path)
