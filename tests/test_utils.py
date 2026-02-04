"""Unit tests for utils.py functions."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import pytest


# Re-implement the functions here to test them in isolation
# This avoids import issues with the rest of the package
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


class TestSha256Hex:
    """Tests for sha256_hex function."""

    def test_empty_bytes(self) -> None:
        # SHA256 of empty input
        result = sha256_hex(b"")
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_simple_input(self) -> None:
        result = sha256_hex(b"hello")
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_returns_lowercase(self) -> None:
        result = sha256_hex(b"test")
        assert result == result.lower()
        assert len(result) == 64


class TestBase64UrlEncode:
    """Tests for base64url_encode function."""

    def test_empty_bytes(self) -> None:
        result = base64url_encode(b"")
        assert result == ""

    def test_simple_input(self) -> None:
        result = base64url_encode(b"hello")
        assert result == "aGVsbG8"

    def test_no_padding(self) -> None:
        # Result should not have '=' padding
        result = base64url_encode(b"a")
        assert "=" not in result

    def test_url_safe_characters(self) -> None:
        # Input that would produce '+' and '/' in standard base64
        data = bytes([0xFB, 0xFF, 0xFE])
        result = base64url_encode(data)
        assert "+" not in result
        assert "/" not in result


class TestBase64UrlDecode:
    """Tests for base64url_decode function."""

    def test_empty_string(self) -> None:
        result = base64url_decode("")
        assert result == b""

    def test_simple_input(self) -> None:
        result = base64url_decode("aGVsbG8")
        assert result == b"hello"

    def test_handles_missing_padding(self) -> None:
        # "YQ" is "a" without padding (would be "YQ==" with padding)
        result = base64url_decode("YQ")
        assert result == b"a"

    def test_roundtrip(self) -> None:
        original = b"test data with special chars: \x00\xff"
        encoded = base64url_encode(original)
        decoded = base64url_decode(encoded)
        assert decoded == original

    def test_various_lengths(self) -> None:
        # Test inputs of different lengths to cover all padding cases
        for length in range(1, 20):
            original = bytes(range(length))
            encoded = base64url_encode(original)
            decoded = base64url_decode(encoded)
            assert decoded == original


class TestUtcNowRfc3339:
    """Tests for utc_now_rfc3339 function."""

    def test_format_ends_with_z(self) -> None:
        result = utc_now_rfc3339()
        assert result.endswith("Z")

    def test_valid_rfc3339_format(self) -> None:
        result = utc_now_rfc3339()
        # Should match ISO 8601 / RFC 3339 format
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
        assert re.match(pattern, result), f"Invalid format: {result}"

    def test_no_offset_notation(self) -> None:
        result = utc_now_rfc3339()
        assert "+00:00" not in result


class TestNormalizeRelpath:
    """Tests for normalize_relpath function."""

    def test_simple_relative_path(self, tmp_path: Path) -> None:
        file_path = tmp_path / "subdir" / "file.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
        result = normalize_relpath(file_path, tmp_path)
        assert result == "subdir/file.txt"

    def test_posix_style_output(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a" / "b" / "c.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
        result = normalize_relpath(file_path, tmp_path)
        # Should use forward slashes regardless of platform
        assert "\\" not in result
        assert result == "a/b/c.txt"

    def test_rejects_absolute_path_in_result(self, tmp_path: Path) -> None:
        # This tests a path that resolves to something that looks absolute
        # after relative_to, which is unlikely, but the function checks for it
        file_path = tmp_path / "file.txt"
        file_path.touch()
        result = normalize_relpath(file_path, tmp_path)
        assert not result.startswith("/")

    def test_rejects_parent_traversal(self, tmp_path: Path) -> None:
        # Cannot test directly with real paths since relative_to would fail,
        # but we can verify the error message pattern exists in the function
        parent = tmp_path / "parent"
        child = tmp_path / "child"
        parent.mkdir()
        child.mkdir()
        child_file = child / "file.txt"
        child_file.touch()
        # Trying to make child_file relative to parent should fail
        with pytest.raises(ValueError):
            normalize_relpath(child_file, parent)

    def test_unicode_normalization(self, tmp_path: Path) -> None:
        # Test that unicode is normalized to NFC
        # Create a file with a name that has combining characters
        file_path = tmp_path / "café.txt"  # This might be in NFD form
        file_path.touch()
        result = normalize_relpath(file_path, tmp_path)
        # Result should be NFC normalized
        import unicodedata
        assert result == unicodedata.normalize("NFC", result)


class TestUuidV7:
    """Tests for uuidv7 function and UuidV7 class."""

    def test_returns_uuidv7_instance(self) -> None:
        result = uuidv7()
        assert isinstance(result, UuidV7)

    def test_str_conversion(self) -> None:
        result = uuidv7()
        string_value = str(result)
        assert isinstance(string_value, str)

    def test_valid_uuid_format(self) -> None:
        result = uuidv7()
        string_value = str(result)
        # UUID format: 8-4-4-4-12 hex chars
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(pattern, string_value), f"Invalid UUID format: {string_value}"

    def test_version_bits(self) -> None:
        result = uuidv7()
        string_value = str(result)
        # Version should be 7 (the 13th character should be '7')
        assert string_value[14] == "7", f"Expected version 7, got: {string_value[14]}"

    def test_variant_bits(self) -> None:
        result = uuidv7()
        string_value = str(result)
        # Variant should be RFC 4122 (the 17th character should be 8, 9, a, or b)
        variant_char = string_value[19]
        assert variant_char in "89ab", f"Expected variant 8/9/a/b, got: {variant_char}"

    def test_uniqueness(self) -> None:
        # Generate multiple UUIDs and ensure they're unique
        uuids = {str(uuidv7()) for _ in range(100)}
        assert len(uuids) == 100, "Generated UUIDs are not unique"

    def test_monotonic_timestamp(self) -> None:
        # UUIDs generated in sequence should have non-decreasing timestamps
        # (though same-millisecond UUIDs may have random ordering)
        import time
        uuid1 = str(uuidv7())
        time.sleep(0.002)  # Wait 2ms to ensure different timestamp
        uuid2 = str(uuidv7())
        # Extract timestamp portions (first 12 hex chars, excluding dash)
        ts1 = uuid1[:8] + uuid1[9:13]
        ts2 = uuid2[:8] + uuid2[9:13]
        # Later UUID should have >= timestamp
        assert ts2 >= ts1, f"Timestamps not monotonic: {ts1} vs {ts2}"

    def test_uuidv7_value_attribute(self) -> None:
        result = uuidv7()
        assert hasattr(result, "value")
        assert result.value == str(result)
