---
name: markdown-to-pdf
description: "Generate a PDF from a Markdown file using the shared markdown_to_pdf.py script (Playwright + markdown). Use when: generating PDF, converting markdown to PDF, export PDF, generate PDF, render document as PDF."
argument-hint: "<path/to/file.md>"
---

# Markdown to PDF

Converts any Markdown file to a styled A4 PDF using headless Chromium via Playwright.

## Script

[scripts/markdown_to_pdf.py](./scripts/markdown_to_pdf.py) — self-contained (PEP 723 inline deps), no project-level setup needed.

Canonical path: `~/Projects/.skills/markdown-to-pdf/scripts/markdown_to_pdf.py`

## Usage

```bash
uv run ~/Projects/.skills/markdown-to-pdf/scripts/markdown_to_pdf.py <input.md>
# output: same path with .pdf extension

uv run ~/Projects/.skills/markdown-to-pdf/scripts/markdown_to_pdf.py <input.md> -o <output.pdf>
```

## First-time setup on a new machine

```bash
uv run playwright install chromium
```

Only needed once per machine — Playwright caches the browser in `~/Library/Caches/ms-playwright/`.

## Adding to a project

No `pyproject.toml` changes required. The script resolves its own deps (`markdown`, `playwright`) via the `# /// script` block. Just run it with `uv run`.

## CSS theme

The script embeds a blue-toned A4 stylesheet:
- **H1** — dark blue background, white text
- **H2** — left-bordered blue panel, uppercase
- **Tables** — dark blue header, alternating rows
- **Blockquotes** — light blue tinted background

To customise the theme, edit the `PDF_CSS` constant in the script.
