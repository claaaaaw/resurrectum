from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol


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
        path = (self.root / ref).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Path traversal detected: {ref}")
        return path.read_bytes()

    def has_blob(self, ref: str) -> bool:
        path = (self.root / ref).resolve()
        if not path.is_relative_to(self.root.resolve()):
            return False
        return path.is_file()

    def put_document(self, capsule_id: str, path: str, data: bytes) -> None:
        target = self.capsule_root(capsule_id) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(target, data)

    def get_document(self, capsule_id: str, path: str) -> bytes:
        target = (self.capsule_root(capsule_id) / path).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ValueError(f"Path traversal detected: {path}")
        return target.read_bytes()

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
        try:
            with tmp.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise


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
        with response["Body"] as body:
            return body.read()

    def has_blob(self, ref: str) -> bool:
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            ClientError = Exception  # type: ignore[misc]
        client = self._client()
        try:
            client.head_object(Bucket=self.bucket, Key=ref)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "") if hasattr(e, "response") else ""
            if error_code in ("404", "NoSuchKey"):
                return False
            raise
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
        with response["Body"] as body:
            return body.read()

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
        raise RuntimeError(f"Read-after-write check failed for key: {key}")


# ============ Helper Functions ============


def _base64url_encode(data: bytes) -> str:
    """Base64url encode (no padding)."""
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# ============ Presigned URL Backend ============


@dataclass
class PresignedUrlBackend:
    """
    Remote storage backend using Presigned URLs via credential service.
    
    Workflow:
    1. Client signs request -> Credential service
    2. Credential service validates -> Returns Presigned URLs
    3. Client uses URLs to directly access R2/S3
    
    Attributes:
        credential_service_url: URL of the credential service (e.g., https://api.resurrectum.dev)
        signing_key_path: Path to the Ed25519 signing key file
    """
    
    credential_service_url: str
    signing_key_path: Path
    
    # Internal URL cache (in-memory)
    _url_cache: dict[str, tuple[dict, float]] = field(
        default_factory=dict, repr=False, compare=False
    )
    _cache_buffer_seconds: float = 300  # Refresh 5 minutes before expiration
    
    def _get_presigned_urls(
        self,
        capsule_id: str,
        action: str,
        blobs: Optional[list[str]] = None,
    ) -> dict:
        """
        Get presigned URLs with caching.
        
        Note: Write requests typically aren't cached since blob lists may change.
        """
        # For read, try cache first
        if action == "read":
            cache_key = f"{capsule_id}:read"
            if cache_key in self._url_cache:
                urls, expires_at = self._url_cache[cache_key]
                if time.time() < expires_at - self._cache_buffer_seconds:
                    return urls
        
        # Request new presigned URLs
        result = self._request_presigned_urls(capsule_id, action, blobs)
        
        # Cache read URLs
        if action == "read":
            cache_key = f"{capsule_id}:read"
            self._url_cache[cache_key] = (result["urls"], result["expires_at"])
        
        return result["urls"]
    
    def _request_presigned_urls(
        self,
        capsule_id: str,
        action: str,
        blobs: Optional[list[str]] = None,
    ) -> dict:
        """Request presigned URLs from credential service."""
        from ..sigil.crypto import (
            get_public_key_from_private,
            load_signing_key,
            sign_message,
        )
        
        timestamp = int(time.time())
        message = f"{capsule_id}:{action}:{timestamp}"
        
        signing_key = load_signing_key(self.signing_key_path)
        signature = sign_message(message.encode("utf-8"), signing_key)
        public_key = get_public_key_from_private(signing_key)
        
        payload = {
            "capsule_id": capsule_id,
            "action": action,
            "timestamp": timestamp,
            "signature": _base64url_encode(signature),
            "public_key": _base64url_encode(public_key),
        }
        if blobs:
            payload["blobs"] = blobs
        
        req = urllib.request.Request(
            f"{self.credential_service_url}/presign",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(
                f"Credential service error: {e.code} - {error_body}"
            ) from e
    
    # ============ StorageBackend Protocol Implementation ============
    
    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        """Upload blob to R2 using presigned URL."""
        urls = self._get_presigned_urls(capsule_id, "write", blobs=[blob_id])
        url = urls.get("blobs", {}).get(blob_id)
        if not url:
            raise RuntimeError(f"No presigned URL for blob: {blob_id}")
        
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/octet-stream")
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Upload failed: {resp.status}")
        
        return f"capsules/{capsule_id}/blobs/{blob_id}"
    
    def get_blob(self, ref: str) -> bytes:
        """Download blob from R2 using presigned URL."""
        # ref format: capsules/{owner_fp}/{uuid}/blobs/{blob_id}
        parts = ref.split("/")
        if len(parts) < 5:
            raise ValueError(f"Invalid blob reference: {ref}")
        # capsule_id = owner_fp/uuid
        capsule_id = f"{parts[1]}/{parts[2]}"
        blob_id = parts[-1]
        
        urls = self._get_presigned_urls(capsule_id, "read")
        url = urls.get("blobs", {}).get(blob_id)
        if not url:
            raise RuntimeError(f"No presigned URL for blob: {blob_id}")
        
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    
    def has_blob(self, ref: str) -> bool:
        """Check if blob exists."""
        try:
            # Try to get presigned URL - if it exists, blob should exist
            parts = ref.split("/")
            if len(parts) < 5:
                return False
            capsule_id = f"{parts[1]}/{parts[2]}"
            blob_id = parts[-1]
            urls = self._get_presigned_urls(capsule_id, "read")
            return blob_id in urls.get("blobs", {})
        except Exception:  # noqa: BLE001
            return False
    
    def put_document(self, capsule_id: str, path: str, data: bytes) -> None:
        """Upload document (manifest/report) using presigned URL."""
        urls = self._get_presigned_urls(capsule_id, "write", blobs=[])
        
        # Map path to URL key
        if path in ("manifest.json", "capsule.manifest.json"):
            url = urls.get("manifest")
        elif path == "redaction.report.json":
            url = urls.get("redaction_report")
        else:
            raise RuntimeError(f"Unknown document path: {path}")
        
        if not url:
            raise RuntimeError(f"No presigned URL for document: {path}")
        
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Upload failed: {resp.status}")
    
    def get_document(self, capsule_id: str, path: str) -> bytes:
        """Download document using presigned URL."""
        urls = self._get_presigned_urls(capsule_id, "read")
        
        if path in ("manifest.json", "capsule.manifest.json"):
            url = urls.get("manifest")
        elif path == "redaction.report.json":
            url = urls.get("redaction_report")
        else:
            raise RuntimeError(f"Unknown document path: {path}")
        
        if not url:
            raise RuntimeError(f"No presigned URL for document: {path}")
        
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    
    def list(self, capsule_id: str, prefix: str) -> list[str]:
        """List objects under prefix."""
        urls = self._get_presigned_urls(capsule_id, "read")
        
        if prefix.startswith("blobs"):
            # Return all blob keys
            return [
                f"capsules/{capsule_id}/blobs/{blob_id}"
                for blob_id in urls.get("blobs", {}).keys()
            ]
        
        return []
