# Resurrectum — Storage Backends v1.1 (OpenClaw-only)

**Audience:** AI engineers

**v1.1 scope:** Storage backend interface and guarantees for OpenClaw-only Resurrectum v1.1.

## 0. Purpose
Specify the storage backend interface and required guarantees for Resurrectum v1.1.

## Related docs
- Architecture: `02-ARCHITECTURE.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`

v1.1 backends:
- **Required:** Local directory backend
- **Recommended:** S3/MinIO backend (S3-compatible)
- **New v1.1:** Presigned URL backend (for Cloudflare R2)
- **Out of scope v1.1:** IPFS transport (reserved for v2+)

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
- `ref` returned by `put_blob` MUST be a stable locator used in `blobs[].storage.ref`:
  - `local_dir`: relative path from capsule root (e.g., `capsules/<capsule_id>/blobs/<blob_id>`)
  - `s3`: object key within the bucket/prefix (bucket is supplied out-of-band by `--out`)
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
### 4.1 Layout (v1.1)
- `capsule_id` format: `{owner_fingerprint}/{uuid}` (see `03-SCHEMAS.md`).

```
<out>/
  capsules/
    {owner_fingerprint}/
      {uuid}/
        capsule.manifest.json
        redaction.report.json
        blobs/
          {blob_id}
```

Example:
```
<out>/
  capsules/
    a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890/
      01925b6a-7c8d-7def-9012-345678abcdef/
        capsule.manifest.json
        redaction.report.json
        blobs/
          abc123def456789...
          789xyz123abc456...
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

## 6. Presigned URL Backend (v1.1)

### 6.1 Purpose
For Cloudflare R2 and other storage that doesn't support STS-style temporary credentials.
Client obtains presigned URLs from a credential service and uses them directly with storage.

### 6.2 Workflow
```
1. Client signs request with Ed25519 key
2. Credential service verifies signature
3. Credential service checks access permissions (via manifest.access)
4. Credential service returns presigned URLs (1 hour validity)
5. Client uses URLs directly with R2/S3
```

### 6.3 Credential Service API

**POST /presign**
```json
// Request
{
  "capsule_id": "owner_fp/uuid",
  "action": "read" | "write",
  "blobs": ["blob_id_1", "blob_id_2"],  // For write: blobs to upload
  "timestamp": 1706000000,
  "signature": "base64url(ed25519_sig)",
  "public_key": "base64url(ed25519_pk)"
}

// Response
{
  "expires_at": 1706003600,
  "urls": {
    "manifest": "https://...presigned...",
    "redaction_report": "https://...presigned...",
    "blobs": {
      "blob_id_1": "https://...presigned...",
      "blob_id_2": "https://...presigned..."
    }
  }
}
```

**GET /health**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": 1706000000
}
```

### 6.4 Access Control
- Write: `owner_fp` in capsule_id MUST match requester's fingerprint
- Read: Check manifest.access field:
  - `public: true` → allow
  - `owner` matches requester → allow
  - `readers[]` contains requester → allow
  - Otherwise → deny

### 6.5 Object Layout (R2)
```
capsules/{owner_fingerprint}/{uuid}/
  ├── capsule.manifest.json
  ├── redaction.report.json
  └── blobs/
      ├── {blob_id}
      └── ...
```

### 6.6 URL Caching
Client SHOULD cache presigned URLs locally:
- Cache location: `~/.resurrectum/cache/urls_{capsule_id}.json`
- Refresh buffer: 5 minutes before expiration
- Clear on demand: `resurrectum cache clear`

## 7. Deletion semantics (honest)
- Local dir: delete can be strong (best effort depending on filesystem).
- S3: delete is best-effort and depends on provider retention/versioning/backups.
- Presigned URL: delete requires credential service cooperation; best-effort.

The spec MUST NOT promise global deletion once encrypted blobs are copied elsewhere.

## 8. Future extension points (v2+)
- IPFS cold backup: store encrypted blobs + signed manifest pointer.
- Replication: multi-backend mirroring.
- Garbage collection: remove unreferenced blobs after retention window.
