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

### 3. Read the relevant cached pages

Each cached page is structured as:

```
# <title>

> Source: <url>
> Fetched: <ISO timestamp>

<body>
```

Use `read_file` to load the relevant `cache/<domain>/<slug>.md` files and reason
over them.

### 4. Answer with citations

- Cite the source URL next to every numeric claim, percentage, threshold, or
  plazo (already at the top of each cached `.md`).
- If the cache does not cover the question, fetch the URL directly:
  ```bash
  uv run scripts/fetch_aeat.py url https://sede.agenciatributaria.gob.es/Sede/...
  ```
  This appends to the cache for future use.
- End the answer with one of:
  - "Fuentes verificadas (caché local del YYYY-MM-DD): <urls>." — normal case.
  - "Fuentes no verificadas: el caché tiene más de 10 días y no se pudo contactar la sede AEAT." — degraded case.

### 5. Never invent values

If neither the cache nor a fresh fetch can confirm a number, say so explicitly and
point the user at the manual práctico or AEAT asistente virtual. Do not extrapolate
from last year's values.

## Files

- `SKILL.md` — this file.
- `README.md` — user-facing usage docs.
- `scripts/fetch_aeat.py` — cache helper (`status`, `refresh`, `url`).
- `cache/<domain>/*.md` — cached pages (HTML + PDFs discovered during refresh).
- `cache/.state.json` — per-domain `last_refresh` timestamps.
- `cache/.gitkeep` — empty marker so the `cache/` directory survives in git.

## Important constraints

- Do NOT fabricate tax figures. If the cache is empty and the network fails, admit it.
- The cache is the only read-only dependency for offline operation. Do not assume
  AEAT pages are reachable unless `refresh` has just succeeded.
- Default TTL is 10 days; the user can force a refresh with `refresh --force`.
- PDFs discovered during HTML refresh are downloaded eagerly by default. Use
  `--skip-pdfs` to opt out.
- This skill does not modify `Docs/Info AEAT/` in any consumer repo. That folder
  is now read-only inspiration for recognition terms.
