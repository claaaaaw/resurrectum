"""
7z Compression Module

Provides file compression/decompression using 7z format for efficient
capsule storage (typically 60-80% space savings for text files).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Lazy import check for py7zr
_HAS_7Z: Optional[bool] = None


def _check_7z_available() -> bool:
    """Check if py7zr is available."""
    global _HAS_7Z
    if _HAS_7Z is None:
        try:
            import py7zr  # noqa: F401
            _HAS_7Z = True
        except ImportError:
            _HAS_7Z = False
    return _HAS_7Z


class CompressionError(RuntimeError):
    """Raised when compression/decompression fails."""
    pass


@dataclass(frozen=True)
class CompressionOptions:
    """
    Compression configuration options.
    
    Attributes:
        enabled: Whether compression is enabled
        algorithm: Compression algorithm (currently only "7z" is supported)
        level: Compression level 0-9 (9 = maximum compression)
    """
    enabled: bool = True
    algorithm: str = "7z"
    level: int = 9
    
    def __post_init__(self) -> None:
        """Validate options."""
        if self.enabled and not _check_7z_available():
            raise CompressionError(
                "py7zr is required for 7z compression. "
                "Install with: pip install py7zr"
            )
        if self.algorithm != "7z":
            raise CompressionError(f"Unsupported compression algorithm: {self.algorithm}")
        if not 0 <= self.level <= 9:
            raise CompressionError(f"Compression level must be 0-9, got: {self.level}")


@dataclass
class CompressionResult:
    """
    Result of a compression operation.
    
    Attributes:
        archive_data: Compressed archive bytes
        original_size: Total size of original files in bytes
        compressed_size: Size of compressed archive in bytes
        file_count: Number of files compressed
    """
    archive_data: bytes
    original_size: int
    compressed_size: int
    file_count: int
    
    @property
    def compression_ratio(self) -> float:
        """
        Calculate compression ratio.
        
        Returns:
            Ratio of compressed to original size (lower is better).
            Returns 1.0 if original size is 0.
        """
        if self.original_size == 0:
            return 1.0
        return self.compressed_size / self.original_size
    
    @property
    def space_saved_percent(self) -> float:
        """
        Calculate percentage of space saved.
        
        Returns:
            Percentage saved (e.g., 70.0 means 70% smaller)
        """
        return (1.0 - self.compression_ratio) * 100


def compress_files(
    workspace: Path,
    file_paths: list[str],
    options: CompressionOptions,
) -> CompressionResult:
    """
    Compress files into a 7z archive.
    
    Args:
        workspace: Workspace root directory
        file_paths: List of relative file paths to compress
        options: Compression configuration
    
    Returns:
        CompressionResult with archive data and statistics
    
    Raises:
        CompressionError: If compression fails
    """
    if not options.enabled:
        raise CompressionError("Compression is disabled")
    
    if not file_paths:
        raise CompressionError("No files to compress")
    
    import py7zr
    
    original_size = 0
    buffer = io.BytesIO()
    
    try:
        # Create 7z archive in memory
        with py7zr.SevenZipFile(buffer, mode="w") as archive:
            for rel_path in file_paths:
                full_path = workspace / rel_path
                if full_path.is_file():
                    file_data = full_path.read_bytes()
                    original_size += len(file_data)
                    # Add to archive maintaining relative path structure
                    archive.writestr(file_data, rel_path)
    except Exception as exc:
        raise CompressionError(f"Failed to create archive: {exc}") from exc
    
    archive_data = buffer.getvalue()
    
    return CompressionResult(
        archive_data=archive_data,
        original_size=original_size,
        compressed_size=len(archive_data),
        file_count=len(file_paths),
    )


def decompress_archive(
    archive_data: bytes,
    target_dir: Path,
    expected_files: Optional[list[str]] = None,
) -> list[str]:
    """
    Decompress a 7z archive.
    
    Args:
        archive_data: Compressed archive bytes
        target_dir: Directory to extract files to
        expected_files: Optional list of expected files for validation
    
    Returns:
        List of extracted file paths (relative to target_dir)
    
    Raises:
        CompressionError: If decompression fails or validation fails
    """
    if not _check_7z_available():
        raise CompressionError(
            "py7zr is required for 7z decompression. "
            "Install with: pip install py7zr"
        )
    
    import py7zr
    
    buffer = io.BytesIO(archive_data)
    extracted_files: list[str] = []
    
    try:
        with py7zr.SevenZipFile(buffer, mode="r") as archive:
            # Get all file names
            names = archive.getnames()
            
            # Optional: validate file list
            if expected_files is not None:
                expected_set = set(expected_files)
                actual_set = set(names)
                if expected_set != actual_set:
                    missing = expected_set - actual_set
                    extra = actual_set - expected_set
                    raise CompressionError(
                        f"Archive content mismatch. "
                        f"Missing: {missing}, Extra: {extra}"
                    )
            
            # Extract all files
            archive.extractall(path=target_dir)
            extracted_files = names
    except py7zr.Bad7zFile as exc:
        raise CompressionError(f"Invalid 7z archive: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, CompressionError):
            raise
        raise CompressionError(f"Failed to extract archive: {exc}") from exc
    
    return extracted_files


def estimate_compression_ratio(sample_data: bytes) -> float:
    """
    Estimate compression ratio based on a sample.
    
    Useful for dry-run estimation without compressing all data.
    
    Args:
        sample_data: Sample data to estimate compression on
    
    Returns:
        Estimated compression ratio (compressed/original)
    """
    if not _check_7z_available():
        return 0.5  # Default estimate when py7zr unavailable
    
    if len(sample_data) < 1024:
        return 0.5  # Default estimate for small files
    
    import py7zr
    
    # Use a sample of up to 64KB for estimation
    sample_size = min(len(sample_data), 65536)
    sample = sample_data[:sample_size]
    
    try:
        buffer = io.BytesIO()
        with py7zr.SevenZipFile(buffer, mode="w") as archive:
            archive.writestr(sample, "sample")
        
        compressed = len(buffer.getvalue())
        return compressed / sample_size if sample_size > 0 else 1.0
    except Exception:  # noqa: BLE001
        return 0.5  # Default estimate on error


def get_compression_info() -> dict:
    """
    Get information about compression support.
    
    Returns:
        Dict with compression availability and version info
    """
    info = {
        "available": _check_7z_available(),
        "algorithm": "7z",
    }
    
    if info["available"]:
        import py7zr
        info["py7zr_version"] = py7zr.__version__
    
    return info
