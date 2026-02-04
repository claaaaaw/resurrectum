# Memory Capsule — Storage Backends v1 (OpenClaw-only)

**Audience:** AI engineers

**v1 scope:** Storage backend interface and guarantees for OpenClaw-only Memory Capsule v1.

## 0. Purpose
Specify the storage backend interface and required guarantees for Memory Capsule v1.

## Related docs
- Architecture: `02-ARCHITECTURE.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`

v1 backends:
- **Required:** Local directory backend
- **Recommended:** S3/MinIO backend (S3-compatible)
- **Out of scope v1:** IPFS transport (reserved for v1.1+)

## 1. Storage assumptions
- Storage is **untrusted** (can read/modify/delete objects).
- Confidentiality comes from E2EE; integrity comes from ciphertext hashes + manifest signature.

## 2. Backend interface (normative)
A backend MUST implement these operations:

- `put_blob(blob_id, bytes) -> ref`
- `get_blob(blob_id) -> bytes`
- `has_blob(blob_id) -> bool`
- `put_document(path, bytes)` (for manifest/report)
- `get_document(path) -> bytes`
- `list(prefix) -> [paths]` (optional but helpful)

Where:
- `blob_id = sha256(ciphertext_bytes)` (v1 required; lowercase hex)
- documents include:
  - `capsule.manifest.json`
  - `redaction.report.json`
  - optional: `restore.report.json`

## 3. Required consistency guarantees
Backends MUST provide at least **read-after-write consistency** for:
- manifest/report documents
- blobs written by the same client run

If backend is eventually consistent, the implementation MUST add retries/backoff when reading after writing.

## 4. Local directory backend (required)
### 4.1 Layout (recommended)
- `capsule_id` is UUIDv7 (see `03-SCHEMAS.md`).

```
<out>/
  capsules/
    <capsule_id>/
      capsule.manifest.json
      redaction.report.json
      blobs/
        <blob_id>
```

### 4.2 Atomicity
- Write blobs first.
- Write redaction report next.
- Write manifest last.
- Prefer atomic writes (write temp + rename) for documents.

## 5. S3/MinIO backend (recommended)
### 5.1 Object layout (recommended)
Prefix: `capsules/<capsule_id>/`
- `capsules/<capsule_id>/capsule.manifest.json`
- `capsules/<capsule_id>/redaction.report.json`
- `capsules/<capsule_id>/blobs/<blob_id>`

### 5.2 Required properties
- Bucket versioning is optional but recommended.
- Server-side encryption is optional (E2EE already required); SSE may still be used for defense-in-depth.

### 5.3 Credentials
Credentials MUST NOT be stored inside the capsule.

## 6. Deletion semantics (honest)
- Local dir: delete can be strong (best effort depending on filesystem).
- S3: delete is best-effort and depends on provider retention/versioning/backups.

The spec MUST NOT promise global deletion once encrypted blobs are copied elsewhere.

## 7. Future extension points (v1.1+)
- IPFS cold backup: store encrypted blobs + signed manifest pointer.
- Replication: multi-backend mirroring.
- Garbage collection: remove unreferenced blobs after retention window.
