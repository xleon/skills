# markdown-to-pdf

Skill to convert Markdown files into styled PDF documents using Playwright.

## What it does

- Renders Markdown to HTML.
- Applies a built-in print stylesheet.
- Exports an A4 PDF using headless Chromium.
- Supports default output path or explicit output file path.

## Script

- scripts/markdown_to_pdf.py

The script is self-contained and designed to run with uv.

## Usage

Convert a file using default output location:

```bash
uv run ~/Projects/.skills/markdown-to-pdf/scripts/markdown_to_pdf.py input.md
```

Set an explicit output file:

```bash
uv run ~/Projects/.skills/markdown-to-pdf/scripts/markdown_to_pdf.py input.md -o output.pdf
```

## First-time setup

Install Chromium once per machine:

```bash
uv run playwright install chromium
```

## Output

- Produces a PDF next to the input file by default.
- Keeps original Markdown unchanged.

## Notes

- Designed for local generation workflows.
- If Playwright browser binaries are missing, run the first-time setup command.
