---
name: markdown-preview
description: "Customize VS Code Markdown preview with a styled theme. Use when: personalizar vista previa markdown, markdown preview theme, add CSS to markdown preview, custom markdown styles, vista previa bonita."
argument-hint: "<project-root> (optional, defaults to current workspace)"
---

# Markdown Preview Customization

Applies a styled green-toned serif theme to VS Code's built-in Markdown preview.

## What it installs

Two files into `.vscode/`:

| File | Purpose |
|------|---------|
| [assets/markdown-preview.css](./assets/markdown-preview.css) | Theme stylesheet |
| [assets/settings.json](./assets/settings.json) | Registers the CSS via `markdown.styles` |

## Procedure

### 1. Copy the CSS

```bash
cp ~/Projects/.skills/markdown-preview/assets/markdown-preview.css <project>/.vscode/markdown-preview.css
```

### 2. Wire up settings.json

**If `.vscode/settings.json` does not exist:**

```bash
cp ~/Projects/.skills/markdown-preview/assets/settings.json <project>/.vscode/settings.json
```

**If `.vscode/settings.json` already exists**, merge this key:

```json
"markdown.styles": [
    ".vscode/markdown-preview.css"
]
```

### 3. Verify

Open any `.md` file and toggle the preview (`⇧⌘V`). The theme should apply immediately — no restart needed.

## Theme summary

- Soft green palette with serif body text
- Frosted glass frame effect (`body::before`)
- Styled `h2` with a teal bullet indicator
- Tinted blockquotes and code blocks
- Zebra-striped tables with hover highlight
