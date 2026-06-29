# Plan: aeat-knowledge-base (replace update-aeat-docs)

## Goal

Replace the `update-aeat-docs` workflow skill with `aeat-knowledge-base`: a Q&A skill that
auto-loads on Spanish fiscal topics (IRPF, IVA, vivienda, modelos, Verifactu, etc.) and answers
from a self-managed local cache of the Agencia Tributaria sede electrónica, refreshed at most
every 10 days.

## Non-goals

- RAG, embeddings, semantic search over the cache (version 2).
- Auto-committing cache content into any consumer repo.
- Modifying `~/Projects/gestion_autonomo/Docs/Info AEAT/` — that folder is read-only
  inspiration for recognition terms.

## Decisions (locked)

| # | Decision |
|---|---|
| 1 | Rename directory: `update-aeat-docs/` → `aeat-knowledge-base/`. Old dir deleted. |
| 2 | Cache location: `aeat-knowledge-base/cache/` inside this `.skills` repo. Gitignored except `.gitkeep`. |
| 3 | Cache state: `cache/.state.json` with `last_refresh` per domain + TTL 10 days. |
| 4 | Cache scope on `refresh`: 3 landing pages + ~14 key sub-pages (URLs inherited from prior SKILL.md). |
| 5 | Cache format: one structured `.md` per page (`# title`, source URL, fetched-at, body). |
| 6 | Refresh policy: trigger if cache empty OR any domain `last_refresh` older than 10 days. Network failures degrade gracefully (use stale cache + warn). |
| 7 | Recognition terms in `SKILL.md` frontmatter `description`, derived from `gestion_autonomo/Docs/Info AEAT/Links-AEAT.md` headings + section titles of TOC. |
| 8 | `install.sh` requires no code change (description sourced from frontmatter). Only root `README.md` skills table needs updating. |

## Files to create / modify / delete

### Delete

- `update-aeat-docs/` — entire directory (SKILL.md, README.md, scripts/fetch_aeat_index.py, `__pycache__/`).

### Create

- `aeat-knowledge-base/`
  - `SKILL.md` — new frontmatter + workflow (see "SKILL.md contents" below).
  - `README.md` — human-facing docs for the skill.
  - `scripts/fetch_aeat.py` — Python ≥ 3.10, standard library only. Reuses the heading-extractor logic from the old `fetch_aeat_index.py`.
  - `scripts/__init__.py` — empty marker (optional; only if we split helpers).
  - `cache/.gitkeep`
  - `cache/.state.json` — created on first successful refresh.

### Modify

- `.gitignore` — add `aeat-knowledge-base/cache/*` and `!aeat-knowledge-base/cache/.gitkeep`.
- `README.md` (root) — replace `update-aeat-docs` row with `aeat-knowledge-base` row.

## `scripts/fetch_aeat.py` CLI

```
uv run scripts/fetch_aeat.py status            # show domain ages, exit 0 if fresh / 1 if stale
uv run scripts/fetch_aeat.py refresh [--scope irpf|iva|vivienda|all] [--skip-pdfs]
                                              # refresh stale domains only; idempotent
uv run scripts/fetch_aeat.py refresh --force   # ignore TTL, refetch everything
uv run scripts/fetch_aeat.py url <url> [--skip-pdfs]
                                              # fetch a single URL on demand, append to cache
```

PDF handling (eager, opt-out with `--skip-pdfs`):

- After parsing each HTML page, collect `<a href>` links ending in `.pdf` (or `Content-Type: application/pdf` on HEAD) whose domain matches `ALLOWED_NETLOCS`.
- For each PDF discovered:
  - `GET` it with the same `User-Agent` and 25 s timeout.
  - Parse text with `pypdf.PdfReader`. Acceptable for AEAT manuales prácticos / normativa consolidada which are text-based. Scanned PDFs (no text layer) are detected by `len(reader.pages[0].extract_text()) < 50` after the first page; when detected, store a placeholder `.md` with the source URL and a "PDF sin capa de texto" note instead of empty content.
  - Write `cache/<slug>.md` with the same header structure as HTML pages:
    ```
    # <title>

    > Source: <url>
    > Fetched: <ISO-8601>

    <extracted text, pages joined with `\n\n---\n\n`, headings preserved as best-effort>
    ```
- Dep declared in script via PEP 723 `# /// script` block: `dependencies = ["pypdf"]`. `uv run` resolves it transparently (matches the convention of other Python-based skills).

Behavior:

- Reads `cache/.state.json`. For each requested domain, compares `last_refresh` to `now - 10 days`.
- If stale (or missing), `GET`s the URL(s) with a `User-Agent` header.
- Extracts `h2`/`h3` headings and main `<p>` content with `HTMLParser` (same approach as
  the old script; safe against AEAT HTML tweaks since we only need text).
- Writes `cache/<domain>/<slug>.md` with:
  ```
  # <title>

  > Source: <url>
  > Fetched: <ISO-8601>

  <extracted body, headings preserved as `##` / `###`, paragraphs joined, URLs kept inline>
  ```
- Updates `cache/.state.json`:
  ```json
  {
    "ttl_days": 10,
    "domains": {
      "irpf":     { "last_refresh": "2026-06-29T19:30:00+02:00", "last_status": "ok" },
      "iva":      { "last_refresh": "2026-06-29T19:30:00+02:00", "last_status": "ok" },
      "vivienda": { "last_refresh": "2026-06-29T19:30:00+02:00", "last_status": "ok" }
    }
  }
  ```
- On network failure: keeps old files, sets `last_status: "network-error"`, preserves prior
  `last_refresh`, prints warning to stderr, **exits 0** so the calling skill can still answer.

### URLs to seed (mirrored from prior skill)

- IRPF index + `/Renta.html`, plazos pagos fraccionados, importes pagos fraccionados, porcentajes retención, novedades.
- IVA index + plazos 303, régimen simplificado, régimen general, tipos impositivos, requisitos deducibilidad, operaciones intracomunitarias, SIF/Verifactu, novedades.
- Vivienda index + rendimiento alquiler, imputación de rentas.

## `SKILL.md` frontmatter (draft)

```yaml
---
name: aeat-knowledge-base
description: "Reference knowledge base for Spain's Agencia Tributaria (sede electrónica). Covers IRPF, IVA, vivienda y otros inmuebles, modelos tributarios (100, 130, 131, 111, 115, 303, 349, 390), retenciones, pagos fraccionados, declaración de la Renta, régimen simplificado, estimación directa, Verifactu / Sistemas Informáticos de Facturación (SIF), plazos de declaración, tipos impositivos, y normativa vigente. Use when the user asks about Spanish taxes, fiscalidad, modelos AEAT, plazos trimestrales, normativa fiscal, retención IRPF, tipo IVA, Verifactu, autónomo, estimación directa, régimen simplificado, o cualquier duda fiscal de la sede.agenciatributaria.gob.es."
argument-hint: ""
---
```

Length of `description` is intentionally long to maximize auto-load hit rate; `install.sh --list`
will print it verbatim (acceptable: matches the convention of other skills, e.g.
`opendataloader-ocr-integration`).

## `SKILL.md` workflow (body for the agent)

```
1. Determine the user question's scope (IRPF, IVA, Vivienda, modelos, plazos, Verifactu, ...).
2. Run `uv run scripts/fetch_aeat.py status`. If all domains are fresh (within TTL), skip to step 4.
3. Run `uv run scripts/fetch_aeat.py refresh`. Tolerate network failures: if it errors, proceed using existing
   cache and explicitly tell the user the cache date.
4. Read the relevant `cache/<domain>/*.md` files. They contain the source URL at the top of each file.
5. Cite the source URL next to every numeric/threshold claim. End the answer with
   "Fuentes verificadas (caché local del YYYY-MM-DD): <urls>." or "Fuentes no verificadas: el caché tiene
   más de 10 días y no se pudo contactar la sede AEAT." (depending on state).
6. If the cache does not contain the answer, ask one clarifying question OR fetch on demand with
   `uv run scripts/fetch_aeat.py url <url>` from the corresponding AEAT landing page. Never invent
   figures.
```

## `README.md` (skill-level)

Short, mirrors existing skill READMEs:

- What the skill is.
- How auto-load works (recognition terms in frontmatter).
- Commands (`status`, `refresh`, `url`).
- Cache location and TTL.
- Dependency on `uv` (matches other skills in this repo).
- Note that `Docs/Info AEAT/` in `gestion_autonomo` is no longer managed by the skill and remains untouched.

## Root `README.md` change

Single row update in the skills table:

```
| [`aeat-knowledge-base`](aeat-knowledge-base/) | Answer Spanish fiscal questions (IRPF, IVA, vivienda, modelos, Verifactu) from a locally cached snapshot of sede.agenciatributaria.gob.es, refreshed every 10 days |
```

## `.gitignore` addition

```
aeat-knowledge-base/cache/*
!aeat-knowledge-base/cache/.gitkeep
```

## Validation (executed by the implementation agent)

1. `bash install.sh --list` — must show `aeat-knowledge-base` with the new description.
2. `bash install.sh --help` — must not error.
3. With `cache/` empty, `uv run scripts/fetch_aeat.py status` exits 1 and prints "stale/missing".
4. `uv run scripts/fetch_aeat.py refresh --scope irpf` writes `cache/irpf/*.md` and `cache/.state.json`.
5. A second `refresh` <10 days later is a no-op (only checks state, no network).
6. A `refresh` with the network turned off (e.g. invalid URL via `--repo` shim) exits 0, leaves cache intact, sets `last_status: "network-error"`.
7. `ls aeat-knowledge-base/cache` after step 4 contains the expected `.md` files.
8. `uv run scripts/fetch_aeat.py refresh --scope iva` writes at least one `<slug>.md` derived from a discovered PDF link (verify by checking that the file's source URL ends in `.pdf`).
9. `uv run scripts/fetch_aeat.py refresh --scope iva --skip-pdfs` makes no PDF requests (verify via offline-cache stub or `--scope iva` count of `.pdf` source `.md` files = 0).

## Risks / open items

- AEAT can change HTML structure. Mitigation: extraction uses `HTMLParser` with conservative tag matching; if extraction returns nothing, fall back to whole-page text dump. Field-tested in the old script.
- PDF extraction quality depends on `pypdf` and the original PDF structure. AEAT manuales prácticos are text-based so quality is acceptable. Scanned PDFs fall back to placeholder + URL.
- First-run bandwidth: with PDFs eager, the initial `refresh` may take 30–90 s and leave 5–20 MB of cache. Mitigated by `--scope` per domain and `--skip-pdfs`.
- `description` length: long descriptions cost context on every load. Acceptable here because the alternative is silent miss on legit fiscal questions.
- Recognition terms aren't exhaustive. After two weeks of use, sweep agent logs for missed fiscal questions and add missing synonyms.
