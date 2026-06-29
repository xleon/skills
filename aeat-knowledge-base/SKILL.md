---
name: aeat-knowledge-base
description: "Reference knowledge base for Spain's Agencia Tributaria (sede electrónica). Covers IRPF, IVA, vivienda y otros inmuebles, modelos tributarios (100, 130, 131, 111, 115, 303, 349, 390), retenciones, pagos fraccionados, declaración de la Renta, régimen simplificado, estimación directa, Verifactu / Sistemas Informáticos de Facturación (SIF), plazos de declaración, tipos impositivos, y normativa vigente. Use when the user asks about Spanish taxes, fiscalidad, modelos AEAT, plazos trimestrales, normativa fiscal, retención IRPF, tipo IVA, Verifactu, autónomo, estimación directa, régimen simplificado, o cualquier duda fiscal de la sede.agenciatributaria.gob.es."
argument-hint: ""
---

# aeat-knowledge-base

Local, self-managed cache of the Agencia Tributaria's `sede.agenciatributaria.gob.es`,
covering IRPF, IVA and Vivienda y otros inmuebles. Answers Spanish fiscal questions
authoritatively without forcing the user to open a browser.

## When this skill applies

Load this skill whenever the user's question overlaps with Spanish fiscal topics:

- IRPF / Renta / declaración de la Renta, retenciones, pagos fraccionados (modelos 130, 131, 111, 115, 100).
- IVA, regímenes (general, simplificado), tipos, deducciones, modelos 303 / 349 / 390.
- Vivienda y otros inmuebles: alquiler, imputación de rentas, venta.
- Verifactu / SIF (Sistemas Informáticos de Facturación).
- Plazos de declaración trimestrales o anuales.
- Consultas del tipo "¿qué porcentaje de retención se aplica a X?" / "¿cuál es el plazo del modelo 303?" / "¿qué cambia este año en IRPF?".

## Source of truth (tiered)

1. The local cache at `cache/` inside the installed skill folder — preferred.
2. The live `sede.agenciatributaria.gob.es` — only if the cache cannot answer.

Treat AEAT sede electrónica as the canonical source. BOE law citations and DGT
consultancies vinculantes are secondary and must be cross-checked against AEAT.

## Workflow

### 1. Check cache freshness

The cache has a TTL of 10 days. Before answering, the agent must:

```bash
uv run scripts/fetch_aeat.py status
```

If `status` exits 0, the cache is fresh — go to step 3.
If `status` exits 1, the cache is stale or missing — go to step 2.

### 2. Refresh the cache (only if stale)

```bash
uv run scripts/fetch_aeat.py refresh
```

Or restrict to a single domain:

```bash
uv run scripts/fetch_aeat.py refresh --scope irpf
```

Add `--skip-pdfs` to avoid downloading linked PDFs in low-bandwidth situations.

The script writes one `.md` per page under `cache/<domain>/`, plus a `.state.json`
with the per-domain `last_refresh` timestamp.

If `refresh` fails because the network is unreachable, do **not** abort. Use the
already-existing cache files (even if stale) and tell the user up-front:

> Aviso: el caché local tiene más de 10 días y no se pudo contactar la sede AEAT
> (<detalle del error>). Respondo sobre lo último verificado.

### 3. Build the search index (once)

The skill searches the cache semantically rather than guessing slugs. Build
the index on first use:

```bash
uv run scripts/fetch_aeat.py index
```

After this, `refresh` and `url` rebuild the index automatically. Inspect it
with:

```bash
uv run scripts/search_aeat.py stats
```

Skip this step only if `cache/.embeddings.npy` already exists; in that case
it's already up to date.

### 4. Run a semantic query

```bash
uv run scripts/search_aeat.py search "<consulta>" --k 5 [--domain irpf|iva|vivienda|on-demand] [--json]
```

- The query can be the user's question verbatim, or a short Spanish phrase
  (e.g. `tipo IVA alquiler vivienda`, `plazo modelo 303`).
- `--domain` restricts retrieval to one section, useful when the user
  names a modelo (e.g. `--domain iva` for "modelo 303").
- `--json` emits one JSON object per result (handy for parsing).
- Scores are cosine similarities in `[0, 1]`; treat `>0.5` as relevant.

The command prints, per result: domain + slug, page title, source URL,
cumulative heading path, and a text snippet. No `read_file` is needed —
the citation is built into the output.

### 5. Cite and answer

- Use the printed `source:` URL as the citation for every numeric claim,
  percentage, threshold, or plazo you mention in the answer.
- If no chunk is good enough (top score `<0.4`), broaden the query, drop
  `--domain`, or fetch the relevant AEAT landing page on demand:
  ```bash
  uv run scripts/fetch_aeat.py url https://sede.agenciatributaria.gob.es/Sede/...
  ```
  This appends to the cache and auto-rebuilds the index.
- End the answer with one of:
  - "Fuentes verificadas (caché local del YYYY-MM-DD): <urls>." — normal case.
  - "Fuentes no verificadas: el caché tiene más de 10 días y no se pudo contactar la sede AEAT." — degraded case.

### 6. Never invent values

If neither the cache nor a fresh fetch can confirm a number, say so explicitly and
point the user at the manual práctico or AEAT asistente virtual. Do not extrapolate
from last year's values.

## Files

- `SKILL.md` — this file.
- `README.md` — user-facing usage docs.
- `scripts/fetch_aeat.py` — cache helper (`status`, `refresh`, `url`, `verify`, `index`).
- `scripts/search_aeat.py` — semantic search over the cache (`build`, `search`, `stats`, `info`).
- `cache/<domain>/*.md` — cached pages (HTML + PDFs discovered during refresh).
- `cache/.state.json` — per-domain `last_refresh` timestamps.
- `cache/.embeddings.npy` — float32 chunk embeddings (built by `search_aeat.py build`).
- `cache/.chunks.jsonl` — chunk metadata (id, text, source_url, domain, slug, title, heading_path, fetched_at).
- `cache/.search_meta.json` — index metadata (model, built_at, num_chunks, dim).
- `cache/.gitkeep` — empty marker so the `cache/` directory survives in git.

## Important constraints

- Do NOT fabricate tax figures. If the cache is empty and the network fails, admit it.
- The cache is the only read-only dependency for offline operation. Do not assume
  AEAT pages are reachable unless `refresh` has just succeeded.
- Default TTL is 10 days; the user can force a refresh with `refresh --force`.
- PDFs discovered during HTML refresh are downloaded eagerly by default. Use
  `--skip-pdfs` to opt out.
- The semantic index is optional. Build it once with `fetch_aeat.py index`; from then
  on it self-maintains after each `refresh` / `url`. Removing the index is safe; the
  cached `.md` files remain the source of truth.
- This skill does not modify `Docs/Info AEAT/` in any consumer repo. That folder
  is now read-only inspiration for recognition terms.
