import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import uuid
from backend.config import settings

router = APIRouter()

UPLOAD_DIR = "uploads"

# 업로드 디렉토리가 없으면 생성 (절대경로 처리)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_PATH = os.path.join(BASE_DIR, UPLOAD_DIR)
if not os.path.exists(UPLOAD_PATH):
    os.makedirs(UPLOAD_PATH)

# 크롤러 이미지 전용 디렉토리
CRAWLED_PATH = os.path.join(UPLOAD_PATH, "crawled")
if not os.path.exists(CRAWLED_PATH):
    os.makedirs(CRAWLED_PATH)

# 허용 확장자/용량 제한 (B2: 악성 파일 업로드 차단 — SVG/HTML 등 실행가능 포맷 거부)
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB


async def _save_image(file: UploadFile) -> dict:
    """단일 이미지 또는 동영상 파일 저장 공통 로직"""
    is_image = file.content_type and file.content_type.startswith("image/")
    is_video = file.content_type and file.content_type.startswith("video/")

    if not is_image and not is_video:
        raise HTTPException(
            status_code=400,
            detail=f"이미지 또는 동영상 파일만 업로드 가능합니다: {file.filename}"
        )

    ext = os.path.splitext(file.filename or "")[1].lower()
    if not ext:
        ext = ".mp4" if is_video else ".jpg"

    # 확장자 화이트리스트 검증 (content-type 은 위조 가능하므로 확장자도 함께 제한)
    allowed_ext = ALLOWED_VIDEO_EXT if is_video else ALLOWED_IMAGE_EXT
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"허용되지 않은 파일 형식입니다({ext}). 허용: {', '.join(sorted(allowed_ext))}"
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 까지 업로드 가능합니다."
        )

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_PATH, unique_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    file_url = f"{settings.BACKEND_URL}/uploads/{unique_filename}"
    return {
        "url": file_url,
        "filename": unique_filename,
        "original_filename": file.filename,
        "size": len(content),
    }


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """단일 이미지 업로드"""
    try:
        result = await _save_image(file)
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multiple")
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    """
    다중 이미지 업로드 (최대 10장)
    - 프론트에서 드래그앤드롭으로 여러 파일을 한번에 올릴 때 사용
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="최대 10장까지 업로드 가능합니다.")

    results = []
    errors = []

    for file in files:
        try:
            result = await _save_image(file)
            results.append(result)
        except HTTPException as e:
            errors.append({"filename": file.filename, "error": e.detail})
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    return JSONResponse(status_code=200, content={
        "uploaded": results,
        "errors": errors,
        "total_uploaded": len(results),
        "total_errors": len(errors),
    })
