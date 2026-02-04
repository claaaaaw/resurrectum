# Resurrectum — Open Questions (track in one place)

**Audience:** AI engineers / maintainers

**v1 scope:** Track unresolved design questions for OpenClaw-only Resurrectum beyond the locked v1 decisions.

## Related docs
- Canonical entry point: `README.md`
- Roadmap: `10-ROADMAP.md`
- Requirements: `01-PRD.md`
- Architecture: `02-ARCHITECTURE.md`
- Normative contracts: `03-SCHEMAS.md`

## v1 decisions already locked
- blob_id derived from ciphertext bytes (`sha256(ciphertext_bytes)`, hex)
- manifest signing required (Ed25519) + pinned/trusted signer model
- bytes-to-sign locked (RFC 8785 JCS, manifest without `signature`, UTF-8, no trailing newline)
- key source: passphrase → Argon2id
- strict default allowlist/export policy
- determinism is byte-preserving (no requirement for stable ciphertext/blob IDs across exports)
- encoding conventions fixed (hash hex; nonce/key/sig base64url; capsule_id UUIDv7)

## Remaining questions
1) **Path privacy:** do we ever encrypt paths/filenames to reduce metadata leakage?
2) **Lineage model:** do we ship `parents[]` in v1.1, and do we guarantee linear history first?
3) **Unencrypted allowance:** do we ever allow unencrypted artifacts in a future version, or keep capsules strictly encrypted-only?
4) **Deterministic export mode (future):** if we want stable ciphertext/nonces/blob_ids for the same inputs, do we add an explicit deterministic mode in v1.1+ or v2?
5) **PII detection:** do we add stronger PII detectors (names/addresses) and how to manage false positives?
6) **Key recovery UX:** recovery phrase / key escrow options (must avoid violating security boundary).
7) **Indexing:** do we encapsulate vector indexes (encrypted) or always rebuild locally?
