"""
Presigned URL Cache Module

Provides persistent caching for presigned URLs to enable cross-process reuse
and reduce requests to the credential service.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PresignedUrlCache:
    """
    Presigned URL persistent cache.
    
    Used for cross-process URL reuse to reduce credential service requests.
    URLs are cached to disk and validated against expiration times.
    """
    
    cache_dir: Path = field(
        default_factory=lambda: Path.home() / ".resurrectum" / "cache"
    )
    buffer_seconds: int = 300  # Refresh 5 minutes before expiration
    
    def __post_init__(self) -> None:
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_path(self, capsule_id: str) -> Path:
        """
        Get cache file path for a capsule.
        
        Args:
            capsule_id: Capsule ID in format "owner_fp/uuid"
        
        Returns:
            Path to the cache file
        """
        # capsule_id format: owner_fp/uuid - replace "/" with "_" for filename
        safe_id = capsule_id.replace("/", "_")
        return self.cache_dir / f"urls_{safe_id}.json"
    
    def get(self, capsule_id: str) -> Optional[dict]:
        """
        Get cached presigned URLs for a capsule.
        
        Args:
            capsule_id: Capsule ID in format "owner_fp/uuid"
        
        Returns:
            Cached URLs dict if valid, None if expired or not found
        """
        path = self._cache_path(capsule_id)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            expires_at = data.get("expires_at", 0)
            
            # Check if still valid (with buffer)
            if time.time() < expires_at - self.buffer_seconds:
                return data.get("urls")
            
            # Expired, delete cache file
            path.unlink(missing_ok=True)
            return None
            
        except (json.JSONDecodeError, TypeError, KeyError, OSError):
            # Corrupted cache, delete it
            path.unlink(missing_ok=True)
            return None
    
    def set(self, capsule_id: str, urls: dict, expires_at: int) -> None:
        """
        Store presigned URLs in cache.
        
        Args:
            capsule_id: Capsule ID in format "owner_fp/uuid"
            urls: Dict of presigned URLs
            expires_at: Unix timestamp when URLs expire
        """
        path = self._cache_path(capsule_id)
        cache_data = {
            "urls": urls,
            "expires_at": expires_at,
            "cached_at": int(time.time()),
        }
        path.write_text(
            json.dumps(cache_data, indent=2, sort_keys=True),
            encoding="utf-8"
        )
        # Set secure permissions (cross-platform)
        self._set_secure_permissions(path)
    
    def clear(self, capsule_id: Optional[str] = None) -> None:
        """
        Clear cached URLs.
        
        Args:
            capsule_id: If provided, clear only this capsule's cache.
                       If None, clear all cached URLs.
        """
        if capsule_id:
            self._cache_path(capsule_id).unlink(missing_ok=True)
        else:
            for path in self.cache_dir.glob("urls_*.json"):
                path.unlink(missing_ok=True)
    
    def list_cached(self) -> list[dict]:
        """
        List all cached URL entries with metadata.
        
        Returns:
            List of dicts with cache info (capsule_id, expires_at, status)
        """
        results = []
        for path in self.cache_dir.glob("urls_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                expires_at = data.get("expires_at", 0)
                remaining = int(expires_at - time.time())
                # Reconstruct capsule_id from filename
                capsule_id = path.stem.replace("urls_", "").replace("_", "/", 1)
                results.append({
                    "capsule_id": capsule_id,
                    "expires_at": expires_at,
                    "remaining_seconds": remaining,
                    "status": "valid" if remaining > 0 else "expired",
                })
            except (json.JSONDecodeError, OSError):
                results.append({
                    "capsule_id": path.stem.replace("urls_", "").replace("_", "/", 1),
                    "status": "corrupted",
                })
        return results
    
    def _set_secure_permissions(self, path: Path) -> None:
        """
        Set secure file permissions (cross-platform).
        
        On Unix: chmod 600 (owner read/write only)
        On Windows: Default permissions are user-level isolated
        """
        if os.name != "nt":  # Unix/Linux/macOS
            path.chmod(0o600)
        # Windows: Default permissions are already secure (user-level isolation)
