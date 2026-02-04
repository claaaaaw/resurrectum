# Resurrectum — Architecture v1.1 (OpenClaw-only, AI-first)

**Audience:** AI engineers

**v1.1 scope:** OpenClaw-only. AI-first: Machine Layer contracts are canonical; this doc must not contradict `03-SCHEMAS.md`.

## 0. Design Constraints
- **OpenClaw compatibility:** capsule MUST operate on the current workspace layout and file semantics (no required format changes).
- **AI-first:** machine-readable artifacts (schemas/manifests/examples/tests) are the source of truth.
- **Untrusted remote:** remote storage is treated as hostile; confidentiality and integrity must be client-enforced.
- **Client-first:** all business logic (encryption/signing/verification) executes on client side.
- **Stateless service:** credential service has no database, no KV, no persistent state.
- **Decentralization-ready:** architecture designed for future migration to IPFS/decentralized storage.
- **Extensible:** reserve room for future: multi-agent graphs, vector indexes, IPFS cold backup, merge semantics.

## 1. System Overview
A capsule is a versioned set of encrypted blobs plus a manifest.

**High-level pipeline**
1) **Discovery**: enumerate candidate workspace files by policy.
2) **Classification & Redaction**: run detectors, decide per-artifact action.
3) **Pack**: split into artifacts (files); compute hashes.
4) **Encrypt**: encrypt payloads; record encryption metadata.
5) **Publish**: write to backend (local dir or S3) by **ciphertext hash**.
6) **Manifest**: write `capsule.manifest.json`; **sign it (required v1)**.
7) **Restore**: fetch objects, verify hash/signature, decrypt, write files.

## 2. Data Model (Machine Layer as SoT)
### 2.1 Key Objects (conceptual)
- **CapsuleManifest**: top-level JSON describing one snapshot/version.
- **Artifact**: a logical file entry (path + metadata) restored into workspace.
- **Blob**: stored encrypted bytes addressed by hash.
- **KeyEnvelope**: how data keys are derived/wrapped (v1 simple; future rotation).
- **RedactionReport**: decision log.

### 2.2 Identity Model (v1.1)
User identity is based on Ed25519 public key fingerprint:
```
User Identity = sha256(public_key_bytes) → hex string (64 characters)

No traditional "user registration":
1. Client generates Ed25519 keypair locally (resurrectum init)
2. Public key fingerprint = sha256(public_key_bytes) → hex string
3. Identity IS the fingerprint, no server-side record needed
```

### 2.3 Canonical IDs
- `capsule_id` = `{owner_fingerprint}/{uuid}` (v1.1 format)
  - `owner_fingerprint`: 64 hex chars (sha256 of owner's public key)
  - `uuid`: UUIDv7
  - Example: `a1b2c3d4e5f67890.../01234567-89ab-cdef-0123-456789abcdef`
- `blob_id = sha256(ciphertext_bytes)` (**v1 required**; lowercase hex; do not use plaintext-hash IDs).
- Optional extension: `x_artifact_id = sha256(normalized_path + ':' + plaintext_hash)` (lowercase hex).
  - `normalized_path` follows the path rules in `03-SCHEMAS.md` (POSIX, NFC, no `..`).

> v1 recommendation: **store ciphertext-addressed blobs** so storage never reveals plaintext hash correlation.

### 2.4 Access Control Model (v1.1)
```json
// manifest.json access field
{
  "access": {
    "owner": "ed25519:a1b2c3d4...",
    "readers": [
      "ed25519:e5f6g7h8...",
      "ed25519:i9j0k1l2..."
    ],
    "public": false
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `owner` | string | Owner's public key fingerprint, has write permission |
| `readers` | string[] | Authorized readers list (optional) |
| `public` | boolean | Whether publicly accessible (default false) |

Permission check logic:
```
read:  owner OR readers[] contains requester OR public=true
write: owner must match
```

### 2.3 Reserved Fields for Future
- `parents[]` for DAG history.
- `merges[]` and conflict markers.
- `indexes[]` for search/vector indexes.

## 3. Packaging Strategy
### 3.1 File-granularity vs Chunk-granularity
- **v1:** file-granularity artifacts only (no chunking fields in the v1 manifest).
- **v1.1+ (future):** chunking for large files or dedupe across daily notes.

### 3.2 Compression (v1.1)
- **v1.1:** optional 7z compression for storage efficiency.
- When enabled, all files are packed into a single 7z archive before encryption.
- Typical space savings: 60-80% for text-heavy workspaces.

```
Export flow (with compression):
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Scan     │───>│ Filter   │───>│ Pack 7z  │───>│ Encrypt  │───>│ Upload   │
│ workspace│    │ excludes │    │ compress │    │ sign     │    │ single   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    │ blob     │
                                                                 └──────────┘
```

Manifest compression field:
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

## 4. Crypto Design (v1)
### 4.1 Goals
- Confidentiality: payload plaintext never leaves the machine.
- Integrity: tampering detected.
- Provenance: **required signing in v1**.

### 4.2 Recommended Primitive Choices
- AEAD: XChaCha20-Poly1305 (preferred) or AES-256-GCM (identifiers in schema: `xchacha20-poly1305` / `aes-256-gcm`).
- KDF: HKDF-SHA256 for deriving per-blob keys from a master key.

### 4.3 Key Hierarchy (v1 minimal)
- **Master Key (MK)**: **passphrase-derived** secret via Argon2id (v1).
- **Data Key (DK)**: derived per blob:
  - `DK = HKDF-SHA256(MK, salt=base64url_decode(blob.nonce), info='capsule:blob', length=32)`.
  - `blob.nonce` MUST be unique per blob and generated with a CSPRNG.

Manifest stores:
- algorithm identifiers
- Argon2id parameters + salt
- per-blob nonces
- *no secrets*

### 4.4 Signing (v1 locked)
- Sign the manifest using an Ed25519 signing key.
- **Bytes-to-sign are locked:** RFC 8785 JCS of manifest with top-level `signature` removed (UTF-8, no trailing newline). See `03-SCHEMAS.md`.
- **Trust model (v1):** verification must be against a pinned/trusted signer identity (fingerprint or key file). Do not accept “any embedded public key” by default.
- Verification happens prior to decrypt/restore.

## 5. Redaction & Sensitive Boundary (Architecture)
Redaction is not a “prettify step”; it defines the security boundary.

### 5.1 Boundary Definition
- **Machine Layer canonical state** = what is in the capsule.
- **Human Layer** = views derived from capsule state.

Therefore: if something is excluded/redacted, it is **not part of the canonical revived agent** unless explicitly reintroduced.

### 5.2 Policy Engine
Inputs:
- file path
- file bytes (streaming)
- detector config

Outputs per file:
- decision: exclude | include_encrypted | include_plaintext | include_redacted
- reasons: detector hits, policy rule IDs

### 5.3 Detection
- content regex/heuristics (keys/tokens)
- file type detection (pem, sqlite, cookies)
- size thresholding

### 5.4 Reporting
- `redaction.report.json` is written alongside manifest.
- Findings include types and locations (line numbers) but never raw secret values.

Note: `include_plaintext` means **unredacted bytes**, not unencrypted bytes. Encryption is still required in v1.

## 6. Backends
### 6.1 Local Directory Backend (required)
Layout (v1.1 with owner_fp/uuid capsule_id):
```
<out>/
  capsules/
    {owner_fingerprint}/{uuid}/
      capsule.manifest.json
      redaction.report.json
      blobs/
        {blob_id}
```

Example:
```
capsules/a1b2c3d4e5f67890.../01234567-89ab-cdef-0123-456789abcdef/
  ├── capsule.manifest.json
  ├── redaction.report.json
  └── blobs/
      ├── abc123def456789...
      └── 789xyz123abc456...
```

### 6.2 S3/MinIO Backend (v1)
- bucket prefix per capsule_id
- objects stored by blob_id

### 6.3 Presigned URL Backend (v1.1)
For Cloudflare R2 and other S3-compatible storage:
- Client signs request → Credential service
- Credential service validates → Returns presigned URLs
- Client uses URLs directly with R2
- No proxy through credential service (low latency)

```
Export flow:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Client   │───>│ Cred Svc │───>│ Read     │───>│ Issue    │
│ sign req │    │ verify   │    │ manifest │    │ URLs     │
└──────────┘    └──────────┘    │ (new:skip)│    └────┬─────┘
                                └──────────┘         │
┌──────────┐    ┌──────────┐    ┌──────────┐         │
│ Upload   │<───│ Direct   │<───│ Client   │<────────┘
│ complete │    │ R2 upload│    │ encrypt  │
└──────────┘    └──────────┘    └──────────┘
```

### 6.4 Future: IPFS Cold Backup (v1.1+)
- store only encrypted blobs
- publish manifest hash (or signed manifest) as a verifiable pointer
- deletion semantics: never promise deletion on IPFS

## 7. CLI + Library Interfaces (to be specified)
Recommend two surfaces:
- `openclaw summon ...` CLI
- `summon` Python/TS library used by CLI

Core operations:
- `export(workspace_path, policy, backend, key_source) -> capsule_id`
- `import(capsule_ref, target_workspace_path, options)`
- `validate(capsule_ref, key_source?, strict_policy=true)`

## 8. Determinism & Reproducibility (v1 locked)
**v1 is byte-preserving (normative):**
- Import MUST restore artifact bytes exactly.
- `plaintext_hash` MUST be computed over the raw restored bytes (redacted bytes if applicable) and MUST verify on import.

**What v1 does *not* require:**
- Re-export producing the same ciphertext.
- Re-export producing the same nonce.
- Re-export producing the same `blob_id` (because `blob_id` is derived from ciphertext bytes and nonces are expected to be random).

Metadata:
- `created_at` may differ across exports.

Future:
- A “deterministic export mode” (stable nonces/ciphertexts) may be introduced in v1.1+ or v2, but is out of scope for v1.

## 9. Failure Modes / Recovery
- Missing blob → import fails with actionable report.
- Wrong key → decrypt fails; never write partial files unless `--partial`.
- Policy violations → fail closed by default.

## 10. Implementation Notes for OpenClaw Compatibility
- Treat `memory/` as an extensible namespace: do not hardcode filenames.
- Default policies must explicitly exclude known high-risk files even if they exist in workspace (e.g., cookie jars, `.env`).
- Do not require editing `SOUL.md/USER.md` formats.

## Related docs
- Requirements: `01-PRD.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- Redaction boundary (normative): `07-REDACTION-POLICY.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`
- Backends: `05-STORAGE-BACKENDS.md`

## 11. Open Questions (Architecture)
- How to represent snapshot lineage (`parents`) and merges.
- Whether to include a local index for fast diff/restore.

> Note: v1 locks `blob_id = sha256(ciphertext_bytes)` (ciphertext-addressed blobs).
