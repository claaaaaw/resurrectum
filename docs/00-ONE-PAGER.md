# Resurrectum ("Soul Immortality") — v1 One-Pager (OpenClaw-only)

Resurrectum: an AI-first resurrection rite for agents — revive identity, vows, and continuity (OpenClaw v1).

## Problem
OpenClaw agents are currently "mortal" across machines/sessions unless their working directory (memory/persona/ops) is preserved and safely moved. Teams need a **portable, versioned, encrypted, verifiable** package of an agent’s persistent state that can be exported/imported without breaking OpenClaw’s existing file conventions.

## Goal
Define a **Resurrectum**: a cryptographically protected, content-addressed, versioned bundle of OpenClaw state (memory + persona/contracts + ops + optional project context) that enables:
- **Revival**: restore an agent to a working OpenClaw directory deterministically.
- **Continuity**: keep long-term identity/behavior stable while allowing incremental updates.
- **Safety**: enforce redaction boundaries so secrets/PII don’t leak to untrusted storage.

## Audience
AI engineers implementing the export/import pipeline, schema(s), CLI, and conformance tests.

## v1 Scope (explicit)
**OpenClaw-only**. Resurrectum must be fully compatible with current OpenClaw workspace file patterns:
- Memory layer: `MEMORY.md`, `memory/*.md`, and durable state JSONs under `memory/`.
- Persona/contract layer: `SOUL.md`, `USER.md`, `IDENTITY.md`.
- Ops layer: `AGENTS.md`, `TOOLS.md`, `HEARTBEAT.md`.
- Optional project layer: `projects/**/STATUS.md`, small config snippets (redacted).

**Non-goals (v1)**
- Cross-framework “agent portability” beyond OpenClaw.
- Running remote execution attestation / TEEs.
- Multi-writer realtime sync (we support linear history + explicit merges later).
- Cloud hosted SaaS UI.

## Product Principles
- **AI-first**: Machine Layer is the source of truth (manifests + schemas + examples + conformance). Human docs are derived.
- **Content-addressed**: **ciphertext-addressed blobs** (`blob_id = sha256(ciphertext_bytes)`) plus plaintext hashes recorded for restore integrity.
- **E2EE by default** for remote storage; remote can be fully untrusted.
- **Deterministic restore**: same capsule → same restored files.
- **Extensible**: reserve room for future layers (vector indexes, tool state, multi-agent graphs).

## Core Concept: Two-Layer Spec
1) **Machine Layer (canonical)**
- `capsule.manifest.json` (versioned)
- `schemas/*.json` (JSON Schema)
- `examples/*`
- `conformance/*` tests and fixtures

2) **Human Layer (derived)**
- one-pager, PRD, architecture notes, diagrams, FAQ

## Minimal Deliverables for v1
- **Machine Layer contracts (must ship together)**
  - `capsule.manifest.json` + JSON Schema
  - `redaction.report.json` + JSON Schema
  - schema versioning (`schema_version` required in all JSON docs)
  - at least **3 examples** (minimal / typical / failure-redacted)
  - **conformance tests** + fixtures (round-trip, tamper, policy)
- **Export/Import**
  - export from an OpenClaw workspace into a capsule
  - import into a new/empty OpenClaw workspace
  - validate with schema + hash checks
- **Crypto (v1)**
  - encrypt payloads (AEAD)
  - **sign manifests (required)**
    - Ed25519
    - bytes-to-sign fixed: RFC 8785 JCS of manifest without `signature` (UTF-8, no trailing newline)
    - verifier must pin/trust signer key/fingerprint
  - key source: **passphrase → Argon2id → master key**
  - Argon2id params + salt recorded in manifest; HKDF `info` fixed to `capsule:blob`
- **Redaction policy (v1)**
  - strict defaults (OpenClaw allowlist; deny secrets/PII)
  - machine-readable redaction report

## Success Criteria
- Engineers can implement without guessing interfaces.
- A capsule round-trips: export → wipe workspace → import → agent behaves consistently.
- Remote storage can be assumed adversarial without leaking plaintext.

## Related docs
- Entry point / reading order: `README.md`
- Requirements: `01-PRD.md`
- Architecture overview: `02-ARCHITECTURE.md`
- Normative contracts: `03-SCHEMAS.md`
- CLI spec: `04-CLI-SPEC.md`
- Redaction boundary (normative): `07-REDACTION-POLICY.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`

## Notes for external comms
- **Moltbook content must be English** (marketing/community); internal engineering docs can be English-only.
