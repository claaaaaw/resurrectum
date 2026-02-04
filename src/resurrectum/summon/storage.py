from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        ...

    def get_blob(self, ref: str) -> bytes:
        ...

    def has_blob(self, ref: str) -> bool:
        ...

    def put_document(self, capsule_id: str, path: str, data: bytes) -> None:
        ...

    def get_document(self, capsule_id: str, path: str) -> bytes:
        ...

    def list(self, capsule_id: str, prefix: str) -> list[str]:
        ...


@dataclass(frozen=True)
class LocalDirBackend:
    root: Path

    def capsule_root(self, capsule_id: str) -> Path:
        return self.root / "capsules" / capsule_id

    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        blobs_dir = self.capsule_root(capsule_id) / "blobs"
        blobs_dir.mkdir(parents=True, exist_ok=True)
        target = blobs_dir / blob_id
        self._atomic_write(target, data)
        rel = Path("capsules") / capsule_id / "blobs" / blob_id
        return rel.as_posix()

    def get_blob(self, ref: str) -> bytes:
        path = self.root / ref
        return path.read_bytes()

    def has_blob(self, ref: str) -> bool:
        return (self.root / ref).is_file()

    def put_document(self, capsule_id: str, path: str, data: bytes) -> None:
        target = self.capsule_root(capsule_id) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(target, data)

    def get_document(self, capsule_id: str, path: str) -> bytes:
        return (self.capsule_root(capsule_id) / path).read_bytes()

    def list(self, capsule_id: str, prefix: str) -> list[str]:
        base = self.capsule_root(capsule_id)
        root = base / prefix
        if not root.exists():
            return []
        paths = []
        for item in root.rglob("*"):
            if item.is_file():
                paths.append(item.relative_to(base).as_posix())
        return sorted(paths)

    def _atomic_write(self, path: Path, data: bytes) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)


@dataclass(frozen=True)
class S3Backend:
    bucket: str
    prefix: str = ""
    region: str | None = None
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    read_after_write_retries: int = 3
    read_after_write_delay: float = 0.5

    def _client(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for S3Backend.") from exc

        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            aws_session_token=self.session_token,
        )

    def _key(self, capsule_id: str, path: str) -> str:
        prefix = self.prefix.strip("/")
        base = f"capsules/{capsule_id}/{path.lstrip('/')}"
        if not prefix:
            return base
        return f"{prefix}/{base}"

    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        key = self._key(capsule_id, f"blobs/{blob_id}")
        client = self._client()
        client.put_object(Bucket=self.bucket, Key=key, Body=data)
        self._ensure_read_after_write(client, key)
        return key

    def get_blob(self, ref: str) -> bytes:
        client = self._client()
        response = client.get_object(Bucket=self.bucket, Key=ref)
        return response["Body"].read()

    def has_blob(self, ref: str) -> bool:
        client = self._client()
        try:
            client.head_object(Bucket=self.bucket, Key=ref)
            return True
        except Exception:  # noqa: BLE001
            return False

    def put_document(self, capsule_id: str, path: str, data: bytes) -> None:
        key = self._key(capsule_id, path)
        client = self._client()
        client.put_object(Bucket=self.bucket, Key=key, Body=data)
        self._ensure_read_after_write(client, key)

    def get_document(self, capsule_id: str, path: str) -> bytes:
        key = self._key(capsule_id, path)
        client = self._client()
        response = client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def list(self, capsule_id: str, prefix: str) -> list[str]:
        client = self._client()
        key_prefix = self._key(capsule_id, prefix).rstrip("/") + "/"
        paginator = client.get_paginator("list_objects_v2")
        results: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=key_prefix):
            for entry in page.get("Contents", []):
                results.append(entry["Key"])
        return sorted(results)

    def _ensure_read_after_write(self, client, key: str) -> None:
        for _ in range(self.read_after_write_retries):
            try:
                client.head_object(Bucket=self.bucket, Key=key)
                return
            except Exception:  # noqa: BLE001
                time.sleep(self.read_after_write_delay)
