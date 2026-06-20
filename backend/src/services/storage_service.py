import uuid

from src.config.settings import settings
from src.db.minio import (
    delete_object,
    get_presigned_download_url,
    get_presigned_upload_url,
    object_exists,
)


def build_object_name(user_id: str, filename: str) -> str:
    """Namespaced object key: <user_id>/<uuid>/<filename>"""
    return f"{user_id}/{uuid.uuid4()}/{filename}"


def generate_upload_url(object_name: str, expiry: int | None = None) -> str:
    return get_presigned_upload_url(object_name, expiry_seconds=expiry)


def generate_download_url(object_name: str, expiry: int | None = None) -> str:
    return get_presigned_download_url(object_name, expiry_seconds=expiry)


def remove_object(object_name: str) -> None:
    if object_exists(object_name):
        delete_object(object_name)


def get_public_url(object_name: str) -> str:
    """Return the internal MinIO URL (not presigned — only usable server-side)."""
    return f"http://{settings.minio_endpoint}/{settings.minio_bucket}/{object_name}"
