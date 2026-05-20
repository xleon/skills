---
name: markdown-preview
description: "Customize VS Code Markdown preview with a styled theme. Use when: personalizar vista previa markdown, markdown preview theme, add CSS to markdown preview, custom markdown styles, vista previa bonita."
argument-hint: "<theme-name> <project-root> (theme and project are optional)"
---

# Markdown Preview Customization

Applies a styled theme to VS Code's built-in Markdown preview.

## Available themes

### Light

| Theme | File | Style | Vibe |
|-------|------|-------|------|
| `github-light` | `theme-github-light.css` | Sans-serif | Clean, minimal — GitHub docs style |
| `solarized-light` | `theme-solarized-light.css` | Serif | Warm amber, scientifically tuned for readability |
| `bear` | `theme-bear.css` | Serif | Warm paper aesthetic, frosted frame |

### Dark

| Theme | File | Style | Vibe |
|-------|------|-------|------|
| `one-dark` | `theme-one-dark.css` | Sans-serif | Atom's iconic One Dark — blue/teal accents |
| `dracula` | `theme-dracula.css` | Sans-serif | High-contrast purple/pink, vibrant |
| `nord` | `theme-nord.css` | Sans-serif | Arctic cool-blue palette, easy on the eyes |

## Procedure

### 0. Ask the user which theme they want

If no theme was specified, ask:

> Which Markdown preview theme would you like?
>
> **Light:** `github-light`, `solarized-light`, `bear`
> **Dark:** `one-dark`, `dracula`, `nord`

### 1. Copy the CSS

```bash
cp ~/.copilot/skills/markdown-preview/assets/theme-<name>.css <project>/.vscode/markdown-preview.css
```

Example for Nord:

```bash
cp ~/.copilot/skills/markdown-preview/assets/theme-nord.css .vscode/markdown-preview.css
```

### 2. Wire up settings.json

**If `.vscode/settings.json` does not exist:**

```bash
cp ~/.copilot/skills/markdown-preview/assets/settings.json <project>/.vscode/settings.json
```

**If `.vscode/settings.json` already exists**, merge this key:

```json
"markdown.styles": [
    ".vscode/markdown-preview.css"
]
```

### 3. Verify

Open any `.md` file and toggle the preview (`⇧⌘V`). The theme applies immediately — no restart needed.

## Switching themes

Re-run this skill with a different theme name. The CSS file will be overwritten.
