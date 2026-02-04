# Resurrectum — Schemas v1.1 (Machine Layer, OpenClaw-only)

**Audience:** AI engineers

**v1.1 scope:** Normative Machine Layer contracts for OpenClaw-only Resurrectum v1.1.

## 0. Goal
This document defines the **canonical Machine Layer contracts** for Resurrectum v1.
- The contracts are normative.
- Human docs must not contradict these contracts.

## Related docs
- Architecture overview: `02-ARCHITECTURE.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Backends: `05-STORAGE-BACKENDS.md`
- Redaction boundary (normative): `07-REDACTION-POLICY.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`
- Conformance tests: `08-CONFORMANCE-TESTS.md`

## 1. Versioning & extension rules
- Capsule format versions: `v1`, `v1.1`, ... (non-breaking additions only within v1.x)
- Each JSON document includes:
  - `spec_version`: e.g. `"v1"`
  - `schema_version`: semver string for the schema itself (e.g. `"1.0.0"`)
- Implementations MUST ignore unknown fields **only if** they are prefixed with `x_`.
- Unknown non-`x_` fields MUST be rejected as schema-invalid.
- Extension fields MUST be prefixed with `x_` and MUST NOT change v1 semantics.

## 2. Common encodings & normalization (v1.1, normative)
To prevent implementation forks, v1.1 fixes encodings and path rules:
- **All hashes are lowercase hex**.
  - `sha256` = 64 hex chars.
- **Nonces/salts are base64url (unpadded)** per RFC 4648 URL-safe alphabet.
- **Signatures and public keys are base64url (unpadded)**.
- `capsule_id` format (v1.1): **`{owner_fingerprint}/{uuid}`**
  - `owner_fingerprint`: 64 hex chars (sha256 of owner's Ed25519 public key)
  - `uuid`: UUIDv7 string
  - Example: `a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890/01925b6a-7c8d-7def-9012-345678abcdef`
- `created_at` uses RFC3339 timestamps.
- `path` normalization for artifacts:
  - POSIX-style `/` separators only.
  - Relative paths only; no leading `/`.
  - No `..` segments or drive-letter prefixes.
  - Normalize Unicode to NFC.
- **Nonce uniqueness (v1):** Each blob nonce MUST be unique and generated from a cryptographically secure RNG.

> Note: storage backends may use their own encoding for object names, but manifest fields MUST follow the above.

## 3. Required JSON documents (v1)
1) `capsule.manifest.json`
2) `redaction.report.json`

Optional (v1):
- `restore.report.json`

## 4. `capsule.manifest.json` (normative)
### 4.1 Purpose
Describes one capsule snapshot:
- what artifacts are included
- how to fetch their encrypted blobs
- how to validate integrity
- how to apply policy/redaction decisions

### 4.2 Required top-level fields (v1.1)
- `spec_version` (string) — MUST be `"v1"`
- `schema_version` (string) — semver for the manifest schema (e.g. `"1.1.0"`)
- `capsule_id` (string) — `{owner_fingerprint}/{uuid}` format (v1.1)
- `created_at` (RFC3339 string)
- `tool` (object): `{ name, version }`
- `source` (object): `{ workspace_fingerprint?, openclaw_version?, host_tz? }` (non-sensitive only)
  - `workspace_fingerprint` is **opaque and non-reversible** (UUIDv7 recommended). Do not derive from raw paths.
- `crypto` (object) — global parameters for all blobs in this manifest:
  - `aead` (string): `xchacha20-poly1305 | aes-256-gcm`
  - `kdf` (string): `hkdf-sha256`
  - `key_source` (string): **MUST be `passphrase_argon2id` (v1)**
  - `hkdf_info` (string): **MUST be `capsule:blob`** (UTF-8)
  - `kdf_params` (object):
    - `alg` (string): **MUST be `argon2id`**
    - `salt` (string): base64url (unpadded)
    - `mem_kib` (int) — memory cost in KiB
    - `iterations` (int) — time cost
    - `parallelism` (int)
    - `hash_len` (int) — derived key length (bytes), **MUST be `32`**
- `artifacts` (array)
- `blobs` (array)
- `redaction` (object)
  - `report_path` (string) => MUST be `redaction.report.json`
  - `policy_version` (string)
- `signature` (object) **required v1**

### 4.2.0 Access control field (v1.1, optional)
- `access` (object) — access control configuration
  - `owner` (string): owner's public key fingerprint prefixed with algorithm (e.g., `"ed25519:a1b2c3d4..."`)
  - `readers` (array of strings): list of authorized reader fingerprints (optional)
  - `public` (boolean): whether capsule is publicly accessible (default: false)

Example:
```json
{
  "access": {
    "owner": "ed25519:a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
    "readers": [
      "ed25519:e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i5j6"
    ],
    "public": false
  }
}
```

### 4.2.0a Compression field (v1.1, optional)
- `compression` (object) — compression configuration (only present if compression was used)
  - `enabled` (boolean): whether compression was used
  - `algorithm` (string): compression algorithm (currently only `"7z"` supported)
  - `level` (int): compression level 0-9
  - `original_size_bytes` (int): total size before compression
  - `compressed_size_bytes` (int): size after compression
  - `compression_ratio` (float): ratio of compressed to original size

Example:
```json
{
  "compression": {
    "enabled": true,
    "algorithm": "7z",
    "level": 9,
    "original_size_bytes": 1234567,
    "compressed_size_bytes": 345678,
    "compression_ratio": 0.28
  }
}
```

AEAD nonce length is implied by `crypto.aead`:
- `xchacha20-poly1305` → 24-byte nonce
- `aes-256-gcm` → 12-byte nonce

### 4.2.1 Key derivation (v1, normative)
Per-blob data keys MUST be derived as follows:
```
DK = HKDF-SHA256(
  IKM = MasterKey,
  salt = base64url_decode(blob.nonce),
  info = "capsule:blob" (UTF-8),
  length = 32
)
```
This rule is locked for v1 interoperability.

### 4.2.2 Signature object (v1, normative)
The `signature` object locks *both* the cryptographic algorithm and the bytes-to-sign rules.

Required fields:
- `alg` (string) — MUST be `ed25519`
- `payload_alg` (string) — MUST be `rfc8785_jcs_without_signature_utf8`
- `public_key` (string) — base64url (unpadded) encoding of raw Ed25519 public key bytes
- `signer_fingerprint` (string) — lowercase hex `sha256(public_key_bytes)`
- `sig` (string) — base64url (unpadded) signature over the canonicalized bytes

Validator MUST recompute `signer_fingerprint` from `public_key` and fail if it does not match.

#### Bytes-to-sign (v1, normative)
`bytes_to_sign` are computed as:
1) Remove the top-level `signature` field from the manifest JSON object.
2) Canonicalize the remaining JSON using **RFC 8785 JSON Canonicalization Scheme (JCS)**.
3) UTF-8 encode the resulting canonical JSON text.
4) Sign exactly those bytes (no trailing newline).

Importer/validator MUST recompute `bytes_to_sign` exactly as above and verify the signature before any decrypt/restore.

### 4.3 Artifact record (v1)
Each artifact represents one file that **will be restored** into an OpenClaw workspace.
- `path` (string) — relative, normalized, no `..` (see Section 2)
- `kind` (string) — one of `memory | persona | ops | project | other`
  - Extension values MUST be prefixed with `x_` (e.g., `x_vector_index`).
- `mode` (string) — `include_encrypted | include_redacted | include_plaintext`
  - **Mode describes redaction state, not encryption.** All payloads are encrypted by default in v1.
  - `include_plaintext` means the **original, unredacted bytes** are stored (still encrypted).
- `plaintext_hash` (string) — lowercase hex `sha256` of the **bytes that will be restored**
  - For `include_redacted`, this hash is computed over the **redacted** bytes.
- `size_bytes` (int) — size of the **bytes that will be restored**
- `blob_id` (string) — lowercase hex; points into `blobs[]`

Artifacts are only included if the decision is not `exclude`. Exclusions are recorded in `redaction.report.json`.
`blob_id` MUST reference an entry in `blobs[]`.

#### Compression (v1, normative)
v1 does **not** define compression. Payload bytes for each artifact MUST be:
- the original file bytes (`include_encrypted` / `include_plaintext`), or
- the redacted bytes (`include_redacted`).
Any compression is non-conformant in v1.

#### Determinism note (v1, normative)
- `plaintext_hash` MUST be stable for the same file bytes.
- v1 does NOT require re-export to produce the same ciphertext, the same nonce, or the same `blob_id`.

## 5. Blob records (normative)
### 5.1 Privacy rule
**Blob IDs MUST be derived from ciphertext bytes in v1.**
- `blob_id = sha256(ciphertext_bytes)` (**lowercase hex**)

### 5.2 Blob record fields (v1.1)
- `blob_id` (string) — lowercase hex `sha256(ciphertext_bytes)`
- `ciphertext_hash` (string) — same as `blob_id` (kept for clarity)
- `ciphertext_size_bytes` (int)
- `nonce` (string) — base64url (unpadded)
- `storage` (object)
  - `backend` (string): `local_dir | s3 | presigned_url`
  - `ref` (string): backend-specific locator
    - `local_dir`: relative path from the capsule root (e.g., `capsules/<capsule_id>/blobs/<blob_id>`)
    - `s3`: object key within the bucket/prefix (bucket is supplied out-of-band by `--out`)
    - `presigned_url`: same as s3 format (URL obtained via credential service)
- `is_archive` (boolean, optional) — if true, blob contains a compressed archive (v1.1)
- `archive_format` (string, optional) — archive format, e.g., `"7z"` (required if `is_archive` is true)

## 5.3 Consistency rules (v1, normative)
- `artifacts[].path` MUST be unique within a manifest.
- `blobs[].blob_id` MUST be unique within a manifest.
- Every `artifacts[].blob_id` MUST reference an entry in `blobs[]`.

## 6. `redaction.report.json` (normative)
### 6.1 Required fields (v1)
- `spec_version` (string) — MUST be `"v1"`
- `schema_version` (string) — semver for the report schema (e.g. `"1.0.0"`)
- `policy_version` (string)
- `created_at` (RFC3339 string)
- `capsule_id` (string) — UUIDv7 (generated even for `--dry-run`)
- `detectors` (array)
  - Each detector: `{ id, version?, config_hash }`
- `decisions` (array)
  - Each decision: `{ path, decision, class, reasons, detector_hits? }`
    - `decision`: `exclude | include_encrypted | include_redacted | include_plaintext`
    - `class`: `public | private | sensitive | forbidden`
    - `reasons`: array of rule IDs or policy labels (strings)
    - `detector_hits`: array of rule IDs (strings)
- `findings` (array)
  - Each finding: `{ path, rule_id, severity, locations }`
    - `severity`: `low | medium | high`
    - `locations`: array of `{ line?, start_byte?, end_byte? }`
- `findings_summary` (object)
  - `total` (int)
  - `by_class` (object)
  - `by_decision` (object)

### 6.2 Findings safety rule
Findings MUST NOT contain raw secret values or matching substrings.
Only types/rule IDs/locations (line numbers) are allowed.

## 7. `restore.report.json` (optional, v1)
### 7.1 Required fields (v1)
- `spec_version` (string) — MUST be `"v1"`
- `schema_version` (string) — semver for the report schema (e.g. `"1.0.0"`)
- `created_at` (RFC3339 string)
- `capsule_id` (string) — UUIDv7
- `target_workspace` (string) — path the restore was attempted into (string for audit; not used for validation)
- `results` (object)
  - `created` (array): list of `{ path, size_bytes, plaintext_hash }`
  - `skipped` (array): list of `{ path, reason }` (e.g., `exists`)
  - `overwritten` (array): list of `{ path, reason }`
  - `failed` (array): list of `{ path, error }`

## 8. Signature canonicalization (normative, v1)
To sign and verify the manifest in an interoperable way:
- Compute JSON Canonicalization Scheme bytes per **RFC 8785 (JCS)**.
- The signed payload is **the JCS-serialized manifest object with the `signature` field removed**.
- Convert to **UTF-8 bytes**.
- **Do not** append a trailing newline.

## 9. Status & next step
Schemas and examples are now provided:
- `schemas/v1/capsule.manifest.schema.json`
- `schemas/v1/redaction.report.schema.json`
- `schemas/v1/restore.report.schema.json`
- `examples/minimal/`, `examples/typical/`, `examples/redaction/`

Next step:
- Wire schema validation + example validation into CI/conformance.
