from datetime import timedelta
from functools import lru_cache

from minio import Minio
from minio.commonconfig import CopySource

from src.config.settings import settings


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )


def ensure_bucket_exists(bucket: str | None = None) -> None:
    client = get_minio_client()
    bucket = bucket or settings.minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _to_public_url(url: str) -> str:
    """Rewrite an internally-signed MinIO URL to the browser-reachable public
    endpoint (nginx proxies /storage -> minio:9000).

    The SigV4 signature stays valid because nginx forwards to MinIO with the
    original Host header (minio:9000) and the same path/query.
    """
    scheme = "https" if settings.minio_secure else "http"
    internal_base = f"{scheme}://{settings.minio_endpoint}"
    return url.replace(internal_base, settings.minio_public_url, 1)


def get_presigned_upload_url(
    object_name: str,
    bucket: str | None = None,
    expiry_seconds: int | None = None,
) -> str:
    """Return a presigned PUT URL for direct browser upload."""
    client = get_minio_client()
    return _to_public_url(
        client.presigned_put_object(
            bucket_name=bucket or settings.minio_bucket,
            object_name=object_name,
            expires=timedelta(seconds=expiry_seconds or settings.minio_presigned_expiry),
        )
    )


def get_presigned_download_url(
    object_name: str,
    bucket: str | None = None,
    expiry_seconds: int | None = None,
) -> str:
    """Return a presigned GET URL for temporary download access."""
    client = get_minio_client()
    return _to_public_url(
        client.presigned_get_object(
            bucket_name=bucket or settings.minio_bucket,
            object_name=object_name,
            expires=timedelta(seconds=expiry_seconds or settings.minio_presigned_expiry),
        )
    )


def delete_object(object_name: str, bucket: str | None = None) -> None:
    client = get_minio_client()
    client.remove_object(bucket or settings.minio_bucket, object_name)


def copy_object(src_object: str, dst_object: str, bucket: str | None = None) -> None:
    client = get_minio_client()
    b = bucket or settings.minio_bucket
    client.copy_object(b, dst_object, CopySource(b, src_object))


def object_exists(object_name: str, bucket: str | None = None) -> bool:
    client = get_minio_client()
    try:
        client.stat_object(bucket or settings.minio_bucket, object_name)
        return True
    except Exception:
        return False
