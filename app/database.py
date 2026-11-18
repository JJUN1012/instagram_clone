import os
from pathlib import Path
from uuid import uuid4
import mysql.connector
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from supabase import create_client

# 프로젝트 루트(instagram_clone)의 .env 파일 로드
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Supabase Storage 설정
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
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 최대 5MB


def get_db():
    """Aiven MySQL DB 연결을 생성하고 요청이 끝나면 자동으로 닫아주는 의존성 함수"""
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
    """이미지 파일을 검증 후 Supabase Storage에 업로드하고 Public URL을 반환"""
    content_type = file.content_type or ""
    extension = IMAGE_EXTENSIONS.get(content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail="JPEG, PNG, WebP만 업로드할 수 있습니다.")

    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="사진은 최대 5MB까지 업로드할 수 있습니다.")

    path = f"{folder}/{uuid4().hex}{extension}"
    bucket.upload(path, data, file_options={"content-type": content_type})
    return bucket.get_public_url(path)