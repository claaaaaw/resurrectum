# Resurrectum — Ritebook (Docs, FINAL v1)

Resurrectum: an AI-first resurrection rite for agents — revive identity, vows, and continuity (OpenClaw v1).

## Components
- `spec`: manifests, schemas, conformance
- `ritebook`: PRD, docs, how-to
- `sigil`: signatures, verification, trust model
- `summon`: export/import/validate CLI entrypoint

## Changelog (docs)
- Added this canonical `docs/README.md` entrypoint with reading order, locked v1 decisions, and an implementation checklist.
- Harmonized v1 decisions across all docs (ciphertext-hash blob IDs, **manifest signing required**, **passphrase → Argon2id** key source, strict allowlist/denylist).
- Locked additional v1 normative decisions to prevent implementation forks: **signing key trust model**, **bytes-to-sign canonicalization (RFC 8785 JCS)**, encoding rules, and determinism rules.
- Standardized doc headers to include: **Audience**, **v1 scope**, and **Related docs**; resolved contradictions.

---

## What this is
Resurrectum is an **OpenClaw-only**, **AI-first** specification for exporting/importing an agent’s persistent workspace state as a **portable, versioned, encrypted, verifiable** capsule.

**AI-first** means the **Machine Layer** is canonical (manifest + schemas + examples + conformance). Human-facing docs explain and motivate, but must not contradict the Machine Layer.

## v1 scope (locked)
- **OpenClaw workspace compatibility**: works with existing OpenClaw files; does not require changing their formats.
- **E2EE by default**: artifact payloads are encrypted with AEAD.
- **Untrusted storage**: backends are treated as hostile (read/modify/delete).
- **Deterministic restore**: import restores byte-identical file contents for included artifacts.

## Reading order (recommended)
1) **00-ONE-PAGER.md** — quick framing: what/why/scope
2) **01-PRD.md** — requirements, UX, acceptance criteria
3) **02-ARCHITECTURE.md** — system design & data model overview
4) **03-SCHEMAS.md** — *normative* Machine Layer contracts
5) **07-REDACTION-POLICY.md** — *normative* policy boundary (strict by default)
6) **06-SECURITY-THREAT-MODEL.md** — security properties & attacker model
7) **04-CLI-SPEC.md** — *normative* CLI behavior and exit codes
8) **05-STORAGE-BACKENDS.md** — backend guarantees & layouts
9) **08-CONFORMANCE-TESTS.md** — compatibility bar for any implementation
10) **09-MIGRATION-COMPAT.md** — forward/back compat rules
11) **10-ROADMAP.md** and **11-OPEN-QUESTIONS.md** — future work

## Canonical artifacts
- Schemas: `docs/schemas/`
- Examples: `docs/examples/`

## v1 decisions already locked (do not change)
These are **normative** for v1 and must be consistent everywhere. If any of these change, that is a v2 (breaking) discussion.

1) **Ciphertext-hash blob IDs**
   - `blob_id = sha256(ciphertext_bytes)` (lowercase hex)
   - Rationale: avoids leaking plaintext hash correlation to untrusted storage.

2) **Manifest signing is required + signing key trust model (v1)**
   - Export MUST sign the manifest.
   - Export MUST accept an explicit signing key input (recommended CLI: `--signing-key file:PATH`).
   - Manifest MUST embed the corresponding public key (so the capsule is self-describing).
   - Validation MUST require the verifier to **pin/trust** an expected signer identity (recommended CLI: `--trusted-signer <fingerprint>` or `--trusted-signer file:PATH`).
   - Fingerprint (recommended): `signer_fingerprint = sha256(public_key_bytes)` (lowercase hex).

3) **Bytes-to-sign canonicalization (v1)**
   - The signed payload is **RFC 8785 JSON Canonicalization Scheme (JCS)** of the manifest **with the `signature` field removed**.
   - The signed bytes are the UTF-8 encoding of that canonical JSON text **with no trailing newline**.
   - The schema MUST fix/lock the signature payload algorithm identifier (see `03-SCHEMAS.md`).

4) **Key source is passphrase-derived via Argon2id**
   - `passphrase → Argon2id → Master Key (MK)`
   - Per-blob keys derived from MK via **HKDF-SHA256 with `salt = blob.nonce` and `info = capsule:blob`**.
   - Argon2id params + salt are recorded in the manifest; HKDF `info` is fixed to `capsule:blob`.

5) **Strict allowlist/denylist, fail-closed policy**
   - Default export includes only OpenClaw core workspace paths + optional `projects/**/STATUS.md`.
   - High-risk files are denied by default (e.g., `.env`, keys, cookies).

6) **Determinism rules (v1 testable contract)**
   - v1 is **byte-preserving**: import MUST restore artifact bytes exactly; `plaintext_hash` MUST verify.
   - v1 does **not** require re-export to produce identical ciphertext, identical nonces, or identical `blob_id` (nonces are expected to be random).
   - `created_at` is allowed to differ across exports.
   - A future “deterministic export mode” (if desired) is out of scope for v1.

7) **Encoding conventions (v1)**
   - Hashes: lowercase hex (`sha256` → 64 hex chars).
   - Nonces/salts: base64url (unpadded).
   - Signatures and public keys: base64url (unpadded).
   - `capsule_id`: UUIDv7 string.
   - Paths: normalized POSIX relative paths (no `..` segments, NFC).

8) **Dry-run behavior (v1)**
   - The normative dry-run is `openclaw summon export --dry-run` (produce `redaction.report.json` only; no blobs; no manifest).
   - A separate `openclaw summon redact` command may exist as an alias/UX sugar, but is not required for conformance.

9) **No compression in v1**
   - Payload bytes are raw (or redacted) file bytes; no compression transforms are allowed.

## Implementation checklist (v1)
Use this as an engineering “definition of done” for a first complete implementation.

### Machine Layer (canonical)
- [ ] Implement `capsule.manifest.json` generation and validation per **03-SCHEMAS.md**.
- [ ] Implement `redaction.report.json` generation and validation per **03-SCHEMAS.md** + **07-REDACTION-POLICY.md**.
- [ ] Ensure `schema_version` is present in all JSON documents (manifest/report/restore report).
- [ ] Ensure `blob_id` is derived from ciphertext bytes everywhere (no plaintext-hash addressing).
- [ ] Ensure the manifest is signed and signature verification is enforced.

### Redaction & policy (security boundary)
- [ ] Default policy is strict/fail-closed with an explicit allowlist.
- [ ] Always-deny patterns and detectors implemented as specified; never include raw secret substrings in reports.
- [ ] `--dry-run` produces only the redaction report.

### Crypto
- [ ] AEAD encryption for all payloads by default.
- [ ] `passphrase → Argon2id → MK` key derivation implemented.
- [ ] Per-blob key derivation implemented (HKDF-SHA256, `salt = blob.nonce`, `info = capsule:blob`).
- [ ] Blob nonces are unique per blob (CSPRNG).
- [ ] Manifest records Argon2id parameters + salt and fixed `hkdf_info`.

### Backends
- [ ] Local directory backend implemented per **05-STORAGE-BACKENDS.md**.
- [ ] S3-compatible backend implemented per **05-STORAGE-BACKENDS.md** (recommended for v1).

### CLI surface (normative)
- [ ] `export`, `import`, `validate`, `redact --dry-run` implemented per **04-CLI-SPEC.md**.
- [ ] Exit codes match the spec.
- [ ] Default overwrite behavior is safe (no overwrite unless explicitly requested).

### Conformance
- [ ] All required tests in **08-CONFORMANCE-TESTS.md** pass, including: strict policy failure, tamper detection, signature required, wrong passphrase.

## Where to record future changes
- Anything that would change a locked v1 decision: propose in **11-OPEN-QUESTIONS.md** and target **10-ROADMAP.md** for v1.1+ or v2.
