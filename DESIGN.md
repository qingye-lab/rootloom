---
name: Rootloom
description: A tactile, evidence-first product site for a Codex-native engineering workflow with a bounded Agent Plugins preview.
colors:
  canvas: "oklch(100% 0 0)"
  surface: "oklch(97.5% 0.004 285)"
  ink: "oklch(18% 0.015 285)"
  muted: "oklch(46% 0.015 285)"
  rule: "oklch(87% 0.008 285)"
  violet: "oklch(61% 0.19 292)"
  coral: "oklch(67% 0.19 27)"
  orange: "oklch(69% 0.17 55)"
  blue: "oklch(58% 0.19 255)"
  green: "oklch(48% 0.13 150)"
typography:
  display:
    fontFamily: "Avenir Next, Avenir, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "clamp(3.25rem, 7vw, 5.75rem)"
    fontWeight: 650
    lineHeight: 0.98
    letterSpacing: "-0.035em"
  body:
    fontFamily: "Avenir Next, Avenir, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 450
    lineHeight: 1.65
  label:
    fontFamily: "Avenir Next, Avenir, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 650
    lineHeight: 1.2
  code:
    fontFamily: "SFMono-Regular, Cascadia Code, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.5
rounded:
  control: "8px"
  media: "12px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "20px"
  lg: "32px"
  xl: "64px"
  section: "clamp(88px, 12vw, 160px)"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.canvas}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "14px 20px"
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "14px 20px"
  command:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.media}"
    padding: "16px 18px"
---

<!-- SEED -->

# Design System: Rootloom

## 1. Overview

**Creative North Star: "The Working Loom"**

Rootloom should feel like a precise workshop tool shown on a clean bench. The hand-drawn black cat and mechanical loom carry the human character; the surrounding interface stays exact, quiet, and easy to inspect. Strong black rules, thread-like connectors, and a few illustration-derived spot colors turn the engineering sequence into a visible object without dressing the page as a terminal.

The public site uses open bands and rails instead of repeated feature cards. Dense technical contracts appear only after the visitor understands the daily workflow. It explicitly rejects generic purple-gradient SaaS pages, glass panels, repetitive feature-card grids, terminal cosplay, fake metrics, inflated AI claims, and dense audit terminology in the first viewport.

**Key Characteristics:**

- True white canvas with near-black structural ink.
- One decisive raster illustration rather than scattered decorative icons.
- Open, asymmetric layouts connected by thin rules and thread paths.
- Plainspoken product copy, real commands, and visible limits.
- Spot color marks meaning; it never becomes ambient decoration.

## 2. Colors

The palette comes directly from the loom illustration: black ink on white, with coral, orange, blue, green, and violet used as small functional accents.

### Primary

- **Workshop Ink** (`oklch(18% 0.015 285)`): headings, navigation, primary actions, and structural rules.
- **Rootloom Violet** (`oklch(61% 0.19 292)`): the brand link and a limited set of focus or active states.

### Secondary

- **Evidence Coral** (`oklch(67% 0.19 27)`): evidence and problem markers.
- **Scope Orange** (`oklch(69% 0.17 55)`): ownership and scope markers.
- **Test Blue** (`oklch(58% 0.19 255)`): verification steps and links within workflow diagrams.
- **Verified Green** (`oklch(48% 0.13 150)`): successful completion, always paired with text or a check mark.

### Neutral

- **Canvas White** (`oklch(100% 0 0)`): the page background.
- **Tool Surface** (`oklch(97.5% 0.004 285)`): code commands and restrained grouped content.
- **Quiet Ink** (`oklch(46% 0.015 285)`): supporting text that still meets contrast requirements.
- **Rule Gray** (`oklch(87% 0.008 285)`): separators and inactive rails.

**The Spot Color Rule.** Accent colors explain state or sequence and should occupy less than 12% of any viewport.

## 3. Typography

**Display Font:** Avenir Next, with Segoe UI and CJK system sans fallbacks

**Body Font:** Avenir Next, with Segoe UI and CJK system sans fallbacks
**Label/Mono Font:** SFMono-Regular, Cascadia Code, or Consolas for commands only

**Character:** The main family is direct and slightly mechanical without pretending the whole page is a terminal. Monospace is reserved for literal commands and Skill names.

### Hierarchy

- **Display** (650, `clamp(3.25rem, 7vw, 5.75rem)`, 0.98): one hero statement; never all caps.
- **Headline** (650, `clamp(2.25rem, 4.5vw, 4rem)`, 1.05): major section arguments.
- **Title** (650, `clamp(1.25rem, 2vw, 1.75rem)`, 1.2): workflow names and comparison labels.
- **Body** (450, `1.125rem`, 1.65): explanations capped at 68 characters per line.
- **Label** (650, `0.875rem`, normal case): navigation and controls; never used as a repeated decorative eyebrow.

**The Literal Mono Rule.** Monospace means copyable code, a Skill name, or machine output. It is not a general mood.

## 4. Elevation

The system is flat by default. Hierarchy comes from white space, rules, and tonal bands. Hovered controls may move by one or two pixels, but containers do not use ambient card shadows.

**The Bench Rule.** Content rests on the page like tools on a workbench; it does not float in stacks of glass or shadow.

## 5. Components

### Buttons

- **Shape:** compact rectangle with an 8px radius.
- **Primary:** Verified Green background for the install action, Canvas White text, `14px 20px` padding. Other high-emphasis actions may use Workshop Ink.
- **Hover / Focus:** move up 1px on hover; use a 3px violet focus outline with 3px offset.
- **Secondary:** white background, ink text, and a single ink border without a shadow.

### Cards / Containers

- **Corner Style:** 12px only where grouping materially helps, such as the command block.
- **Background:** Canvas White or Tool Surface.
- **Shadow Strategy:** none at rest.
- **Border:** full neutral rule, never a colored side stripe.
- **Internal Padding:** 20-32px based on density.

### Navigation

- Rootloom wordmark on the left, essential section links in the center, and language/GitHub actions on the right.
- Hover and active states use an underline or ink shift, not pills.
- Mobile navigation becomes a native disclosure button with visible focus and a simple vertical list.

### Command Block

- Uses the Tool Surface background, a 12px radius, and literal monospace text.
- The copy control has a text label and state confirmation; the clipboard icon is never the only cue.

### Workflow Rail

- A real ordered sequence with five steps, connected by a thin horizontal or vertical rule.
- Each step has one spot color, a short action title, and one sentence of evidence. It is not a grid of interchangeable feature cards.

## 6. Do's and Don'ts

### Do:

- **Do** keep the first installation action visible in the first viewport.
- **Do** use the cat-at-the-loom illustration as the single signature image and preserve its true white background.
- **Do** show the sequence from repository evidence to a verified completion report.
- **Do** pair status colors with words, symbols, or sequence position.
- **Do** keep technical contracts behind progressive disclosure after the daily workflow is clear.

### Don't:

- **Don't** use generic purple-gradient SaaS pages, glass panels, or soft glowing blobs.
- **Don't** build repetitive feature-card grids, nested cards, or giant rounded section wrappers.
- **Don't** use terminal cosplay, fake metrics, inflated AI claims, or dense audit terminology in the first viewport.
- **Don't** use a colored `border-left` or `border-right` accent wider than 1px.
- **Don't** treat test success as proof of correctness or make optional evidence machinery look mandatory.
- **Don't** use cream, beige, parchment, or tinted off-white as the page canvas.
