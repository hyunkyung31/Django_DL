import mimetypes
import os
from datetime import timedelta
from typing import Optional, Tuple
from urllib.parse import quote

from django.conf import settings


def _gcs_enabled() -> bool:
    return bool(getattr(settings, "GCS_MEDIA_BUCKET", "") or "")


def _gcs_client():
    from google.cloud import storage

    return storage.Client(project=getattr(settings, "GCS_PROJECT", None) or None)


def save_media_file(patient_id: str, media_type: str, uploaded_file) -> str:
    """
    파일을 GCS 또는 로컬 MEDIA_ROOT에 저장하고 DB에 넣을 path 문자열을 반환.
    media_type: key_frame | video | gradcam
    """
    filename = os.path.basename(uploaded_file.name)
    content_type = (
        getattr(uploaded_file, "content_type", None) or "application/octet-stream"
    )
    uploaded_file.seek(0)
    content = uploaded_file.read()
    return save_media_bytes(
        patient_id=patient_id,
        media_type=media_type,
        filename=filename,
        content=content,
        content_type=content_type,
    )


def save_media_bytes(
    patient_id: str,
    media_type: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """bytes를 GCS/로컬에 저장하고 DB path를 반환한다."""
    safe_name = os.path.basename(filename)
    relative = f"patients/{patient_id}/{media_type}/{safe_name}"

    if _gcs_enabled():
        client = _gcs_client()
        bucket = client.bucket(settings.GCS_MEDIA_BUCKET)
        blob = bucket.blob(relative)
        blob.upload_from_string(content, content_type=content_type)
        return f"gs://{settings.GCS_MEDIA_BUCKET}/{relative}"

    dest = os.path.join(settings.MEDIA_ROOT, relative.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        out.write(content)
    return relative.replace("\\", "/")


def download_media_bytes(stored_path: Optional[str]) -> Tuple[bytes, str, str]:
    """
    DB에 저장된 path에서 파일 bytes를 읽는다.
    지원 형식:
      - gs://bucket/object/key
      - patients/... (로컬 MEDIA_ROOT 상대경로)
      - /media/... 또는 media/... (레거시 절대/상대 경로)
    """
    if not stored_path or not str(stored_path).strip():
        raise FileNotFoundError("저장된 미디어 경로가 비어 있습니다.")

    path = str(stored_path).strip()

    if path.startswith("gs://"):
        without = path[5:]
        bucket_name, _, blob_name = without.partition("/")
        if not bucket_name or not blob_name:
            raise FileNotFoundError(f"잘못된 GCS 경로입니다: {path}")

        client = _gcs_client()
        blob = client.bucket(bucket_name).blob(blob_name)
        if not blob.exists():
            raise FileNotFoundError(f"GCS 객체를 찾을 수 없습니다: {path}")

        content = blob.download_as_bytes()
        filename = os.path.basename(blob_name) or "image.png"
        content_type = blob.content_type or (
            mimetypes.guess_type(filename)[0] or "application/octet-stream"
        )
        return content, filename, content_type

    normalized = path.replace("\\", "/")
    if normalized.startswith("/media/"):
        normalized = normalized[len("/media/") :]
    elif normalized.startswith("media/"):
        normalized = normalized[len("media/") :]
    elif normalized.startswith("/"):
        if os.path.isfile(path):
            filename = os.path.basename(path)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            with open(path, "rb") as f:
                return f.read(), filename, content_type
        raise FileNotFoundError(f"로컬 파일을 찾을 수 없습니다: {path}")

    local = resolve_local_media_path(normalized)
    if local is None:
        raise FileNotFoundError(f"로컬 미디어를 찾을 수 없습니다: {path}")

    filename = os.path.basename(local)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(local, "rb") as f:
        return f.read(), filename, content_type


def build_media_url(request, stored_path: Optional[str]) -> Optional[str]:
    """DB에 저장된 path를 프론트가 쓸 수 있는 URL로 변환."""
    if not stored_path:
        return None

    path = stored_path.strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path

    if path.startswith("gs://"):
        return request.build_absolute_uri(f"/api/media/gcs/?path={quote(path)}")

    return request.build_absolute_uri(f"/api/media/local/?path={quote(path)}")


def _signed_gcs_url(gs_uri: str) -> Optional[str]:
    without = gs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    if not bucket_name or not blob_name:
        return None
    try:
        client = _gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
        )
    except Exception:
        return None


def resolve_local_media_path(relative_path: str) -> Optional[str]:
    """경로 traversal 방지 후 절대경로 반환."""
    if not relative_path or ".." in relative_path or relative_path.startswith(("/", "\\")):
        return None
    full = os.path.normpath(
        os.path.join(settings.MEDIA_ROOT, relative_path.replace("/", os.sep))
    )
    media_root = os.path.normpath(str(settings.MEDIA_ROOT))
    if not full.startswith(media_root):
        return None
    if not os.path.isfile(full):
        return None
    return full