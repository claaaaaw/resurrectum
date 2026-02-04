# Memory Capsule (Soul Immortality) — PRD v1 (OpenClaw-only)

**Audience:** AI engineers

**v1 scope:** OpenClaw-only capsule export/import. AI-first (Machine Layer contracts are canonical). Untrusted storage assumed.

**Status:** Draft

## 1. Background / Context
OpenClaw persists agent continuity via a set of workspace files:
- **Memory:** `MEMORY.md`, daily logs in `memory/YYYY-MM-DD*.md`, plus state JSONs (e.g., `memory/*.json`).
- **Persona/Contracts:** `SOUL.md`, `USER.md`, `IDENTITY.md`.
- **Ops / Runbook:** `AGENTS.md`, `TOOLS.md`, `HEARTBEAT.md`.

Today this state is coupled to a local filesystem. We need a formal, portable representation that can be securely stored, transferred, versioned, and restored.

## 2. Problem Statement
We lack:
- A **stable contract** describing what “agent state” consists of (machine-readable).
- A **secure export/import** mechanism with integrity, confidentiality, and provenance.
- A **redaction boundary** so secrets/PII don’t get captured by default.

Result: fragile backups, inconsistent restores, and high risk when syncing to any remote.

## 3. Goals
### 3.1 Primary Goals
1) **Export** an OpenClaw workspace into a capsule with deterministic contents.
2) **Import** a capsule into a target OpenClaw workspace and restore files.
3) Provide **integrity verification** (hashes) and **schema validation**.
4) Provide **E2EE** encryption so remote storage can be untrusted.
5) Provide a **redaction framework** with machine-readable reporting.

### 3.2 Secondary Goals
- Enable incremental snapshots (dedupe by content addressing).
- Support “hot storage + cold backup” patterns (e.g., S3/MinIO hot; IPFS encrypted cold later).

## 4. Non-Goals (v1)
- A generic, cross-agent-framework interchange format.
- Automatic multi-device conflict resolution; no realtime sync.
- Server-side search/indexing over plaintext.
- UI product; CLI and libraries only.

## 5. Users / Personas
- **AI Engineer**: implements capsule spec + tooling.
- **Ops Engineer**: runs export/import in automation, needs validation and auditability.
- **Agent Runtime** (OpenClaw): consumes restored files with zero or minimal changes.

## 6. Core User Stories
1) As an engineer, I can run `openclaw capsule export` to produce a capsule artifact from a workspace.
2) As an engineer, I can run `openclaw capsule import` to reconstruct the workspace.
3) As an ops user, I can validate a capsule without decrypting payload (when encryption metadata allows) or with keys.
4) As a security reviewer, I can audit what was included/excluded and why (redaction report).

## 7. Functional Requirements
### 7.1 Capsule Composition (OpenClaw Compatibility)
- Must support inclusion of the following paths (defaults):
  - `MEMORY.md`
  - `memory/**` (md/json, allow extensible)
  - `SOUL.md`, `USER.md`, `IDENTITY.md`
  - `AGENTS.md`, `TOOLS.md`, `HEARTBEAT.md`
- Must support optional inclusion of:
  - `projects/**/STATUS.md`
  - selected project files via explicit allowlist

### 7.2 Manifest (Machine Layer)
- Export produces a **manifest** that lists:
  - `capsule_id` (UUIDv7)
  - capsule format version
  - source workspace info (non-sensitive)
  - included artifacts (path, type, size, hash, encryption ref)
  - redaction decisions and detectors that ran
  - provenance: created_at, creator tool version
  - **required signature over the manifest** (v1), including:
    - Ed25519 public key embedded in the manifest
    - RFC 8785 JCS bytes-to-sign definition
    - pinned/trusted signer model for verification

See `03-SCHEMAS.md` (normative) and `04-CLI-SPEC.md` (normative).

> Interface: `capsule.manifest.json` (JSON) + JSON Schema.

### 7.3 Encryption + Key Source (v1)
- Payload encryption must use an AEAD scheme (e.g., XChaCha20-Poly1305 or AES-256-GCM).
- Encrypt at **artifact** granularity by default (chunking is optional/future).
- Manifest must not contain plaintext secrets.
- **Key source (v1): passphrase → Argon2id → Master Key (MK).**
  - MK is used to derive per-blob keys via HKDF.
  - Key rotation is out-of-scope for v1; a new capsule can use new keys.

### 7.4 Import Semantics
- Import must be able to:
  - reconstruct directory tree
  - restore file bytes exactly
  - optionally write a restore report (what changed)
- Must not overwrite existing files unless explicitly specified.

### 7.5 Validation
- `validate` checks:
  - schema validity
  - hash integrity of payloads
  - signature validity (**required v1**) using RFC 8785 JCS bytes-to-sign
  - pinned/trusted signer requirement (do not trust the embedded public key by default)
  - policy compliance (e.g., no forbidden paths)

## 8. Sensitive Boundary / Redaction Policy (Required)
This is a **hard requirement** and part of the v1 spec.

### 8.1 Threat Model Summary
Assume remote storage is adversarial:
- can read, copy, and delete stored objects
- can serve tampered objects
- cannot break modern crypto

We must prevent:
- plaintext secrets/PII leaving the local machine
- silent tampering of restored state

### 8.2 Data Classification
Define 4 classes (machine-annotated in reports):
- **Public**: safe to store plaintext (rare).
- **Private**: store encrypted; OK to export.
- **Sensitive**: export only if encrypted and policy allows; require explicit opt-in (default off).
- **Forbidden**: never export (even encrypted) in v1 unless user explicitly overrides with `--i-know-what-im-doing`.

### 8.3 Default Policy (v1) — Strict (OpenClaw-first)
- Default export is **strict / fail-closed**.
- **Allowlist** only the OpenClaw core files (Section 7.1) plus optional `projects/**/STATUS.md`.
- **Denylist (always Forbidden by default)**, even if present inside the workspace:
  - `.env`, `**/*.pem`, `**/*id_rsa*`, `**/*token*`, `**/*cookies*.json`, browser profiles
  - `memory/moltbook.json` (credentials), `**/cookies*.json`, `**/*_cookies.json`
  - any file > configurable size limit (avoid accidental media dumps)
- Pattern detectors (heuristic, not perfect):
  - API keys (e.g., `sk-...`, `ghp_...`), JWTs
  - private key blocks (`-----BEGIN ... PRIVATE KEY-----`)
  - cookie/session fields (`session`, `csrf`, `auth`)

### 8.4 Redaction Actions
Per artifact, exporter may choose:
- **exclude** (default for Forbidden)
- **include_encrypted**
- **include_plaintext** (rare; should require explicit allow)
- **include_redacted** (content rewritten; store both hash of original? v1: store only redacted content)

### 8.5 Redaction Report
Export MUST emit `redaction.report.json` with:
- policy version
- detectors run + config
- per-file decision + reasons
- extracted "findings" (**types/rule IDs/locations only; never raw secret values or matching substrings**)

### 8.6 Human Safety Guardrails
- CLI requires confirmation when any Sensitive/Forbidden finding is detected.
- Provide `--dry-run` that only produces the redaction report.
- Provide `--strict` (default on) that **fails export** if Forbidden findings are detected.

## 9. Storage Backends (v1)
- Local directory backend (required).
- S3-compatible object storage backend (recommended).
- IPFS backend is **out of scope** for v1; reserve extension points.

## 10. Metrics / Acceptance Criteria
### 10.1 Acceptance Tests
- **Round-trip**: export a sample OpenClaw workspace → import into empty dir → byte-identical restore.
- **Policy**: ensure `.env` and detected private keys are excluded by default.
- **Tamper**: modify payload object → validation fails.
- **Determinism (v1)**: import restores byte-identical artifacts and `plaintext_hash` verifies. Re-export is NOT required to produce the same ciphertext/blob IDs; `created_at` may differ.

### 10.2 Success Metrics (qualitative)
- Engineers can implement CLI + library with only this spec.
- No plaintext secrets appear in storage during normal usage.

## 11. Open Questions
- Deterministic export mode (future): if we want stable ciphertext/nonces/blob_ids for the same inputs, do we add an explicit mode in v1.1+ or v2?
- How do we represent merges/conflicts (git-like DAG vs linear snapshots) in v1?
- How do we encode “Human Layer derived from Machine Layer” in repo layout?

> Note: v1 locks **manifest signing as required** and `blob_id = sha256(ciphertext_bytes)`; those are not open questions.

## Related docs
- Overview: `00-ONE-PAGER.md`
- Architecture: `02-ARCHITECTURE.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- CLI spec (normative): `04-CLI-SPEC.md`
- Redaction policy (normative): `07-REDACTION-POLICY.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`
- Conformance: `08-CONFORMANCE-TESTS.md`

## 12. Appendix: Current OpenClaw File Compatibility
This v1 spec MUST NOT require changing existing OpenClaw files. Capsule tooling operates over the current workspace layout.
