# Memory Capsule — CLI Spec v1 (OpenClaw-only)

**Audience:** AI engineers

**v1 scope:** Normative CLI surface for OpenClaw-only Memory Capsule v1.

## 0. Goal
Define a CLI that is safe-by-default, implementation-oriented, and testable.

## Related docs
- Requirements: `01-PRD.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- Backends: `05-STORAGE-BACKENDS.md`
- Redaction policy (normative): `07-REDACTION-POLICY.md`
- Conformance tests: `08-CONFORMANCE-TESTS.md`

> This is a spec (normative): flags, exit codes, and outputs must be stable.

## 1. Command overview
Proposed namespace:
- `openclaw capsule export`
- `openclaw capsule import`
- `openclaw capsule validate`

**v1 canonical dry-run surface:** `openclaw capsule export --dry-run`

If OpenClaw core CLI integration is not available, provide an equivalent `capsule` standalone binary/script with the same UX.

## 2. `export`
### 2.1 Synopsis
`openclaw capsule export --workspace <path> --out <path|s3://...> [options]`

Notes:
- In v1, `--dry-run` is part of `export` (produce only `redaction.report.json`).
- `--signing-key` is required for any non-dry-run export.

### 2.2 Required behavior
- Default policy is **strict** (fail closed).
- Export MUST produce:
  - `capsule.manifest.json`
  - `redaction.report.json`
  - encrypted blobs
- Export MUST sign the manifest (v1 required).
- v1 signing key is provided explicitly via `--signing-key file:PATH` (Ed25519 private key).

### 2.3 Options (v1)
- `--workspace <path>` (default: cwd)
- `--out <path|s3://bucket/prefix>`
- `--passphrase <prompt|env:VAR|file:PATH>` (default: prompt)
- `--signing-key <file:PATH>` (**required unless `--dry-run`**)
  - MUST be an Ed25519 private key.
  - The corresponding public key is embedded in the manifest (`signature.public_key`).
  - The manifest MUST also include `signature.signer_fingerprint` = `sha256(public_key_bytes)`.
- `--trusted-signer <hex_fingerprint|file:PATH>` (used by `validate`/`import`; see below)
  - hex fingerprint is `sha256(public_key_bytes)` (lowercase hex)
- `--policy <path>` (optional; advanced)
- `--include-project-status` (default: true)
- `--allow <glob>` (repeatable; explicit allowlist extensions)
- `--deny <glob>` (repeatable; explicit denylist)
- `--dry-run` (only generate `redaction.report.json`; **no blobs, no manifest, no signature**)
- `--strict/--no-strict` (default: strict)
- `--i-know-what-im-doing` (required to include Forbidden class; loud warning)

## 3. `import`
### 3.1 Synopsis
`openclaw capsule import --from <path|s3://...> --to <workspace_path> [options]`

### 3.2 Required behavior
- Validate schema + hashes + signature before writing files.
- **Trust model (v1):** signature verification MUST be performed against a pinned/trusted signer (via `--trusted-signer` or an equivalent trust store). Do not accept “any embedded public_key” by default.
- Default: do not overwrite existing files.

### 3.3 Options (v1)
- `--from <ref>`
- `--to <path>`
- `--passphrase <prompt|env:VAR|file:PATH>`
- `--trusted-signer <hex_fingerprint|file:PATH>` (**required v1**)
- `--overwrite` (explicit)
- `--partial` (write what can be restored; still produce restore report)

## 4. `validate`
### 4.1 Synopsis
`openclaw capsule validate --from <ref> [--passphrase ...] --trusted-signer <hex_fingerprint|file:PATH> [options]`

### 4.2 Required checks
- JSON Schema validation
- signature validation (required v1)
  - v1 trust model: validator MUST be given a trusted public key (or keyring) out-of-band.
  - verify Ed25519 signature over RFC 8785 JCS bytes (see `03-SCHEMAS.md`)
  - require pinned/trusted signer (do not trust the embedded public key by default)
- blob hash validation (ciphertext hash)
- decrypt + plaintext hash verification (if passphrase provided)

## 5. Exit codes (normative)
- `0`: success
- `2`: policy violation / forbidden findings in strict mode
- `3`: schema invalid
- `4`: signature invalid
- `5`: blob missing/corrupt (hash mismatch)
- `6`: decrypt failed (wrong passphrase)
- `7`: restore failed (filesystem/write error)

## 6. Standard output artifacts
- `redaction.report.json`
- `restore.report.json` (on import)

## 7. Next step
- Write conformance tests that assert exit codes + artifact outputs.
