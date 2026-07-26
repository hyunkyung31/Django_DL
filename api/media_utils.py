import os
from datetime import timedelta
from typing import Optional
from urllib.parse import quote

from django.conf import settings


def _gcs_enabled() -> bool:
    return bool(getattr(settings, "GCS_MEDIA_BUCKET", "") or "")


def save_media_file(patient_id: str, media_type: str, uploaded_file) -> str:
    """
    파일을 GCS 또는 로컬 MEDIA_ROOT에 저장하고 DB에 넣을 path 문자열을 반환.
    media_type: key_frame | video | gradcam
    """
    filename = os.path.basename(uploaded_file.name)
    relative = f"patients/{patient_id}/{media_type}/{filename}"

    if _gcs_enabled():
        from google.cloud import storage

        client = storage.Client(project=getattr(settings, "GCS_PROJECT", None) or None)
        bucket = client.bucket(settings.GCS_MEDIA_BUCKET)
        blob = bucket.blob(relative)
        uploaded_file.seek(0)
        blob.upload_from_file(
            uploaded_file,
            content_type=getattr(uploaded_file, "content_type", None) or "application/octet-stream",
        )
        return f"gs://{settings.GCS_MEDIA_BUCKET}/{relative}"

    dest = os.path.join(settings.MEDIA_ROOT, relative.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    uploaded_file.seek(0)
    with open(dest, "wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
    return relative.replace("\\", "/")


def build_media_url(request, stored_path: Optional[str]) -> Optional[str]:
    """DB에 저장된 path를 프론트가 쓸 수 있는 URL로 변환."""
    if not stored_path:
        return None

    path = stored_path.strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path

    if path.startswith("gs://"):
        return request.build_absolute_uri(f"/api/media/gcs/?path={quote(path)}")

    # 로컬 media 상대경로 → 인증된 프록시 URL
    return request.build_absolute_uri(f"/api/media/local/?path={quote(path)}")


def _signed_gcs_url(gs_uri: str) -> Optional[str]:
    # gs://bucket/object/key
    without = gs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    if not bucket_name or not blob_name:
        return None
    try:
        from google.cloud import storage

        client = storage.Client(project=getattr(settings, "GCS_PROJECT", None) or None)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
        )
    except Exception:
        # 서명 실패 시 프록시로 폴백할 수도 있지만, 일단 None
        return None


def resolve_local_media_path(relative_path: str) -> Optional[str]:
    """경로 traversal 방지 후 절대경로 반환."""
    if not relative_path or ".." in relative_path or relative_path.startswith(("/", "\\")):
        return None
    full = os.path.normpath(os.path.join(settings.MEDIA_ROOT, relative_path.replace("/", os.sep)))
    media_root = os.path.normpath(settings.MEDIA_ROOT)
    if not full.startswith(media_root):
        return None
    if not os.path.isfile(full):
        return None
    return full
