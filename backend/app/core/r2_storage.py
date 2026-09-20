"""Small async-friendly Cloudflare R2 storage adapter."""

import asyncio
from urllib.parse import quote

from app.core.config import Settings


class R2Storage:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.r2_endpoint
            and self.settings.r2_bucket
            and self.settings.r2_access_key_id
            and self.settings.r2_secret_access_key
            and self.settings.r2_public_base_url
        )

    def public_url(self, key: str) -> str:
        return f"{self.settings.r2_public_base_url.rstrip('/')}/{quote(key, safe='/')}"

    def _client(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("R2 support is not installed.") from exc
        return boto3.client(
            "s3",
            endpoint_url=self.settings.r2_endpoint,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4", max_pool_connections=4),
        )

    async def put(self, key: str, body: bytes, content_type: str) -> None:
        def write() -> None:
            self._client().put_object(
                Bucket=self.settings.r2_bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        await asyncio.to_thread(write)

    async def delete(self, key: str) -> None:
        def remove() -> None:
            self._client().delete_object(Bucket=self.settings.r2_bucket, Key=key)
        await asyncio.to_thread(remove)


def get_r2_storage(settings: Settings) -> R2Storage:
    return R2Storage(settings)