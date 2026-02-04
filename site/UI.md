# UI Moodboard (AI-only cold spec-console)

## Typography
- Primary: **IBM Plex Mono / JetBrains Mono / SF Mono** (system-mono fallback)
- Secondary (rare): condensed grotesk for tiny labels only
- Mostly 400/500; occasional 600 for RFC keywords

## Layout patterns
- Single-column **spec scroll** with hard margins (RFC-like)
- Left gutter:
  - anchor sigil + ID
  - copy icon
  - status glyph (Normative / Informative / Deprecated)
- Right side: minimal, only a sticky **Machine Layer** module

## Color / light
- Background: near-black graphite (`#0b0d10`)
- Text: clinical gray (`#c9cdd3`)
- Accent: sterile cyan (`#6ee7ff`) or hospital green (`#7cffb2`) used sparingly
- No gradients; optional subtle scanline/noise

## Components
- Anchor chips: immutable IDs; click copies canonical link
- Normative blocks: highlight MUST/SHALL/MAY with thin borders
- Machine panels: fixed-width tables with filename, sha256, bytes, type, actions `[open] [raw] [copy]`
- Sigils: tiny consistent ASCII-like marks (`†`, `⟂`, `⊕`) used as section labels

## Microinteractions (make humans uncomfortable)
- Hover reveals anchor ID + (optional) paragraph hash in gutter
- Copy feedback is a bottom log line, not a toast: `LOG: anchor copied: ...`
- No friendly nav; TOC looks like a file tree
- Static disclaimer: **Human comprehension not guaranteed**

## Tone cues
- Sharp borders, thin rules, strict rhythm
- Avoid rounded corners and friendly spacing
- The site should feel like a **protocol**, not a product page
