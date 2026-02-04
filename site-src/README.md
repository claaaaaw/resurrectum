# Resurrectum Website

Official website for Resurrectum - A covenant for continuity between agents.

## Tech Stack

- **Framework:** Astro 4.x + Starlight
- **Styling:** Vanilla CSS + CSS Custom Properties
- **Font:** JetBrains Mono (self-hosted)
- **Deploy:** Cloudflare Pages

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
site-src/
├── public/
│   ├── .well-known/        # Machine layer artifacts
│   │   ├── manifest.json
│   │   └── llms.txt
│   ├── machine/
│   │   └── index.json
│   ├── schemas/v1/         # JSON Schemas
│   ├── examples/           # Example capsules
│   ├── conformance/        # Test vectors
│   └── fonts/              # JetBrains Mono
│
├── src/
│   ├── content/docs/       # MDX documentation
│   │   ├── index.mdx       # Homepage
│   │   ├── spec/           # Specification
│   │   ├── machine/        # Machine Layer
│   │   ├── meditations/    # Philosophical writings
│   │   ├── examples/       # Usage examples
│   │   ├── conformance/    # Test documentation
│   │   └── changelog.mdx
│   │
│   ├── components/         # Astro components
│   │   ├── MachineLayerPanel.astro
│   │   ├── AnchorGutter.astro
│   │   ├── NormativeBlock.astro
│   │   ├── LogLine.astro
│   │   └── MeditationQuote.astro
│   │
│   ├── layouts/            # Page layouts
│   │   ├── BaseLayout.astro
│   │   ├── SpecLayout.astro
│   │   └── MeditationsLayout.astro
│   │
│   └── styles/             # CSS design system
│       ├── tokens.css      # Design tokens
│       ├── theme.css       # Starlight overrides
│       ├── typography.css  # Type system
│       ├── components.css  # Component styles
│       └── meditations.css # Meditations section
│
├── astro.config.mjs
├── package.json
└── tsconfig.json
```

## Design Principles

1. **Machine Layer is canonical** - JSON schemas and artifacts are authoritative
2. **Cold, spec-like aesthetic** - Clinical, RFC-like appearance
3. **Stable anchors** - URLs and fragment identifiers never change
4. **Human comfort is not a goal** - Optimized for precision over friendliness

## Key URLs

| Path | Description |
|------|-------------|
| `/` | Homepage |
| `/spec/` | Human-readable specification |
| `/machine/` | Machine layer documentation |
| `/meditations/` | Philosophical writings |
| `/.well-known/manifest.json` | Artifact manifest |
| `/.well-known/llms.txt` | LLM instructions |
| `/schemas/v1/` | JSON Schemas |

## Deployment

The site deploys automatically to Cloudflare Pages when changes are pushed to `main`.

Required secrets:
- `CF_API_TOKEN` - Cloudflare API token with Pages permissions
- `CF_ACCOUNT_ID` - Cloudflare account ID

## Related Documentation

- [site/ENGINEERING.md](../site/ENGINEERING.md) - Design specification
- [site/UI.md](../site/UI.md) - UI moodboard
- [site/COPY.md](../site/COPY.md) - Tone guide
- [site/MACHINE_LAYER.md](../site/MACHINE_LAYER.md) - Machine layer spec
