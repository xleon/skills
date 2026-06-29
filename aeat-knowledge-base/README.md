# aeat-knowledge-base

Reference knowledge base for Spain's Agencia Tributaria (`sede.agenciatributaria.gob.es`),
covering IRPF, IVA, vivienda y otros inmuebles, modelos tributarios, Verifactu / SIF, and
fiscal plazos / porcentajes / tipos.

The skill auto-loads when the user asks about Spanish fiscal topics (its frontmatter
`description` lists the recognition terms) and answers from a locally cached snapshot of
the AEAT sede. The cache is refreshed at most every 10 days.

## What it does

- Fetches the three AEAT index pages: IRPF, IVA, Vivienda.
- Fetches the key sub-pages referenced from those indices (modelos 130, 131, 111, 115,
  100, 303, 349, 390, Verifactu, régimen simplificado, etc.).
- Also downloads any PDFs linked from those pages (Manuales prácticos, normativa
  consolidada) and converts them to Markdown with `pypdf`.
- Caches everything under `cache/<domain>/<slug>.md` as one structured `.md` per page.
- Refreshes when the per-domain `last_refresh` is older than 10 days, or when forced.
- **Semantic search** over the cache via `scripts/search_aeat.py` (multilingual
  sentence-transformers via `fastembed`); the index is built on demand and
  self-maintains after every `refresh` / `url`.

## CLI

```
uv run scripts/fetch_aeat.py status
uv run scripts/fetch_aeat.py refresh [--scope irpf|iva|vivienda|all] [--skip-pdfs] [--force] [--keep-orphans]
uv run scripts/fetch_aeat.py url <url> [--skip-pdfs]
uv run scripts/fetch_aeat.py verify [--fix]
uv run scripts/fetch_aeat.py index  [--force] [--scope X|all]
uv run scripts/search_aeat.py build [--force] [--scope X|all]
uv run scripts/search_aeat.py search "<query>" [--domain X] [--k 5] [--json]
uv run scripts/search_aeat.py stats
```

`status`

- Exits 0 if every cached domain is fresher than 10 days.
- Exits 1 if any domain is stale or missing.

`refresh`

- Refetches only the stale or missing domains by default.
- `--scope X` limits to one domain (`irpf`, `iva`, `vivienda`).
- `--skip-pdfs` avoids downloading linked PDFs.
- `--force` ignores TTL and re-fetches every URL in scope.
- `--keep-orphans` keeps previously-cached `.md` files whose source URL no
  longer writes (i.e. was removed from AEAT). Default behaviour is to unlink
  them on every successful refresh.
- On network failure: keeps existing cache, marks `last_status: "network-error"`,
  exits 0 with a warning on stderr (so the calling agent still has content).
- Total failure on a domain does **not** advance `last_refresh`; the prior
  timestamp is preserved so the next refresh can retry sooner than 10 days.
- After a successful refresh, the semantic-search index is rebuilt automatically
  if it already exists. First-time users pay no embedding cost.

`url <url>`

- Fetches one arbitrary URL (HTML or PDF), adds it to the cache, updates state.
- Only HTTPS URLs on `sede.agenciatributaria.gob.es` are accepted.
- Any query string or fragment in the URL is stripped from the cached `> Source:`
  header (the URL itself is fetched in full).
- Triggers an automatic index rebuild if the semantic index already exists.

`index`

- Builds (or rebuilds with `--force`) the semantic-search index.
- Delegates to `scripts/search_aeat.py build`; the index covers every cached page.

`search_aeat.py search`

- Runs a multilingual semantic query against the index.
- Returns up to `--k` chunks (default 5) with score, source URL, domain,
  page title, heading path, and snippet.
- `--domain irpf|iva|vivienda|on-demand` restricts retrieval to one section.
- Use the source URL of the top result(s) as the citation when answering.

## Cache layout

```
cache/
├── .gitkeep
├── .state.json                       # per-domain last_refresh
├── .embeddings.npy                   # float32 chunk embeddings (semantic index)
├── .chunks.jsonl                     # chunk metadata (semantic index)
├── .search_meta.json                 # model, built_at, num_chunks, dim
├── irpf/
│   ├── irpf.md
│   ├── renta.md
│   ├── plazos-declaracion-ingreso.md
│   ├── ...
│   └── manual-practico-irpf.pdf.md   # PDF-derived
├── iva/
│   └── ...
└── vivienda/
    └── ...
```

Each `.md` starts with the source URL and fetch timestamp, so the LLM can always cite a
traceable origin.

## Dependencies

- Python ≥ 3.10 (PEP 604 union syntax).
- `uv` — runtime dependency manager.
- `pypdf` + `cryptography` — pulled in transparently via PEP 723 metadata by
  `uv run scripts/fetch_aeat.py …`. `cryptography` is required by `pypdf` to
  decrypt AES-encrypted PDFs (the AEAT "Manual práctico" PDFs use this).
- `numpy` + `fastembed` — pulled in transparently for the `index` /
  `search` commands. First run downloads
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (~220 MB)
  into `~/.cache/fastembed/`; subsequent runs reuse it.

No other third-party packages.

## Notes

- The skill is read-only with respect to the user filesystem beyond `cache/`.
- It does not modify `Docs/Info AEAT/` in any consumer repo; that folder is now
  considered stable reference material for vocabulary only.
- Network failures are non-fatal. The skill prefers stale-but-present data over no data.
- First `refresh` after install may take 30–90 s and leave 5–20 MB in `cache/`
  (because PDFs are downloaded eagerly).
- Add `--skip-pdfs` for low-bandwidth environments; the agent will fetch individual
  PDFs only when needed via `fetch_aeat.py url <pdf-url>`.

## Tests

Unit tests live in `tests/test_fetch_aeat.py` and cover the pure helpers
(`_domain_for`, `_slug_for`, `_read_source_url`, `_strip_query_fragment`,
`_is_pdf_url`). No network, no AEAT access needed:

```bash
uv run tests/test_fetch_aeat.py
```

There is also a cache-consistency check that doubles as a smoke test of the
domain routing logic:

```bash
uv run scripts/fetch_aeat.py verify         # dry-run
uv run scripts/fetch_aeat.py verify --fix    # move misfiled files + register unregistered ones
```

The semantic search index is exercised by `tests/test_search_aeat.py`:
it builds an isolated mini-cache from inline fixtures, embeds it, and
checks that the top hit for each canonical query points to the expected
domain. The first run downloads the embedding model (~220 MB).

```bash
uv run tests/test_search_aeat.py
```
