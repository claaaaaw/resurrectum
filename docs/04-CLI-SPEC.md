# Resurrectum — CLI Spec v1.1 (OpenClaw-only)

**Audience:** AI engineers

**v1.1 scope:** Normative CLI surface for OpenClaw-only Resurrectum v1.1.

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
Standalone CLI namespace:
- `resurrectum init` — Initialize identity (generate Ed25519 keypair)
- `resurrectum whoami` — Show identity fingerprint
- `resurrectum export` — Export workspace to capsule
- `resurrectum import` — Import workspace from capsule
- `resurrectum validate` — Validate capsule integrity
- `resurrectum cache clear|info` — Manage URL cache
- `resurrectum info` — Show system information

Alternative namespace (OpenClaw integration):
- `openclaw summon export`
- `openclaw summon import`
- `openclaw summon validate`

Dry-run/redaction UX:
- **Normative v1 dry-run:** `resurrectum export --dry-run`
- Optional alias (not required for conformance): `openclaw summon redact --dry-run`

If OpenClaw core CLI integration is not available, provide an equivalent `resurrectum` standalone binary/script with the same UX.

## 1.1 Identity Management Commands (v1.1)

### `resurrectum init`
Initialize identity by generating Ed25519 keypair.

```
resurrectum init [--output PATH]
```

Options:
- `--output, -o` — Output path prefix for key files (default: `~/.resurrectum/identity`)
  - Creates `{path}.key` (private key, PEM format)
  - Creates `{path}.pub` (public key, raw bytes)

Example:
```bash
$ resurrectum init
Identity generated!
  Private key: ~/.resurrectum/identity.key
  Public key:  ~/.resurrectum/identity.pub
  Fingerprint: a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890

IMPORTANT: Back up your private key!
    If lost, you cannot recover your capsules.
```

### `resurrectum whoami`
Show current identity fingerprint.

```
resurrectum whoami [--key PATH]
```

Options:
- `--key, -k` — Path to private key file (default: `~/.resurrectum/identity.key`)

## 1.2 Cache Management Commands (v1.1)

### `resurrectum cache clear`
Clear cached presigned URLs.

```
resurrectum cache clear [--capsule-id ID]
```

Options:
- `--capsule-id` — Clear only specific capsule's cache

### `resurrectum cache info`
Show cache status.

```
resurrectum cache info
```

## 2. `export`
### 2.1 Synopsis
`resurrectum export --workspace <path> --out <path|remote> [options]`

Notes:
- In v1, `--dry-run` is part of `export` (produce only `redaction.report.json`).
- `--signing-key` is required for any non-dry-run export.
- `--out` is required even for `--dry-run` to define where the report is written.
- v1.1: `--out remote` uses credential service for remote storage.

### 2.2 Required behavior
- Default policy is **strict** (fail closed).
- Export MUST produce:
  - `capsule.manifest.json`
  - `redaction.report.json`
  - encrypted blobs
- Export MUST sign the manifest (v1 required).
- v1 signing key is provided explicitly via `--signing-key file:PATH` (Ed25519 private key).
- Manifest MUST include `schema_version` and Argon2id parameters (per `03-SCHEMAS.md`).
- v1.1: `capsule_id` MUST be in `owner_fp/uuid` format.
- For `--dry-run`, exporter MUST:
  - generate a `capsule_id` (owner_fp/uuid or uuid-only if no key) and include it in `redaction.report.json`
  - write **only** `redaction.report.json` to the output backend
  - write no blobs and no manifest

### 2.3 Options (v1.1)
- `--workspace, -w <path>` (default: cwd)
- `--out, -o <path|remote>` (required)
  - Local path: uses LocalDirBackend
  - `remote`: uses PresignedUrlBackend with credential service
- `--passphrase <prompt|env:VAR|file:PATH>` (default: prompt; ignored for `--dry-run`)
- `--signing-key <PATH>` (default: `~/.resurrectum/identity.key`)
  - MUST be an Ed25519 private key.
  - The corresponding public key is embedded in the manifest (`signature.public_key`).
  - The manifest MUST also include `signature.signer_fingerprint` = `sha256(public_key_bytes)`.
- `--credential-service <URL>` (default: `https://api.resurrectum.dev`, env: `RESURRECTUM_CREDENTIAL_SERVICE`)
- `--compress/--no-compress` (default: `--no-compress`)
  - When enabled, all files are packed into a 7z archive before encryption.
- `--compression-level <0-9>` (default: 9)
- `--public` (make capsule publicly accessible)
- `--trusted-signer <hex_fingerprint|file:PATH>` (used by `validate`/`import`; see below)
  - hex fingerprint is `sha256(public_key_bytes)` (lowercase hex)
- `--policy <path>` (optional; advanced)
- `--include-project-status` (default: true)
- `--allow <glob>` (repeatable; explicit allowlist extensions)
- `--deny <glob>` (repeatable; explicit denylist)
- `--dry-run` (only generate `redaction.report.json`; **no blobs, no manifest, no signature**)
  - Local dir: write to `<out>/capsules/<capsule_id>/redaction.report.json`
  - Remote: write to credential service storage
- `--strict/--no-strict` (default: strict)
- `--i-know-what-im-doing` (required to include Forbidden class; loud warning)

### 2.3.1 Passphrase handling (v1, normative)
To ensure interoperability across implementations:
- Passphrase bytes are derived from UTF-8 encoding of the passphrase string.
- `prompt` and `env:VAR` use the exact string value as provided.
- `file:PATH` reads the file as UTF-8 text and **trims a single trailing newline** (`\n` or `\r\n`) if present.
  - No other trimming/normalization is performed.

### 2.4 Policy precedence (v1)
- `--deny` always wins over `--allow`.
- Forbidden findings require `--i-know-what-im-doing` **and** `--no-strict` to proceed.
- `--allow` cannot override a Forbidden classification unless the explicit override flag is present.

### 2.5 Argon2id defaults (v1)
Unless overridden by implementation-specific config, v1 recommends:
- `mem_kib`: `65536` (64 MiB)
- `iterations`: `3`
- `parallelism`: `1`
- `hash_len`: `32`

Export MUST record the actual Argon2id parameters and salt in the manifest.

### 2.6 Signing key generation (v1.1)
**Recommended: Use `resurrectum init`**
```bash
resurrectum init
```

Alternative Ed25519 key generation (PKCS8 PEM):
- `openssl genpkey -algorithm Ed25519 -out capsule-signing.key`
- `openssl pkey -in capsule-signing.key -pubout -out capsule-signing.pub`

The exporter MUST derive `signature.public_key` (raw Ed25519 public key bytes, base64url) and `signature.signer_fingerprint` (sha256 over raw public key bytes).
`--trusted-signer` MAY accept either a hex fingerprint or a PEM public key file.

## 3. `import`
### 3.1 Synopsis
`openclaw summon import --from <path|s3://...> --to <workspace_path> [options]`

### 3.2 Required behavior
- Validate schema + hashes + signature before writing files.
- **Trust model (v1):** signature verification MUST be performed against a pinned/trusted signer (via `--trusted-signer` or an equivalent trust store). Do not accept “any embedded public_key” by default.
- Default: do not overwrite existing files.
- Import requires a passphrase to decrypt payloads; if not provided, import MUST fail.

### 3.3 Options (v1)
- `--from <ref>`
- `--to <path>`
- `--passphrase <prompt|env:VAR|file:PATH>` (**required**)
- `--trusted-signer <hex_fingerprint|file:PATH>` (**required v1**)
- `--overwrite` (explicit)
- `--partial` (write what can be restored; still produce restore report)

## 4. `validate`
### 4.1 Synopsis
`openclaw summon validate --from <ref> [--passphrase ...] --trusted-signer <hex_fingerprint|file:PATH> [options]`

### 4.2 Required checks
- JSON Schema validation
- signature validation (required v1)
  - v1 trust model: validator MUST be given a trusted public key (or keyring) out-of-band.
  - verify Ed25519 signature over RFC 8785 JCS bytes (see `03-SCHEMAS.md`)
  - require pinned/trusted signer (do not trust the embedded public key by default)
  - recompute `signer_fingerprint` from `public_key` and fail if it does not match
- blob hash validation (ciphertext hash)
- decrypt + plaintext hash verification (if passphrase provided)
  - If no passphrase is provided, `validate` MUST still run schema + signature + ciphertext hash checks.

## 5. Exit codes (normative)
- `0`: success
- `2`: policy violation / forbidden findings in strict mode
- `3`: schema invalid
- `4`: signature invalid
- `5`: blob missing/corrupt (hash mismatch)
- `6`: decrypt failed (wrong or missing passphrase)
- `7`: restore failed (filesystem/write error)

## 6. Standard output artifacts
- `redaction.report.json`
- `restore.report.json` (on import)

## 7. Next step
- Write conformance tests that assert exit codes + artifact outputs.
