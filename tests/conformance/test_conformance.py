from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from resurrectum.summon.capsule import (
    BlobInvalidError,
    DecryptFailedError,
    ExportOptions,
    ImportOptions,
    PolicyViolationError,
    SignatureInvalidError,
    ValidateOptions,
    export_capsule,
    import_capsule,
    validate_capsule,
)
from resurrectum.sigil.crypto import blob_id_for_ciphertext
from resurrectum.spec.redaction import RedactionPolicy
from resurrectum.spec.schemas import SchemaRegistry, load_json
from resurrectum.summon.storage import LocalDirBackend
from resurrectum.utils import base64url_decode, sha256_hex

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = REPO_ROOT / "conformance" / "fixtures"


def _copy_fixture(name: str, tmp_path: Path) -> Path:
    source = FIXTURES_ROOT / name
    target = tmp_path / name
    shutil.copytree(source, target)
    return target


def _generate_signing_key() -> tuple[bytes, str]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    fingerprint = sha256_hex(public_bytes)
    return private_pem, fingerprint


def _export_capsule(tmp_path: Path, workspace: Path) -> tuple[str, dict[str, object], LocalDirBackend, str]:
    backend_root = tmp_path / "backend"
    backend = LocalDirBackend(backend_root)
    passphrase = "correct horse battery staple"
    signing_key_pem, fingerprint = _generate_signing_key()
    options = ExportOptions(
        workspace=workspace,
        backend=backend,
        passphrase=passphrase,
        signing_key_pem=signing_key_pem,
        policy=RedactionPolicy.openclaw_default(),
        strict=True,
        dry_run=False,
    )
    capsule_id, manifest = export_capsule(options)
    return capsule_id, manifest, backend, fingerprint


def _snapshot_workspace(workspace: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(workspace).as_posix()] = path.read_bytes()
    return snapshot


def test_round_trip_minimal_workspace(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    original = _snapshot_workspace(workspace)

    capsule_id, manifest, backend, fingerprint = _export_capsule(tmp_path, workspace)

    backend_root = backend.root
    manifest_path = backend_root / "capsules" / capsule_id / "capsule.manifest.json"
    report_path = backend_root / "capsules" / capsule_id / "redaction.report.json"

    registry = SchemaRegistry.default()
    registry.validate_instance(load_json(manifest_path), "capsule.manifest.schema.json")
    registry.validate_instance(load_json(report_path), "redaction.report.schema.json")

    assert "schema_version" in manifest
    assert "crypto" in manifest
    assert "kdf_params" in manifest["crypto"]
    assert manifest["crypto"]["hkdf_info"] == "capsule:blob"

    shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    restore_report_path = workspace / "restore.report.json"
    import_capsule(
        ImportOptions(
            capsule_id=capsule_id,
            backend=backend,
            target_workspace=workspace,
            passphrase="correct horse battery staple",
            trusted_fingerprints={fingerprint},
            overwrite=False,
            partial=False,
            restore_report_path=restore_report_path,
        )
    )

    restored = _snapshot_workspace(workspace)
    for rel_path, data in original.items():
        assert rel_path in restored
        assert restored[rel_path] == data

    registry.validate_instance(load_json(restore_report_path), "restore.report.schema.json")


def test_policy_strict_blocks_forbidden_files(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_with_secrets", tmp_path)
    backend_root = tmp_path / "backend"
    backend = LocalDirBackend(backend_root)
    signing_key_pem, _ = _generate_signing_key()

    with pytest.raises(PolicyViolationError) as exc:
        export_capsule(
            ExportOptions(
                workspace=workspace,
                backend=backend,
                passphrase="passphrase",
                signing_key_pem=signing_key_pem,
                policy=RedactionPolicy.openclaw_default(),
                strict=True,
                dry_run=False,
            )
        )

    assert exc.value.exit_code == 2

    capsule_dirs = list((backend_root / "capsules").iterdir())
    assert capsule_dirs
    report_path = capsule_dirs[0] / "redaction.report.json"
    report = load_json(report_path)

    forbidden = [d for d in report["decisions"] if d["class"] == "forbidden"]
    assert forbidden
    assert all(d["decision"] == "exclude" for d in forbidden)

    report_text = json.dumps(report)
    assert "sk-" not in report_text


def test_dry_run_writes_report_only(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    backend = LocalDirBackend(tmp_path / "backend")

    capsule_id, report = export_capsule(
        ExportOptions(
            workspace=workspace,
            backend=backend,
            passphrase=None,
            signing_key_pem=None,
            policy=RedactionPolicy.openclaw_default(),
            strict=True,
            dry_run=True,
        )
    )

    capsule_root = backend.root / "capsules" / capsule_id
    assert (capsule_root / "redaction.report.json").is_file()
    assert not (capsule_root / "capsule.manifest.json").exists()
    assert not (capsule_root / "blobs").exists()
    assert report["capsule_id"] == capsule_id


def test_tamper_detection_fails_validation(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    capsule_id, manifest, backend, fingerprint = _export_capsule(tmp_path, workspace)

    blob = manifest["blobs"][0]
    blob_path = backend.root / blob["storage"]["ref"]
    original = blob_path.read_bytes()
    blob_path.write_bytes(original + b"tamper")

    with pytest.raises(BlobInvalidError) as exc:
        validate_capsule(
            ValidateOptions(
                capsule_id=capsule_id,
                backend=backend,
                trusted_fingerprints={fingerprint},
            )
        )

    assert exc.value.exit_code == 5


def test_signature_required(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    capsule_id, manifest, backend, fingerprint = _export_capsule(tmp_path, workspace)

    manifest_path = backend.root / "capsules" / capsule_id / "capsule.manifest.json"
    manifest.pop("signature", None)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(SignatureInvalidError) as exc:
        validate_capsule(
            ValidateOptions(
                capsule_id=capsule_id,
                backend=backend,
                trusted_fingerprints={fingerprint},
            )
        )

    assert exc.value.exit_code == 4


def test_wrong_passphrase_fails_import(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    capsule_id, manifest, backend, fingerprint = _export_capsule(tmp_path, workspace)

    shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    with pytest.raises(DecryptFailedError) as exc:
        import_capsule(
            ImportOptions(
                capsule_id=capsule_id,
                backend=backend,
                target_workspace=workspace,
                passphrase="wrong passphrase",
                trusted_fingerprints={fingerprint},
                overwrite=False,
                partial=False,
            )
        )

    assert exc.value.exit_code == 6
    assert not any(workspace.rglob("*"))


def test_trusted_signer_pinning(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    capsule_id, _, backend, _ = _export_capsule(tmp_path, workspace)

    with pytest.raises(SignatureInvalidError) as exc:
        validate_capsule(
            ValidateOptions(
                capsule_id=capsule_id,
                backend=backend,
                trusted_fingerprints={"deadbeef"},
            )
        )

    assert exc.value.exit_code == 4


def test_manifest_consistency(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    capsule_id, manifest, backend, fingerprint = _export_capsule(tmp_path, workspace)

    artifact_paths = [artifact["path"] for artifact in manifest["artifacts"]]
    blob_ids = [blob["blob_id"] for blob in manifest["blobs"]]

    assert len(artifact_paths) == len(set(artifact_paths))
    assert len(blob_ids) == len(set(blob_ids))
    assert {artifact["blob_id"] for artifact in manifest["artifacts"]} <= set(blob_ids)

    manifest_path = backend.root / "capsules" / capsule_id / "capsule.manifest.json"
    stored = load_json(manifest_path)
    stored_signature = stored["signature"]
    public_key_bytes = base64url_decode(stored_signature["public_key"])
    assert stored_signature["signer_fingerprint"] == sha256_hex(public_key_bytes)
    assert stored_signature["signer_fingerprint"] == fingerprint

    blob = manifest["blobs"][0]
    blob_path = backend.root / blob["storage"]["ref"]
    assert blob_id_for_ciphertext(blob_path.read_bytes()) == blob["blob_id"]


def test_redaction_report_coverage_and_summary(tmp_path: Path) -> None:
    workspace = _copy_fixture("workspace_minimal", tmp_path)
    backend_root = tmp_path / "backend"
    backend = LocalDirBackend(backend_root)
    signing_key_pem, _ = _generate_signing_key()

    capsule_id, _ = export_capsule(
        ExportOptions(
            workspace=workspace,
            backend=backend,
            passphrase="passphrase",
            signing_key_pem=signing_key_pem,
            policy=RedactionPolicy.openclaw_default(),
            strict=True,
            dry_run=False,
        )
    )

    report = load_json(backend_root / "capsules" / capsule_id / "redaction.report.json")

    decision_paths = {d["path"] for d in report["decisions"]}
    workspace_paths = {p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file()}
    assert decision_paths == workspace_paths

    findings = report["findings"]
    summary = report["findings_summary"]
    assert summary["total"] == len(findings)

    by_class = {"public": 0, "private": 0, "sensitive": 0, "forbidden": 0}
    by_decision = {
        "exclude": 0,
        "include_encrypted": 0,
        "include_redacted": 0,
        "include_plaintext": 0,
    }
    for decision in report["decisions"]:
        by_class[decision["class"]] = by_class.get(decision["class"], 0) + 1
        by_decision[decision["decision"]] = by_decision.get(decision["decision"], 0) + 1

    assert summary["by_class"] == by_class
    assert summary["by_decision"] == by_decision
