from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..sigil.crypto import (
    Argon2Params,
    CryptoError,
    SignatureError,
    blob_id_for_ciphertext,
    decrypt_payload,
    derive_master_key,
    encrypt_payload,
    get_fingerprint,
    sign_manifest,
    verify_manifest_signature,
)
from ..spec.models import CapsuleManifest, RedactionReport, RestoreReport
from ..spec.redaction import RedactionPolicy
from ..spec.schemas import SchemaValidationError
from .compression import (
    CompressionError,
    CompressionOptions,
    CompressionResult,
    compress_files,
    decompress_archive,
)
from .storage import LocalDirBackend, PresignedUrlBackend, S3Backend, StorageBackend
from ..utils import base64url_decode, base64url_encode, sha256_hex, utc_now_rfc3339, uuidv7


class CapsuleError(RuntimeError):
    exit_code: int = 1


class PolicyViolationError(CapsuleError):
    exit_code = 2


class SchemaInvalidError(CapsuleError):
    exit_code = 3


class SignatureInvalidError(CapsuleError):
    exit_code = 4


class BlobInvalidError(CapsuleError):
    exit_code = 5


class DecryptFailedError(CapsuleError):
    exit_code = 6


class RestoreFailedError(CapsuleError):
    exit_code = 7


@dataclass(frozen=True)
class AccessControl:
    """
    Access control configuration for a capsule.
    
    Attributes:
        owner: Owner's public key fingerprint (required)
        readers: List of authorized reader fingerprints
        public: Whether the capsule is publicly accessible
    """
    owner: str
    readers: list[str] = field(default_factory=list)
    public: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to manifest-compatible dict."""
        result: dict[str, Any] = {
            "owner": f"ed25519:{self.owner}",
        }
        if self.readers:
            result["readers"] = [f"ed25519:{r}" for r in self.readers]
        result["public"] = self.public
        return result


@dataclass(frozen=True)
class ExportOptions:
    workspace: Path
    backend: StorageBackend
    passphrase: str | None
    signing_key_pem: bytes | None
    policy: RedactionPolicy
    aead: str = "xchacha20-poly1305"
    argon2_params: Argon2Params = field(default_factory=Argon2Params)
    strict: bool = True
    dry_run: bool = False
    # New fields for v1.1
    compression: CompressionOptions = field(default_factory=lambda: CompressionOptions(enabled=False))
    access: Optional[AccessControl] = None


@dataclass(frozen=True)
class ImportOptions:
    capsule_id: str
    backend: StorageBackend
    target_workspace: Path
    passphrase: str
    trusted_fingerprints: set[str]
    overwrite: bool = False
    partial: bool = False
    restore_report_path: Path | None = None


@dataclass(frozen=True)
class ValidateOptions:
    capsule_id: str
    backend: StorageBackend
    trusted_fingerprints: set[str]
    passphrase: str | None = None


def export_capsule(options: ExportOptions) -> tuple[str, dict[str, Any]]:
    """
    Export a workspace to an encrypted capsule.
    
    Args:
        options: Export configuration options
    
    Returns:
        Tuple of (capsule_id, manifest)
    
    Raises:
        CapsuleError: If export fails
        PolicyViolationError: If forbidden content is found in strict mode
    """
    # Generate capsule_id in owner_fp/uuid format
    capsule_id = _generate_capsule_id(options.signing_key_pem)
    
    report = options.policy.scan_workspace(options.workspace)
    report["capsule_id"] = capsule_id

    if options.strict and any(decision["class"] == "forbidden" for decision in report["decisions"]):
        _write_redaction_report(options.backend, capsule_id, report)
        raise PolicyViolationError("Forbidden findings detected in strict mode.")

    if options.dry_run:
        _write_redaction_report(options.backend, capsule_id, report)
        RedactionReport.from_dict(report)
        return capsule_id, report

    if not options.passphrase or not options.signing_key_pem:
        raise CapsuleError("Passphrase and signing key are required for export.")

    master_salt = _random_salt()
    master_key = derive_master_key(options.passphrase, master_salt, options.argon2_params)

    # Collect files to include
    included_files = [
        d["path"] for d in report["decisions"]
        if d["decision"] != "exclude"
    ]

    artifacts: list[dict[str, Any]] = []
    blobs: list[dict[str, Any]] = []
    compression_info: dict[str, Any] = {"enabled": False}

    if options.compression.enabled and included_files:
        # === 7z Compression Mode ===
        try:
            compress_result = compress_files(
                workspace=options.workspace,
                file_paths=included_files,
                options=options.compression,
            )
        except CompressionError as exc:
            raise CapsuleError(f"Compression failed: {exc}") from exc
        
        # Encrypt the compressed archive
        nonce, ciphertext = encrypt_payload(compress_result.archive_data, master_key, options.aead)
        blob_id = blob_id_for_ciphertext(ciphertext)
        ref = options.backend.put_blob(capsule_id, blob_id, ciphertext)
        
        # Single blob entry (compressed archive)
        blobs.append({
            "blob_id": blob_id,
            "ciphertext_hash": blob_id,
            "ciphertext_size_bytes": len(ciphertext),
            "nonce": base64url_encode(nonce),
            "storage": {"backend": _backend_name(options.backend), "ref": ref},
            "is_archive": True,
            "archive_format": "7z",
        })
        
        # Artifacts still list all files (for metadata)
        for decision in report["decisions"]:
            if decision["decision"] == "exclude":
                continue
            rel_path = decision["path"]
            full_path = options.workspace / rel_path
            payload = full_path.read_bytes()
            artifacts.append({
                "path": rel_path,
                "kind": artifact_kind(rel_path),
                "mode": decision["decision"],
                "plaintext_hash": sha256_hex(payload),
                "size_bytes": len(payload),
                "blob_id": blob_id,  # All files point to same archive blob
            })
        
        compression_info = {
            "enabled": True,
            "algorithm": options.compression.algorithm,
            "level": options.compression.level,
            "original_size_bytes": compress_result.original_size,
            "compressed_size_bytes": compress_result.compressed_size,
            "compression_ratio": round(compress_result.compression_ratio, 4),
        }
    else:
        # === Original Mode: Each file encrypted separately ===
        for decision in report["decisions"]:
            if decision["decision"] == "exclude":
                continue
            rel_path = decision["path"]
            full_path = options.workspace / rel_path
            payload = full_path.read_bytes()
            plaintext_hash = sha256_hex(payload)
            nonce, ciphertext = encrypt_payload(payload, master_key, options.aead)
            blob_id = blob_id_for_ciphertext(ciphertext)
            ref = options.backend.put_blob(capsule_id, blob_id, ciphertext)
            blobs.append({
                "blob_id": blob_id,
                "ciphertext_hash": blob_id,
                "ciphertext_size_bytes": len(ciphertext),
                "nonce": base64url_encode(nonce),
                "storage": {"backend": _backend_name(options.backend), "ref": ref},
            })
            artifacts.append({
                "path": rel_path,
                "kind": artifact_kind(rel_path),
                "mode": decision["decision"],
                "plaintext_hash": plaintext_hash,
                "size_bytes": len(payload),
                "blob_id": blob_id,
            })

    manifest = build_manifest(
        capsule_id=capsule_id,
        aead=options.aead,
        salt=master_salt,
        params=options.argon2_params,
        artifacts=artifacts,
        blobs=blobs,
        policy_version=options.policy.policy_version,
        compression=compression_info,
        access=options.access,
    )
    manifest["signature"] = sign_manifest(manifest, options.signing_key_pem)

    CapsuleManifest.from_dict(manifest)
    RedactionReport.from_dict(report)

    _write_redaction_report(options.backend, capsule_id, report)
    _write_manifest(options.backend, capsule_id, manifest)
    return capsule_id, manifest


def import_capsule(options: ImportOptions) -> dict[str, Any]:
    """
    Import a workspace from an encrypted capsule.
    
    Args:
        options: Import configuration options
    
    Returns:
        Restore report dict
    
    Raises:
        CapsuleError: If import fails
    """
    manifest = _load_manifest(options.backend, options.capsule_id)
    _ensure_supported_spec_version(manifest)
    _ensure_signature_present(manifest)
    try:
        CapsuleManifest.from_dict(manifest)
    except SchemaValidationError as exc:
        raise SchemaInvalidError(str(exc)) from exc

    _verify_manifest_or_raise(manifest, options.trusted_fingerprints)

    master_key, aead = _derive_master_key_from_manifest(manifest, options.passphrase)

    results: dict[str, list] = {"created": [], "skipped": [], "overwritten": [], "failed": []}
    
    # Check if capsule uses compression
    compression = manifest.get("compression", {})
    is_compressed = compression.get("enabled", False)
    
    if is_compressed:
        # === Compressed Mode: Single archive blob ===
        # Find the archive blob
        archive_blob = None
        for blob in manifest["blobs"]:
            if blob.get("is_archive"):
                archive_blob = blob
                break
        
        if not archive_blob:
            raise BlobInvalidError("Compressed capsule missing archive blob.")
        
        try:
            ciphertext = options.backend.get_blob(archive_blob["storage"]["ref"])
        except FileNotFoundError as exc:
            raise BlobInvalidError("Missing archive blob.") from exc
        
        if sha256_hex(ciphertext) != archive_blob["blob_id"]:
            raise BlobInvalidError("Archive ciphertext hash mismatch.")
        
        nonce = base64url_decode(archive_blob["nonce"])
        try:
            archive_data = decrypt_payload(ciphertext, master_key, nonce, aead)
        except CryptoError as exc:
            raise DecryptFailedError("Failed to decrypt archive.") from exc
        
        # Extract archive to target workspace
        try:
            expected_files = [a["path"] for a in manifest["artifacts"]]
            decompress_archive(archive_data, options.target_workspace, expected_files)
        except CompressionError as exc:
            raise RestoreFailedError(f"Failed to extract archive: {exc}") from exc
        
        # Verify extracted files and build results
        for artifact in manifest["artifacts"]:
            path = artifact["path"]
            target = options.target_workspace / path
            
            if not target.exists():
                results["failed"].append({"path": path, "error": "File not extracted"})
                continue
            
            # Verify hash
            extracted_data = target.read_bytes()
            if sha256_hex(extracted_data) != artifact["plaintext_hash"]:
                results["failed"].append({"path": path, "error": "Plaintext hash mismatch"})
                continue
            
            results["created"].append({
                "path": path,
                "size_bytes": len(extracted_data),
                "plaintext_hash": artifact["plaintext_hash"],
            })
    else:
        # === Original Mode: Each file decrypted separately ===
        for artifact in manifest["artifacts"]:
            path = artifact["path"]
            target = options.target_workspace / path
            existed = target.exists()
            if existed and not options.overwrite:
                results["skipped"].append({"path": path, "reason": "exists"})
                continue
            try:
                blob_entry = _lookup_blob(manifest, artifact["blob_id"])
                try:
                    ciphertext = options.backend.get_blob(blob_entry["storage"]["ref"])
                except FileNotFoundError as exc:
                    raise BlobInvalidError("Missing blob.") from exc
                if sha256_hex(ciphertext) != blob_entry["blob_id"]:
                    raise BlobInvalidError("Ciphertext hash mismatch.")
                nonce = base64url_decode(blob_entry["nonce"])
                try:
                    plaintext = decrypt_payload(ciphertext, master_key, nonce, aead)
                except CryptoError as exc:
                    raise DecryptFailedError("Decrypt failed.") from exc
                if sha256_hex(plaintext) != artifact["plaintext_hash"]:
                    raise BlobInvalidError("Plaintext hash mismatch.")
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(plaintext)
                except OSError as exc:
                    raise RestoreFailedError("Failed to write restored file.") from exc
                entry = {"path": path, "size_bytes": len(plaintext), "plaintext_hash": artifact["plaintext_hash"]}
                if existed and options.overwrite:
                    results["overwritten"].append({**entry, "reason": "overwrite"})
                else:
                    results["created"].append(entry)
            except CapsuleError as exc:
                if options.partial:
                    results["failed"].append({"path": path, "error": str(exc)})
                    continue
                raise

    report = build_restore_report(options.capsule_id, options.target_workspace, results)
    if options.restore_report_path:
        RestoreReport.from_dict(report)
        options.restore_report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def validate_capsule(options: ValidateOptions) -> None:
    manifest = _load_manifest(options.backend, options.capsule_id)
    _ensure_supported_spec_version(manifest)
    _ensure_signature_present(manifest)
    try:
        CapsuleManifest.from_dict(manifest)
    except SchemaValidationError as exc:
        raise SchemaInvalidError(str(exc)) from exc

    _verify_manifest_or_raise(manifest, options.trusted_fingerprints)

    for blob in manifest["blobs"]:
        try:
            ciphertext = options.backend.get_blob(blob["storage"]["ref"])
        except FileNotFoundError as exc:
            raise BlobInvalidError("Missing blob.") from exc
        if sha256_hex(ciphertext) != blob["blob_id"]:
            raise BlobInvalidError("Ciphertext hash mismatch.")

    if options.passphrase:
        master_key, aead = _derive_master_key_from_manifest(manifest, options.passphrase)
        for artifact in manifest["artifacts"]:
            blob_entry = _lookup_blob(manifest, artifact["blob_id"])
            try:
                ciphertext = options.backend.get_blob(blob_entry["storage"]["ref"])
            except FileNotFoundError as exc:
                raise BlobInvalidError("Missing blob.") from exc
            nonce = base64url_decode(blob_entry["nonce"])
            try:
                plaintext = decrypt_payload(ciphertext, master_key, nonce, aead)
            except CryptoError as exc:
                raise DecryptFailedError("Decrypt failed.") from exc
            if sha256_hex(plaintext) != artifact["plaintext_hash"]:
                raise BlobInvalidError("Plaintext hash mismatch.")


def build_manifest(
    capsule_id: str,
    aead: str,
    salt: bytes,
    params: Argon2Params,
    artifacts: list[dict[str, Any]],
    blobs: list[dict[str, Any]],
    policy_version: str,
    compression: Optional[dict[str, Any]] = None,
    access: Optional[AccessControl] = None,
) -> dict[str, Any]:
    """
    Build a capsule manifest.
    
    Args:
        capsule_id: Capsule ID (format: owner_fp/uuid or uuid)
        aead: AEAD algorithm name
        salt: KDF salt
        params: Argon2 parameters
        artifacts: List of artifact entries
        blobs: List of blob entries
        policy_version: Redaction policy version
        compression: Optional compression info dict
        access: Optional access control configuration
    
    Returns:
        Manifest dict
    """
    manifest: dict[str, Any] = {
        "spec_version": "v1",
        "schema_version": "1.1.0",  # Updated for new features
        "capsule_id": capsule_id,
        "created_at": utc_now_rfc3339(),
        "tool": _tool_info(),
        "crypto": {
            "aead": aead,
            "kdf": "hkdf-sha256",
            "key_source": "passphrase_argon2id",
            "hkdf_info": "capsule:blob",
            "kdf_params": {
                "alg": "argon2id",
                "salt": base64url_encode(salt),
                **params.to_dict(),
            },
        },
        "artifacts": artifacts,
        "blobs": blobs,
        "redaction": {"report_path": "redaction.report.json", "policy_version": policy_version},
        "signature": {},
    }
    
    # Add compression info if provided
    if compression:
        manifest["compression"] = compression
    
    # Add access control if provided
    if access:
        manifest["access"] = access.to_dict()
    
    return manifest


def build_restore_report(capsule_id: str, target_workspace: Path, results: dict[str, Any]) -> dict[str, Any]:
    return {
        "spec_version": "v1",
        "schema_version": "1.0.0",
        "created_at": utc_now_rfc3339(),
        "capsule_id": capsule_id,
        "target_workspace": str(target_workspace),
        "results": results,
    }


def artifact_kind(rel_path: str) -> str:
    posix = Path(rel_path)
    if rel_path.startswith("memory/") or rel_path == "MEMORY.md":
        return "memory"
    if posix.name in {"SOUL.md", "USER.md", "IDENTITY.md"}:
        return "persona"
    if posix.name in {"AGENTS.md", "TOOLS.md", "HEARTBEAT.md"}:
        return "ops"
    if rel_path.endswith("STATUS.md") and rel_path.startswith("projects/"):
        return "project"
    return "other"


def _tool_info() -> dict[str, str]:
    return {"name": "resurrectum", "version": "0.1.0"}


def _backend_name(backend: StorageBackend) -> str:
    """Get backend name string for manifest."""
    if isinstance(backend, LocalDirBackend):
        return "local_dir"
    if isinstance(backend, S3Backend):
        return "s3"
    if isinstance(backend, PresignedUrlBackend):
        return "presigned_url"
    raise CapsuleError(f"Unknown backend type: {type(backend).__name__}")


def _generate_capsule_id(signing_key_pem: bytes | None) -> str:
    """
    Generate a capsule ID in owner_fp/uuid format.
    
    Args:
        signing_key_pem: PEM-encoded signing key (optional for dry run)
    
    Returns:
        Capsule ID in format "owner_fingerprint/uuid" or just "uuid" if no key
    """
    uuid_part = str(uuidv7())
    
    if signing_key_pem:
        # Extract public key and compute fingerprint
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        try:
            private_key = serialization.load_pem_private_key(signing_key_pem, password=None)
            if isinstance(private_key, ed25519.Ed25519PrivateKey):
                public_key_bytes = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                owner_fp = get_fingerprint(public_key_bytes)
                return f"{owner_fp}/{uuid_part}"
        except Exception:  # noqa: BLE001
            pass
    
    # Fallback to UUID only (for dry run or if key parsing fails)
    return uuid_part


def _write_manifest(backend: StorageBackend, capsule_id: str, manifest: dict[str, Any]) -> None:
    backend.put_document(capsule_id, "capsule.manifest.json", _json_bytes(manifest))


def _write_redaction_report(backend: StorageBackend, capsule_id: str, report: dict[str, Any]) -> None:
    backend.put_document(capsule_id, "redaction.report.json", _json_bytes(report))


def _load_manifest(backend: StorageBackend, capsule_id: str) -> dict[str, Any]:
    payload = backend.get_document(capsule_id, "capsule.manifest.json")
    return json.loads(payload.decode("utf-8"))


def _lookup_blob(manifest: dict[str, Any], blob_id: str) -> dict[str, Any]:
    for blob in manifest["blobs"]:
        if blob["blob_id"] == blob_id:
            return blob
    raise BlobInvalidError(f"Blob {blob_id} not found in manifest.")


def _verify_manifest_or_raise(manifest: dict[str, Any], trusted_fingerprints: set[str]) -> None:
    try:
        verify_manifest_signature(manifest, trusted_fingerprints)
    except SignatureError as exc:
        raise SignatureInvalidError(str(exc)) from exc


def _derive_master_key_from_manifest(manifest: dict[str, Any], passphrase: str) -> tuple[bytes, str]:
    crypto = manifest["crypto"]
    params = crypto["kdf_params"]
    salt = base64url_decode(params["salt"])
    argon = Argon2Params(
        mem_kib=params["mem_kib"],
        iterations=params["iterations"],
        parallelism=params["parallelism"],
        hash_len=params["hash_len"],
    )
    master_key = derive_master_key(passphrase, salt, argon)
    return master_key, crypto["aead"]


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _random_salt() -> bytes:
    return os.urandom(16)


def _ensure_supported_spec_version(manifest: dict[str, Any]) -> None:
    spec_version = manifest.get("spec_version")
    if spec_version != "v1":
        raise SchemaInvalidError(f"Unsupported spec_version: {spec_version}")


def _ensure_signature_present(manifest: dict[str, Any]) -> None:
    signature = manifest.get("signature")
    if not isinstance(signature, dict):
        raise SignatureInvalidError("Manifest missing signature object.")
