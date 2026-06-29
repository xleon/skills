# opendataloader-ocr-integration

Generic, project-agnostic guide to install and operate `opendataloader-pdf` as a high-accuracy OCR/PDF extraction backend in any `uv`-managed Python project.

The skill is **interactive** — it detects the environment automatically and asks the user only for the values that cannot be inferred (project path, dep group name, port, languages, JDK location).

## What it covers

- Detect environment (OS, arch, Java availability, `uv` architecture).
- Install `opendataloader-pdf[hybrid]` via the project's `uv` dep group.
- Configure runtime env vars (port, OCR languages, backend auto-start).
- Start the hybrid backend and verify the `/health` endpoint.
- Diagnose common failures (Java not in PATH, Rosetta contamination, build stuck, port conflict, etc.).

## What it does NOT do

- It does not modify project source files (extractors, parsers, etc.).
- It does not assume a specific `pyproject.toml` group name; it asks.
- It does not silently rewrite the user's shell rc — it tells them what to export.

## Sub-commands

- `install` (default) — install the OCR dep group and verify the backend starts.
- `start` — start the hybrid backend in the foreground.
- `verify` — run the verification checklist only (no install).
- `diagnose` — print environment + connectivity diagnostics; suggest fixes.

If invoked without a sub-command, default to `install`.

## Dependencies

- Python project managed by `uv` (pyproject.toml + uv.lock).
- Java 11+ on PATH or via JAVA_HOME.
- ~2 GB of disk for OpenDataLoader transitive deps (torch, docling, etc.).

## Supported platforms

- macOS arm64 (recommended; beware of Rosetta contamination on `uv`).
- Linux x86_64 and arm64.
- macOS x86_64 is **not** reliably supported because some `torch` wheels are unavailable there.

## Files

- `SKILL.md` — the full interactive workflow + troubleshooting guide.

## Notes

- OpenDataLoader is a **fallback** for hard OCR cases. Default extraction (pdfplumber → pypdf → tesseract) is faster and lighter.
- First startup can take several minutes due to model download/load. Don't mistake that for a failure.
- The skill should never run `uv sync --group <NAME>` without first confirming the group exists in `pyproject.toml`.
