# Memory Capsule — Docs (FINAL v1)

## Changelog (docs)
- Added this canonical `docs/README.md` entrypoint with reading order, locked v1 decisions, and an implementation checklist.
- Harmonized v1 decisions across all docs (ciphertext-hash blob IDs, **manifest signing required**, **passphrase → Argon2id** key source, strict allowlist/denylist).
- Locked additional v1 normative decisions to prevent implementation forks: **signing key trust model**, **bytes-to-sign canonicalization (RFC 8785 JCS)**, encoding rules, and determinism rules.
- Standardized doc headers to include: **Audience**, **v1 scope**, and **Related docs**; resolved contradictions.

---

## What this is
Memory Capsule is an **OpenClaw-only**, **AI-first** specification for exporting/importing an agent’s persistent workspace state as a **portable, versioned, encrypted, verifiable** capsule.

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

## v1 decisions already locked (index)
The **normative** text for these decisions lives in the Machine Layer and security/CLI specs:
- **Machine Layer (canonical):** `03-SCHEMAS.md`
- **CLI surface (canonical):** `04-CLI-SPEC.md`
- **Security/trust model (canonical):** `06-SECURITY-THREAT-MODEL.md`
- **Determinism semantics (canonical):** `02-ARCHITECTURE.md` + `03-SCHEMAS.md`

Locked decisions (summary only):
1) `blob_id = sha256(ciphertext_bytes)` (lowercase hex)
2) Manifest signing required (Ed25519) + verifier must pin/trust signer (fingerprint/keyring)
3) bytes-to-sign fixed: RFC 8785 JCS(manifest without `signature`) → UTF-8 bytes (no trailing newline)
4) Key source: passphrase → Argon2id
5) Strict allowlist/denylist, fail-closed
6) Determinism: byte-preserving restore; no requirement for stable ciphertext/blob IDs across exports
7) Encoding fixed: hash=hex; nonce/salt=base64url; sig/pubkey=base64url; `capsule_id`=UUIDv7
8) Canonical dry-run: `openclaw capsule export --dry-run`

## Implementation checklist (v1)
Use this as an engineering “definition of done” for a first complete implementation.

### Machine Layer (canonical)
- [ ] Implement `capsule.manifest.json` generation and validation per **03-SCHEMAS.md**.
- [ ] Implement `redaction.report.json` generation and validation per **03-SCHEMAS.md** + **07-REDACTION-POLICY.md**.
- [ ] Ensure `blob_id` is derived from ciphertext bytes everywhere (no plaintext-hash addressing).
- [ ] Ensure the manifest is signed and signature verification is enforced.

### Redaction & policy (security boundary)
- [ ] Default policy is strict/fail-closed with an explicit allowlist.
- [ ] Always-deny patterns and detectors implemented as specified; never include raw secret substrings in reports.
- [ ] `--dry-run` produces only the redaction report.

### Crypto
- [ ] AEAD encryption for all payloads by default.
- [ ] `passphrase → Argon2id → MK` key derivation implemented.
- [ ] Per-blob key derivation implemented (e.g., HKDF).

### Backends
- [ ] Local directory backend implemented per **05-STORAGE-BACKENDS.md**.
- [ ] S3-compatible backend implemented per **05-STORAGE-BACKENDS.md** (recommended for v1).

### CLI surface (normative)
- [ ] `export`, `import`, `validate` implemented per **04-CLI-SPEC.md**.
- [ ] Exit codes match the spec.
- [ ] Default overwrite behavior is safe (no overwrite unless explicitly requested).

### Conformance
- [ ] All required tests in **08-CONFORMANCE-TESTS.md** pass, including: strict policy failure, tamper detection, signature required, wrong passphrase.

## Where to record future changes
- Anything that would change a locked v1 decision: propose in **11-OPEN-QUESTIONS.md** and target **10-ROADMAP.md** for v1.1+ or v2.
