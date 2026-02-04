from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..sigil.crypto import (
    Argon2Params,
    CryptoError,
    SignatureError,
    blob_id_for_ciphertext,
    decrypt_payload,
    derive_master_key,
    encrypt_payload,
    sign_manifest,
    verify_manifest_signature,
)
from ..spec.models import CapsuleManifest, RedactionReport, RestoreReport
from ..spec.redaction import RedactionPolicy
from ..spec.schemas import SchemaValidationError
from .storage import LocalDirBackend, S3Backend, StorageBackend
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
class ExportOptions:
    workspace: Path
    backend: StorageBackend
    passphrase: str | None
    signing_key_pem: bytes | None
    policy: RedactionPolicy
    aead: str = "xchacha20-poly1305"
    argon2_params: Argon2Params = Argon2Params()
    strict: bool = True
    dry_run: bool = False


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
    capsule_id = str(uuidv7())
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

    artifacts: list[dict[str, Any]] = []
    blobs: list[dict[str, Any]] = []

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
        blobs.append(
            {
                "blob_id": blob_id,
                "ciphertext_hash": blob_id,
                "ciphertext_size_bytes": len(ciphertext),
                "nonce": base64url_encode(nonce),
                "storage": {"backend": _backend_name(options.backend), "ref": ref},
            }
        )
        artifacts.append(
            {
                "path": rel_path,
                "kind": artifact_kind(rel_path),
                "mode": decision["decision"],
                "plaintext_hash": plaintext_hash,
                "size_bytes": len(payload),
                "blob_id": blob_id,
            }
        )

    manifest = build_manifest(
        capsule_id=capsule_id,
        aead=options.aead,
        salt=master_salt,
        params=options.argon2_params,
        artifacts=artifacts,
        blobs=blobs,
        policy_version=options.policy.policy_version,
    )
    manifest["signature"] = sign_manifest(manifest, options.signing_key_pem)

    CapsuleManifest.from_dict(manifest)
    RedactionReport.from_dict(report)

    _write_redaction_report(options.backend, capsule_id, report)
    _write_manifest(options.backend, capsule_id, manifest)
    return capsule_id, manifest


def import_capsule(options: ImportOptions) -> dict[str, Any]:
    manifest = _load_manifest(options.backend, options.capsule_id)
    _ensure_supported_spec_version(manifest)
    _ensure_signature_present(manifest)
    try:
        CapsuleManifest.from_dict(manifest)
    except SchemaValidationError as exc:
        raise SchemaInvalidError(str(exc)) from exc

    _verify_manifest_or_raise(manifest, options.trusted_fingerprints)

    master_key, aead = _derive_master_key_from_manifest(manifest, options.passphrase)

    results = {"created": [], "skipped": [], "overwritten": [], "failed": []}
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
) -> dict[str, Any]:
    return {
        "spec_version": "v1",
        "schema_version": "1.0.0",
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
    if isinstance(backend, LocalDirBackend):
        return "local_dir"
    if isinstance(backend, S3Backend):
        return "s3"
    raise CapsuleError(f"Unknown backend type: {type(backend).__name__}")


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
