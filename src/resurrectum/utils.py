from __future__ import annotations

import base64
import hashlib
import os
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_relpath(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    posix = PurePosixPath(rel.as_posix())
    if posix.is_absolute():
        raise ValueError(f"Path must be relative: {posix}")
    if any(part == ".." for part in posix.parts):
        raise ValueError(f"Path must not contain '..': {posix}")
    normalized = unicodedata.normalize("NFC", str(posix))
    if "\\" in normalized:
        raise ValueError(f"Path must not contain backslashes: {normalized}")
    return normalized


@dataclass(frozen=True)
class UuidV7:
    value: str

    def __str__(self) -> str:
        return self.value


def uuidv7() -> UuidV7:
    ts_ms = int(time.time() * 1000)
    time_bytes = ts_ms.to_bytes(6, "big")
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = (rand >> 68) & 0x0FFF
    rand_b = (rand >> 6) & ((1 << 62) - 1)

    byte6 = 0x70 | ((rand_a >> 8) & 0x0F)
    byte7 = rand_a & 0xFF
    byte8 = 0x80 | ((rand_b >> 56) & 0x3F)
    bytes9_15 = (rand_b & ((1 << 56) - 1)).to_bytes(7, "big")

    raw = bytearray()
    raw.extend(time_bytes)
    raw.append(byte6)
    raw.append(byte7)
    raw.append(byte8)
    raw.extend(bytes9_15)
    hexed = raw.hex()
    uuid = f"{hexed[0:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:32]}"
    return UuidV7(uuid)
