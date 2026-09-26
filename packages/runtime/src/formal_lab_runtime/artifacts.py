"""ArtifactStore implementations: local filesystem and S3-compatible object storage.

Objects are content-addressed (sha256); `put` is idempotent and `get` verifies the digest, so artifacts
referenced from events and bundles cannot silently change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from formal_lab_contracts import ArtifactRef, Digest
from formal_lab_contracts.errors import InvalidInput, NotFound, RetryableFailure

from .settings import get_setting


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify(ref: ArtifactRef, data: bytes) -> bytes:
    if _digest(data) != ref.digest.value:
        raise InvalidInput(f"artifact {ref.uri} does not match its digest")
    return data


class LocalArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha: str) -> Path:
        return self.root / sha[:2] / sha

    def put(self, data: bytes, *, name: str, media_type: str, format_version: str) -> ArtifactRef:
        sha = _digest(data)
        path = self._path(sha)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return ArtifactRef(uri=path.as_uri(), media_type=media_type, size_bytes=len(data), digest=Digest(value=sha),
                           format_version=format_version, name=name)

    def get(self, ref: ArtifactRef) -> bytes:
        path = self._path(ref.digest.value)
        if not path.exists():
            raise NotFound(f"artifact {ref.digest.value} not in local store {self.root}")
        return _verify(ref, path.read_bytes())

    def describe(self) -> dict[str, Any]:
        return {"backend": "local", "root": str(self.root)}


class S3ArtifactStore:
    def __init__(self, *, bucket: str, endpoint_url: str | None, access_key: str | None, secret_key: str | None,
                 region: str = "us-east-1", prefix: str = "artifacts/"):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.prefix = prefix
        self.endpoint_url = endpoint_url
        self.client = boto3.client(
            "s3", endpoint_url=endpoint_url, aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            region_name=region, config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                                              retries={"max_attempts": 3}))

    def ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, data: bytes, *, name: str, media_type: str, format_version: str) -> ArtifactRef:
        from botocore.exceptions import BotoCoreError, ClientError

        sha = _digest(data)
        key = f"{self.prefix}{sha[:2]}/{sha}"
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=media_type,
                                   Metadata={"sha256": sha, "format-version": format_version, "name": name[:200]})
        except (BotoCoreError, ClientError) as exc:
            raise RetryableFailure(f"object store put failed: {exc}") from exc
        return ArtifactRef(uri=f"s3://{self.bucket}/{key}", media_type=media_type, size_bytes=len(data),
                           digest=Digest(value=sha), format_version=format_version, name=name)

    def get(self, ref: ArtifactRef) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        sha = ref.digest.value
        key = f"{self.prefix}{sha[:2]}/{sha}"
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey as exc:
            raise NotFound(f"artifact {sha} not in bucket {self.bucket}") from exc
        except (BotoCoreError, ClientError) as exc:
            raise RetryableFailure(f"object store get failed: {exc}") from exc
        return _verify(ref, obj["Body"].read())

    def describe(self) -> dict[str, Any]:
        return {"backend": "s3", "bucket": self.bucket, "endpoint": self.endpoint_url}


def store_from_settings() -> LocalArtifactStore | S3ArtifactStore:
    backend = get_setting("FAL_ARTIFACT_BACKEND", "local")
    if backend == "s3":
        store = S3ArtifactStore(
            bucket=get_setting("FAL_S3_BUCKET", "formal-lab-artifacts") or "formal-lab-artifacts",
            endpoint_url=get_setting("FAL_S3_ENDPOINT_URL"),
            access_key=get_setting("FAL_S3_ACCESS_KEY_ID"),
            secret_key=get_setting("FAL_S3_SECRET_ACCESS_KEY"),
            region=get_setting("FAL_S3_REGION", "us-east-1") or "us-east-1",
        )
        store.ensure_bucket()
        return store
    if backend != "local":
        raise InvalidInput(f"unknown FAL_ARTIFACT_BACKEND {backend!r}")
    return LocalArtifactStore(get_setting("FAL_ARTIFACT_ROOT", "./var/artifacts") or "./var/artifacts")
