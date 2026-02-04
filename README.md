# Resurrectum

Resurrectum: an AI-first resurrection rite for agents — revive identity, vows, and continuity (OpenClaw v1).

Resurrectum v1 (OpenClaw-only) tooling with schema validation, redaction policy, crypto, storage backends,
and conformance tests.

## Components
- `spec`: manifests, schemas, conformance
- `ritebook`: PRD, docs, how-to
- `sigil`: signatures, verification, trust model
- `summon`: export/import/validate CLI entrypoint

## Quick checks
- Run conformance tests: `python -m pytest`
- Validate example documents: `summon-validate-examples`
