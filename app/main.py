import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile
from supabase import create_client

app = FastAPI()
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
MAX_IMAGE_BYTES = 2 * 1024 * 1024


@app.post("/images", status_code=201)
def upload_image(file: UploadFile):
    content_type = file.content_type or ""
    extension = IMAGE_EXTENSIONS.get(content_type)
    if extension is None:
        raise HTTPException(415, "JPEG, PNG, WebP만 업로드할 수 있습니다.")

    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(400, "빈 파일입니다.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "사진은 최대 2MB까지 업로드할 수 있습니다.")

    path = f"posts/{uuid4().hex}{extension}"
    bucket.upload(path, data, file_options={"content-type": content_type})

    return {"path": path, "url": bucket.get_public_url(path)}