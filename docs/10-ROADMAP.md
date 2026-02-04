# Resurrectum — Roadmap

**Audience:** AI engineers / maintainers

**v1 scope:** Planning document for OpenClaw-only Resurrectum spec and tooling.

## Related docs
- Canonical entry point: `README.md`
- Requirements: `01-PRD.md`
- Architecture: `02-ARCHITECTURE.md`
- Open questions: `11-OPEN-QUESTIONS.md`

## v1 (OpenClaw-only) — current focus
Deliver a complete Machine Layer + tooling spec suitable for implementation:
- Manifest + redaction report schemas
- Restore report schema (optional output, but schema defined)
- CLI spec (export/import/validate/dry-run)
- Backends (local dir + S3/MinIO)
- Signing + E2EE defaults
- Strict redaction policy
- Conformance tests

## v1.1 (non-breaking)
- Optional chunking for large artifacts (dedupe)
- Lineage fields: `parents[]` (linear history at minimum)
- Optional local restore cache/index
- Optional export of encrypted CAR for IPFS cold backup (no strong delete promises)

## v1.2+
- Explicit merge semantics (two-parent merge) + conflict markers
- Multi-agent capsule graph (capsules referencing other capsules)
- Optional path encryption / metadata minimization

## v2 (breaking)
- If needed: stronger canonicalization rules, new manifest model, or new crypto envelope.
