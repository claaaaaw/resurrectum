# Memory Capsule — Schemas v1 (Machine Layer, OpenClaw-only)

**Audience:** AI engineers

**v1 scope:** Normative Machine Layer contracts for OpenClaw-only Memory Capsule v1.

## 0. Goal
This document defines the **canonical Machine Layer contracts** for Memory Capsule v1.
- The contracts are normative.
- Human docs must not contradict these contracts.

## Related docs
- Architecture overview: `02-ARCHITECTURE.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Backends: `05-STORAGE-BACKENDS.md`
- Redaction boundary (normative): `07-REDACTION-POLICY.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`
- Conformance tests: `08-CONFORMANCE-TESTS.md`

## 1. Versioning
- Capsule format versions: `v1`, `v1.1`, ... (non-breaking additions only within v1.x)
- Each JSON document includes:
  - `spec_version`: e.g. `"v1"`
  - `schema_version`: semver string for the schema itself

## 2. Required JSON documents (v1)
1) `capsule.manifest.json`
2) `redaction.report.json`

Optional (v1):
- `restore.report.json`

## 3. `capsule.manifest.json` (normative)
### 3.1 Purpose
Describes one capsule snapshot:
- what artifacts are included
- how to fetch their encrypted blobs
- how to validate integrity
- how to apply policy/redaction decisions

### 3.1.1 Encoding conventions (v1, normative)
To prevent implementation forks, v1 fixes encodings:
- **All hashes are lowercase hex**.
  - `sha256` = 64 hex chars.
- **Nonces/salts are base64url (unpadded)**.
- **Signatures and public keys are base64url (unpadded)**.
- `capsule_id` is a **UUIDv7** string.

> Note: storage backends may use their own encoding for object names, but manifest fields MUST follow the above.

### 3.2 Required top-level fields (v1)
- `spec_version` (string) — MUST be `"v1"`
- `capsule_id` (string) — UUIDv7
- `created_at` (RFC3339 string)
- `tool` (object): `{ name, version }`
- `source` (object): `{ workspace_fingerprint?, openclaw_version?, host_tz? }` (non-sensitive only)
- `crypto` (object)
  - `aead` (string)
  - `kdf` (string)
  - `key_source` (string): **MUST be `passphrase_argon2id` (v1)**
- `artifacts` (array)
- `blobs` (array)
- `redaction` (object)
  - `report_path` (string) => MUST be `redaction.report.json`
  - `policy_version` (string)
- `signature` (object) **required v1**

### 3.2.1 Signature object (v1, normative)
The `signature` object locks *both* the cryptographic algorithm and the bytes-to-sign rules.

Required fields:
- `alg` (string) — MUST be `ed25519`
- `payload_alg` (string) — MUST be `rfc8785_jcs_without_signature_utf8`
- `public_key` (string) — base64url (unpadded) encoding of raw Ed25519 public key bytes
- `signer_fingerprint` (string) — lowercase hex `sha256(public_key_bytes)`
- `sig` (string) — base64url (unpadded) signature over the canonicalized bytes

#### Bytes-to-sign (v1, normative)
`bytes_to_sign` are computed as:
1) Remove the top-level `signature` field from the manifest JSON object.
2) Canonicalize the remaining JSON using **RFC 8785 JSON Canonicalization Scheme (JCS)**.
3) UTF-8 encode the resulting canonical JSON text.
4) Sign exactly those bytes (no trailing newline).

Importer/validator MUST recompute `bytes_to_sign` exactly as above and verify the signature before any decrypt/restore.

### 3.3 Artifact record (v1)
Each artifact represents one file to be restored into an OpenClaw workspace.
- `path` (string) — relative, normalized, no `..`
- `kind` (string) — e.g. `memory`, `persona`, `ops`, `project`
- `mode` (string) — `include_encrypted | include_redacted | include_plaintext` (plaintext should be rare)
- `plaintext_hash` (string) — lowercase hex `sha256` of the **raw restored bytes** (deterministic restore check)
- `size_bytes` (int)
- `blob_id` (string) — lowercase hex; points into `blobs[]`

#### Determinism note (v1, normative)
- `plaintext_hash` MUST be stable for the same file bytes.
- v1 does NOT require re-export to produce the same ciphertext, the same nonce, or the same `blob_id`.

## 4. Blob records (normative)
### 4.1 Privacy rule
**Blob IDs MUST be derived from ciphertext bytes in v1.**
- `blob_id = sha256(ciphertext_bytes)` (**lowercase hex**)

### 4.2 Blob record fields (v1)
- `blob_id` (string) — lowercase hex `sha256(ciphertext_bytes)`
- `ciphertext_hash` (string) — same as `blob_id` (kept for clarity)
- `ciphertext_size_bytes` (int)
- `nonce` (string) — base64url (unpadded)
- `storage` (object)
  - `backend` (string): `local_dir | s3`
  - `ref` (string): backend-specific locator

## 5. `redaction.report.json` (normative)
### 5.1 Required fields (draft)
- `spec_version`
- `policy_version`
- `created_at`
- `detectors` (array): detectors run + config hash
- `decisions` (array)
- `findings_summary` (object)

### 5.2 Findings safety rule
Findings MUST NOT contain raw secret values or matching substrings.
Only types/rule IDs/locations (line numbers) are allowed.

## 6. Signature canonicalization (normative, v1)
To sign and verify the manifest in an interoperable way:
- Compute JSON Canonicalization Scheme bytes per **RFC 8785 (JCS)**.
- The signed payload is **the JCS-serialized manifest object with the `signature` field removed**.
- Convert to **UTF-8 bytes**.
- **Do not** append a trailing newline.

## 7. Next step
- Convert this doc into actual JSON Schemas:
  - `schemas/v1/capsule.manifest.schema.json`
    - fix `signature.alg = ed25519`
    - fix `signature.payload_alg = rfc8785_jcs_without_signature_utf8`
    - enforce encoding constraints (hash hex; nonce/key/sig base64url)
    - enforce `capsule_id` UUIDv7 format
  - `schemas/v1/redaction.report.schema.json`
- Add 3 examples:
  - minimal
  - typical
  - redaction-triggered (shows excluded files + report)
