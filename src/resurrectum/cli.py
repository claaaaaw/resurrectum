"""
Resurrectum CLI

Command-line interface for Resurrectum - Soul Immortality for AI Agents.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import click

from .sigil.crypto import generate_keypair, get_fingerprint, load_signing_key
from .spec.redaction import RedactionPolicy
from .summon.capsule import (
    AccessControl,
    CapsuleError,
    ExportOptions,
    ImportOptions,
    ValidateOptions,
    export_capsule,
    import_capsule,
    validate_capsule,
)
from .summon.compression import CompressionOptions, get_compression_info
from .summon.storage import LocalDirBackend, PresignedUrlBackend
from .summon.url_cache import PresignedUrlCache


# ============ Main CLI Group ============


@click.group()
@click.version_option(version="0.1.0", prog_name="resurrectum")
def cli() -> None:
    """Resurrectum - Soul Immortality for AI Agents"""
    pass


# ============ Identity Management ============


@cli.command()
@click.option(
    "--output", "-o",
    default="~/.resurrectum/identity",
    help="Output path prefix for key files"
)
def init(output: str) -> None:
    """Initialize identity (generate Ed25519 keypair)."""
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    private_key_path = output_path.with_suffix(".key")
    public_key_path = output_path.with_suffix(".pub")
    
    if private_key_path.exists():
        click.echo(f"Identity already exists: {private_key_path}")
        click.echo("Use --output to specify a different path.")
        sys.exit(1)
    
    # Generate keypair
    private_key_pem, public_key_bytes = generate_keypair()
    fingerprint = get_fingerprint(public_key_bytes)
    
    # Save keys
    private_key_path.write_bytes(private_key_pem)
    if os.name != "nt":
        private_key_path.chmod(0o600)
    
    public_key_path.write_bytes(public_key_bytes)
    
    click.echo("Identity generated!")
    click.echo(f"  Private key: {private_key_path}")
    click.echo(f"  Public key:  {public_key_path}")
    click.echo(f"  Fingerprint: {fingerprint}")
    click.echo("")
    click.echo("IMPORTANT: Back up your private key!")
    click.echo("    If lost, you cannot recover your capsules.")


@cli.command()
@click.option(
    "--key", "-k",
    default="~/.resurrectum/identity.key",
    help="Path to private key file"
)
def whoami(key: str) -> None:
    """Show identity fingerprint."""
    key_path = Path(key).expanduser()
    
    if not key_path.exists():
        click.echo(f"Key not found: {key_path}")
        click.echo("Run 'resurrectum init' to create an identity.")
        sys.exit(1)
    
    try:
        private_key = load_signing_key(key_path)
        from cryptography.hazmat.primitives import serialization
        public_key_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        fingerprint = get_fingerprint(public_key_bytes)
        click.echo(f"Fingerprint: {fingerprint}")
    except Exception as exc:
        click.echo(f"Error loading key: {exc}")
        sys.exit(1)


# ============ Export/Import Commands ============


@cli.command()
@click.option("--workspace", "-w", default=".", help="Workspace path to export")
@click.option("--out", "-o", required=True, help="Output path (local dir) or 'remote'")
@click.option(
    "--passphrase",
    default="prompt",
    help="Passphrase source: prompt | env:VAR | file:PATH | literal value"
)
@click.option(
    "--signing-key",
    default="~/.resurrectum/identity.key",
    help="Path to Ed25519 signing key"
)
@click.option(
    "--credential-service",
    default="https://api.resurrectum.dev",
    envvar="RESURRECTUM_CREDENTIAL_SERVICE",
    help="Credential service URL (for remote storage)"
)
@click.option("--dry-run", is_flag=True, help="Only generate redaction report")
@click.option("--compress/--no-compress", default=False, help="Enable 7z compression")
@click.option(
    "--compression-level",
    type=click.IntRange(0, 9),
    default=9,
    help="Compression level 0-9 (default: 9 = max)"
)
@click.option("--public", is_flag=True, help="Make capsule publicly accessible")
def export(
    workspace: str,
    out: str,
    passphrase: str,
    signing_key: str,
    credential_service: str,
    dry_run: bool,
    compress: bool,
    compression_level: int,
    public: bool,
) -> None:
    """Export workspace to encrypted capsule."""
    workspace_path = Path(workspace).resolve()
    signing_key_path = Path(signing_key).expanduser()
    
    if not workspace_path.exists():
        click.echo(f"Workspace not found: {workspace_path}")
        sys.exit(1)
    
    # Select backend
    if out == "remote":
        if not signing_key_path.exists():
            click.echo(f"Signing key required for remote storage: {signing_key_path}")
            sys.exit(1)
        backend = PresignedUrlBackend(
            credential_service_url=credential_service,
            signing_key_path=signing_key_path,
        )
        click.echo(f"Using remote storage: {credential_service}")
    else:
        out_path = Path(out).resolve()
        backend = LocalDirBackend(root=out_path)
        click.echo(f"Using local storage: {out_path}")
    
    # Get passphrase
    passphrase_value: Optional[str] = None
    if not dry_run:
        passphrase_value = _resolve_passphrase(passphrase)
        if not passphrase_value:
            click.echo("Passphrase is required for export.")
            sys.exit(1)
    
    # Load signing key
    signing_key_pem: Optional[bytes] = None
    if signing_key_path.exists():
        signing_key_pem = signing_key_path.read_bytes()
    elif not dry_run:
        click.echo(f"Signing key not found: {signing_key_path}")
        click.echo("Run 'resurrectum init' to create an identity.")
        sys.exit(1)
    
    # Compression options
    compression_opts = CompressionOptions(
        enabled=compress,
        algorithm="7z",
        level=compression_level,
    )
    
    if compress:
        comp_info = get_compression_info()
        if not comp_info["available"]:
            click.echo("7z compression requires py7zr. Install with: pip install py7zr")
            sys.exit(1)
    
    # Access control
    access: Optional[AccessControl] = None
    if signing_key_pem and not dry_run:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ed25519
            private_key = serialization.load_pem_private_key(signing_key_pem, password=None)
            if isinstance(private_key, ed25519.Ed25519PrivateKey):
                public_key_bytes = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                owner_fp = get_fingerprint(public_key_bytes)
                access = AccessControl(owner=owner_fp, public=public)
        except Exception:  # noqa: BLE001
            pass
    
    # Build export options
    options = ExportOptions(
        workspace=workspace_path,
        backend=backend,
        passphrase=passphrase_value,
        signing_key_pem=signing_key_pem,
        policy=RedactionPolicy.openclaw_default(),
        strict=True,
        dry_run=dry_run,
        compression=compression_opts,
        access=access,
    )
    
    try:
        capsule_id, result = export_capsule(options)
        click.echo(f"Capsule ID: {capsule_id}")
        if dry_run:
            click.echo("Dry run complete. See redaction report.")
            _show_redaction_summary(result)
        else:
            artifact_count = len(result.get("artifacts", []))
            click.echo(f"Export complete. {artifact_count} artifacts.")
            if compress and "compression" in result:
                comp = result["compression"]
                ratio = comp.get("compression_ratio", 1.0)
                saved = (1 - ratio) * 100
                click.echo(f"Compression: {saved:.1f}% space saved")
    except CapsuleError as exc:
        click.echo(f"Export failed: {exc}")
        sys.exit(exc.exit_code)


@cli.command("import")
@click.option("--from", "from_", required=True, help="Capsule ID or local path")
@click.option("--to", required=True, help="Target workspace path")
@click.option(
    "--passphrase",
    default="prompt",
    help="Passphrase source: prompt | env:VAR | file:PATH"
)
@click.option(
    "--trusted-signer",
    required=True,
    help="Trusted signer fingerprint or file:PATH"
)
@click.option(
    "--credential-service",
    default="https://api.resurrectum.dev",
    envvar="RESURRECTUM_CREDENTIAL_SERVICE",
    help="Credential service URL"
)
@click.option(
    "--signing-key",
    default="~/.resurrectum/identity.key",
    help="Path to Ed25519 signing key (for remote)"
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files")
@click.option("--partial", is_flag=True, help="Continue on errors")
def import_cmd(
    from_: str,
    to: str,
    passphrase: str,
    trusted_signer: str,
    credential_service: str,
    signing_key: str,
    overwrite: bool,
    partial: bool,
) -> None:
    """Import workspace from encrypted capsule."""
    target_path = Path(to).resolve()
    signing_key_path = Path(signing_key).expanduser()
    
    # Determine if local or remote
    if "/" in from_ and len(from_.split("/")[0]) == 64:
        # Looks like owner_fp/uuid format - remote
        if not signing_key_path.exists():
            click.echo(f"Signing key required for remote import: {signing_key_path}")
            sys.exit(1)
        backend = PresignedUrlBackend(
            credential_service_url=credential_service,
            signing_key_path=signing_key_path,
        )
        capsule_id = from_
        click.echo(f"Importing from remote: {capsule_id}")
    else:
        # Local path
        local_path = Path(from_).resolve()
        if not local_path.exists():
            click.echo(f"Path not found: {local_path}")
            sys.exit(1)
        backend = LocalDirBackend(root=local_path.parent.parent)
        capsule_id = local_path.name
        click.echo(f"Importing from local: {local_path}")
    
    # Get passphrase
    passphrase_value = _resolve_passphrase(passphrase)
    if not passphrase_value:
        click.echo("Passphrase is required for import.")
        sys.exit(1)
    
    # Resolve trusted signer
    trusted_fingerprints = _resolve_trusted_signer(trusted_signer)
    
    options = ImportOptions(
        capsule_id=capsule_id,
        backend=backend,
        target_workspace=target_path,
        passphrase=passphrase_value,
        trusted_fingerprints=trusted_fingerprints,
        overwrite=overwrite,
        partial=partial,
    )
    
    try:
        report = import_capsule(options)
        results = report.get("results", {})
        created = len(results.get("created", []))
        skipped = len(results.get("skipped", []))
        failed = len(results.get("failed", []))
        click.echo(f"Import complete. Created: {created}, Skipped: {skipped}, Failed: {failed}")
    except CapsuleError as exc:
        click.echo(f"Import failed: {exc}")
        sys.exit(exc.exit_code)


@cli.command()
@click.option("--capsule-id", required=True, help="Capsule ID to validate")
@click.option("--path", "-p", help="Local capsule path (if local)")
@click.option(
    "--trusted-signer",
    required=True,
    help="Trusted signer fingerprint or file:PATH"
)
@click.option(
    "--passphrase",
    default=None,
    help="Optional passphrase for full validation"
)
@click.option(
    "--credential-service",
    default="https://api.resurrectum.dev",
    envvar="RESURRECTUM_CREDENTIAL_SERVICE",
    help="Credential service URL"
)
@click.option(
    "--signing-key",
    default="~/.resurrectum/identity.key",
    help="Path to Ed25519 signing key (for remote)"
)
def validate(
    capsule_id: str,
    path: Optional[str],
    trusted_signer: str,
    passphrase: Optional[str],
    credential_service: str,
    signing_key: str,
) -> None:
    """Validate capsule integrity and signature."""
    signing_key_path = Path(signing_key).expanduser()
    
    # Determine backend
    if path:
        local_path = Path(path).resolve()
        backend = LocalDirBackend(root=local_path)
    else:
        if not signing_key_path.exists():
            click.echo(f"Signing key required for remote validation: {signing_key_path}")
            sys.exit(1)
        backend = PresignedUrlBackend(
            credential_service_url=credential_service,
            signing_key_path=signing_key_path,
        )
    
    trusted_fingerprints = _resolve_trusted_signer(trusted_signer)
    
    passphrase_value: Optional[str] = None
    if passphrase:
        passphrase_value = _resolve_passphrase(passphrase)
    
    options = ValidateOptions(
        capsule_id=capsule_id,
        backend=backend,
        trusted_fingerprints=trusted_fingerprints,
        passphrase=passphrase_value,
    )
    
    try:
        validate_capsule(options)
        click.echo("Validation passed!")
        if passphrase_value:
            click.echo("  - Signature: valid")
            click.echo("  - Blobs: verified")
            click.echo("  - Decryption: successful")
        else:
            click.echo("  - Signature: valid")
            click.echo("  - Blobs: hash verified")
            click.echo("  - Decryption: skipped (no passphrase)")
    except CapsuleError as exc:
        click.echo(f"Validation failed: {exc}")
        sys.exit(exc.exit_code)


# ============ Cache Management ============


@cli.group()
def cache() -> None:
    """Manage URL cache."""
    pass


@cache.command("clear")
@click.option("--capsule-id", help="Clear specific capsule cache only")
def cache_clear(capsule_id: Optional[str]) -> None:
    """Clear cached presigned URLs."""
    url_cache = PresignedUrlCache()
    url_cache.clear(capsule_id)
    if capsule_id:
        click.echo(f"Cleared cache for: {capsule_id}")
    else:
        click.echo("Cache cleared.")


@cache.command("info")
def cache_info() -> None:
    """Show cache status."""
    url_cache = PresignedUrlCache()
    entries = url_cache.list_cached()
    
    if not entries:
        click.echo("No cached URLs.")
        return
    
    click.echo(f"Cached URLs: {len(entries)}")
    for entry in entries:
        status = entry.get("status", "unknown")
        capsule_id = entry.get("capsule_id", "unknown")
        remaining = entry.get("remaining_seconds", 0)
        if status == "valid":
            click.echo(f"  {capsule_id}: {status} ({remaining}s remaining)")
        else:
            click.echo(f"  {capsule_id}: {status}")


# ============ Info Commands ============


@cli.command()
def info() -> None:
    """Show system information."""
    click.echo("Resurrectum v0.1.0")
    click.echo("")
    
    # Compression support
    comp_info = get_compression_info()
    if comp_info["available"]:
        click.echo(f"7z Compression: available (py7zr {comp_info.get('py7zr_version', 'unknown')})")
    else:
        click.echo("7z Compression: not available (install py7zr)")
    
    # Identity
    default_key = Path("~/.resurrectum/identity.key").expanduser()
    if default_key.exists():
        try:
            private_key = load_signing_key(default_key)
            from cryptography.hazmat.primitives import serialization
            public_key_bytes = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            fingerprint = get_fingerprint(public_key_bytes)
            click.echo(f"Identity: {fingerprint[:16]}...")
        except Exception:  # noqa: BLE001
            click.echo("Identity: error loading key")
    else:
        click.echo("Identity: not initialized (run 'resurrectum init')")
    
    # Cache
    url_cache = PresignedUrlCache()
    entries = url_cache.list_cached()
    valid_count = sum(1 for e in entries if e.get("status") == "valid")
    click.echo(f"URL Cache: {valid_count} valid entries")


# ============ Helper Functions ============


def _resolve_passphrase(source: str) -> Optional[str]:
    """Resolve passphrase from various sources."""
    if source == "prompt":
        return click.prompt("Passphrase", hide_input=True)
    if source.startswith("env:"):
        var_name = source[4:]
        value = os.environ.get(var_name)
        if not value:
            click.echo(f"Environment variable not set: {var_name}")
            return None
        return value
    if source.startswith("file:"):
        file_path = Path(source[5:]).expanduser()
        if not file_path.exists():
            click.echo(f"Passphrase file not found: {file_path}")
            return None
        return file_path.read_text(encoding="utf-8").rstrip("\n\r")
    # Literal value
    return source


def _resolve_trusted_signer(source: str) -> set[str]:
    """Resolve trusted signer fingerprints."""
    if source.startswith("file:"):
        file_path = Path(source[5:]).expanduser()
        if not file_path.exists():
            click.echo(f"Trusted signer file not found: {file_path}")
            sys.exit(1)
        # Read fingerprints, one per line
        content = file_path.read_text(encoding="utf-8")
        fingerprints = {line.strip() for line in content.splitlines() if line.strip()}
        return fingerprints
    # Single fingerprint
    return {source}


def _show_redaction_summary(report: dict) -> None:
    """Show redaction report summary."""
    decisions = report.get("decisions", [])
    summary = report.get("summary", {})
    
    by_decision = {}
    for d in decisions:
        dec = d.get("decision", "unknown")
        by_decision[dec] = by_decision.get(dec, 0) + 1
    
    click.echo("Redaction summary:")
    for decision, count in sorted(by_decision.items()):
        click.echo(f"  {decision}: {count}")
    
    if summary.get("has_forbidden"):
        click.echo("")
        click.echo("WARNING: Forbidden content detected!")
        for d in decisions:
            if d.get("class") == "forbidden":
                click.echo(f"  - {d.get('path')}")


# ============ Entry Point ============


def main() -> None:
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
