# Resurrectum (v1, OpenClaw-only)

Resurrectum is an **AI-first** “resurrection rite” for OpenClaw agents: a spec + reference tooling for exporting/importing an agent workspace as a **portable, versioned, encrypted, and verifiable capsule**.

The **Machine Layer** (schemas/examples/conformance) is canonical. Human docs must not contradict it.

## What’s in this repo
- `docs/` — **Ritebook** (the canonical reading order + locked v1 decisions). Start here.
- `docs/schemas/` — JSON Schemas (normative).
- `docs/examples/` — Example documents (used by validation).
- `src/resurrectum/` — Python reference tooling:
  - `spec/` — schema loading, models, redaction policy helpers
  - `sigil/` — crypto/signing primitives
  - `summon/` — capsule assembly + storage abstractions
- `tests/` — unit + conformance-style tests.
- `conformance/fixtures/` — fixture workspaces and expected outputs.

## Frontend / UI
No frontend site is currently present (no Astro/Starlight/Next/Vite config, no `package.json`). Docs are Markdown in `docs/`.

## Read the docs
Open **`docs/README.md`** and follow the “Reading order (recommended)” section.

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"

pytest
summon-validate-examples
```

## Contributing
- Keep v1 **locked decisions** consistent across code + docs (`docs/README.md` lists what’s locked).
- Prefer changes that improve **conformance** (tests/fixtures/schemas) over prose.
- If you propose a breaking change, put it in `docs/11-OPEN-QUESTIONS.md` (likely v2).

## Status
- v1 spec is documented in `docs/`.
- Python tooling is an early reference implementation; expect iteration until conformance coverage is complete.
