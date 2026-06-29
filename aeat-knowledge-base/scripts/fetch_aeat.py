#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf", "cryptography"]
# ///
"""
Cache helper for the `aeat-knowledge-base` skill.

Maintains a local, structured snapshot of the Agencia Tributaria sede electrónica so
the skill can answer Spanish fiscal questions (IRPF, IVA, vivienda, modelos,
Verifactu / SIF) without forcing the user to open a browser.

Commands:

    uv run scripts/fetch_aeat.py status
    uv run scripts/fetch_aeat.py refresh [--scope irpf|iva|vivienda|all] [--skip-pdfs] [--force] [--keep-orphans]
    uv run scripts/fetch_aeat.py url <url> [--skip-pdfs]

Cache layout:

    cache/
    ├── .state.json
    ├── irpf/<slug>.md
    ├── iva/<slug>.md
    ├── vivienda/<slug>.md
    └── on-demand/<slug>.md        # anything fetched via `url`

Each `.md` is structured as:

    # <title>

    > Source: <url>
    > Fetched: <ISO-8601>

    <body>
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore[assignment]

INDEX_PAGES: dict[str, str] = {
    "irpf": "https://sede.agenciatributaria.gob.es/Sede/irpf.html",
    "iva": "https://sede.agenciatributaria.gob.es/Sede/iva.html",
    "vivienda": "https://sede.agenciatributaria.gob.es/Sede/vivienda-otros-inmuebles.html",
}

# Key sub-pages to fetch eagerly on first `refresh`. URLs mirror the previous
# skill's curated list (each starts with the matching index path).
SEED_SUBPAGES: dict[str, list[str]] = {
    "irpf": [
        "https://sede.agenciatributaria.gob.es/Sede/Renta.html",
        "https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/pagos-fraccionados/plazos-declaracion-ingreso.html",
        "https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/pagos-fraccionados/importe-pagos-fraccionados.html",
        "https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/retenciones-ingresos-cuenta/porcentajes-retencion-aplicables-distintas-rentas.html",
        "https://sede.agenciatributaria.gob.es/Sede/irpf/novedades-impuesto.html",
    ],
    "iva": [
        "https://sede.agenciatributaria.gob.es/Sede/iva/presentar-declaracion-iva-modelo-303/plazo-presentacion-modelo-303.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/regimenes-tributacion-iva/regimen-simplificado.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/regimenes-tributacion-iva/regimen-general.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/calculo-iva-repercutido-clientes/tipos-impositivos-iva.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/que-iva-soportado-puedo-deducir/que-requisitos-debo-cumplir-poder-iva.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-comercio-exterior/adquisiciones-entregas-intracomunitarias.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu.html",
        "https://sede.agenciatributaria.gob.es/Sede/iva/novedades.html",
    ],
    "vivienda": [
        "https://sede.agenciatributaria.gob.es/Sede/vivienda-otros-inmuebles/tributacion-arrendador-viviendas-otros-inmuebles/calculo-rendimiento-alquiler-inmueble.html",
        "https://sede.agenciatributaria.gob.es/Sede/vivienda-otros-inmuebles/imputacion-rentas-inmobiliarias.html",
    ],
}

ALLOWED_NETLOCS: frozenset[str] = frozenset({
    "sede.agenciatributaria.gob.es",
    "www.sede.agenciatributaria.gob.es",
})

DEFAULT_TTL_DAYS = 10
DEFAULT_TIMEOUT = 25.0
USER_AGENT = "kilo-aeat-knowledge-base/1.0 (+https://sede.agenciatributaria.gob.es)"
PDF_TEXT_THRESHOLD = 50  # chars; below this we assume scanned / image-only

SKILL_ROOT: Path = Path(__file__).resolve().parent.parent
CACHE_DIR: Path = SKILL_ROOT / "cache"
STATE_FILE: Path = CACHE_DIR / ".state.json"
STATE_TMP: Path = CACHE_DIR / ".state.json.tmp"

# Event kinds emitted by _ContentExtractor in document order.
EVT_HEADING = "heading"
EVT_PARAGRAPH = "paragraph"


# ----------------------------- HTTP --------------------------------------------

def _http_get(url: str, *, timeout: float = DEFAULT_TIMEOUT, accept: str = "*/*") -> bytes:
    """GET a URL with the configured User-Agent. Raise on non-2xx.

    AEAT occasionally publishes URLs with literal spaces or other characters that
    `urllib` refuses to send. We percent-encode the path component while keeping
    `?query` fragments intact."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"refusing non-HTTPS URL: {url!r}")
    encoded_path = urllib.parse.quote(parsed.path, safe="/")
    encoded = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        encoded_path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    req = urllib.request.Request(encoded, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    body = _http_get(url, timeout=timeout, accept="text/html,application/xhtml+xml")
    return body.decode("utf-8", errors="replace")


def fetch_pdf_bytes(url: str, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    return _http_get(url, timeout=timeout, accept="application/pdf")


# ----------------------------- helpers ----------------------------------------

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _canonicalize_url(href: str, base: str) -> str | None:
    """Resolve + canonicalize an AEAT internal link, forcing HTTPS.

    Returns an absolute URL with `?query`/`#fragment` preserved *only* for the
    network fetch — callers that want a display-only URL should call
    `_strip_query_fragment` on the result."""
    if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
        return None
    full = urllib.parse.urljoin(base, href)
    parsed = urllib.parse.urlparse(full)
    if parsed.netloc not in ALLOWED_NETLOCS:
        return None
    if parsed.scheme and parsed.scheme != "https":
        # Force HTTPS regardless of what the HTML declared.
        parsed = parsed._replace(scheme="https")
    cleaned = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return cleaned.rstrip("/")


def _strip_query_fragment(url: str) -> str:
    """Return the URL with empty query/fragment for display / cache headers."""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _is_pdf_url(url: str) -> bool:
    return urllib.parse.urlparse(url).path.lower().endswith(".pdf")


# ----------------------------- HTML extraction ---------------------------------

class _ContentExtractor(HTMLParser):
    """Extract page title and a clean body text/headings from AEAT HTML.

    Emits an ordered stream of (kind, payload) so the document structure is
    preserved in the final Markdown rendering."""

    SKIP_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "form"}

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.in_title: bool = False
        self.events: list[tuple[str, str]] = []  # (kind, payload)
        self._skip_depth: int = 0
        self._current_heading_level: int | None = None
        self._heading_buf: list[str] = []
        self._current_paragraph: list[str] = []
        self._active_buf: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        t = tag.lower()
        if t == "title":
            self.in_title = True
            self.title_parts = []
            return
        if t in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if t in {"h1", "h2", "h3", "h4"}:
            self._flush_paragraph()
            self._current_heading_level = int(t[1])
            self._heading_buf = []
            self._active_buf = self._heading_buf
            return
        if t == "p":
            self._current_paragraph = []
            self._active_buf = self._current_paragraph
            return
        if t == "br":
            if self._active_buf is self._current_paragraph:
                self._flush_paragraph()
            return

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title":
            self.in_title = False
            return
        if t in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if t in {"h1", "h2", "h3", "h4"} and self._current_heading_level is not None:
            text = _clean(" ".join(self._heading_buf))
            if text:
                self.events.append((EVT_HEADING, f"{'#' * (self._current_heading_level + 1)} {text}"))
            self._current_heading_level = None
            self._heading_buf = []
            self._active_buf = None
            return
        if t == "p":
            self._flush_paragraph()
            self._active_buf = None
            return

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        if self._active_buf is not None:
            self._active_buf.append(data)

    def _flush_paragraph(self) -> None:
        text = _clean(" ".join(self._current_paragraph))
        if text and len(text) >= 15:
            self.events.append((EVT_PARAGRAPH, text))
        self._current_paragraph = []

    def title(self) -> str:
        return _clean(" ".join(self.title_parts))

    def body_markdown(self) -> str:
        return "\n\n".join(payload for _, payload in self.events if payload).strip()


class _PdfLinkCollector(HTMLParser):
    """Collect every .pdf link (absolute) inside an AEAT page."""

    def __init__(self, base: str) -> None:
        super().__init__()
        self.base = base
        self.pdfs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = (dict(attrs).get("href") or "").strip()
        if not href.lower().endswith(".pdf"):
            return
        full = _canonicalize_url(href, self.base)
        if full:
            self.pdfs.append(full)


def extract_html(url: str) -> tuple[str, str, list[str]]:
    """Fetch an AEAT HTML page and return (title, markdown_body, pdf_links)."""
    html = fetch_page(url)
    parser = _ContentExtractor()
    parser.feed(html)
    pdf_parser = _PdfLinkCollector(url)
    pdf_parser.feed(html)
    seen: set[str] = set()
    unique_pdfs: list[str] = []
    for p in pdf_parser.pdfs:
        if p not in seen:
            seen.add(p)
            unique_pdfs.append(p)
    return parser.title() or url, parser.body_markdown(), unique_pdfs


# ----------------------------- PDF extraction ----------------------------------

def extract_pdf(url: str) -> tuple[str, str]:
    """Fetch an AEAT PDF and return (title, body_text). Falls back gracefully
    if the file is scanned or `pypdf` is unavailable."""
    title = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1] or url
    if PdfReader is None:
        return title, "(pypdf no disponible para extraer el contenido)"
    raw = fetch_pdf_bytes(url)
    reader = PdfReader(io.BytesIO(raw))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            chunks.append(text.strip())
    body = "\n\n---\n\n".join(chunks).strip()
    if not body or len(body) < PDF_TEXT_THRESHOLD:
        return title, (
            f"PDF sin capa de texto (escaneado o protegido). "
            f"Descargar manualmente para inspección: <{url}>"
        )
    return title, body


# ----------------------------- Slugs and domain routing ------------------------

def _slug_for(url: str) -> str:
    """Deterministic, filesystem-safe slug for a URL.

    Uses a SHA-1 prefix so:
      - collisions across HTML vs. PDF with the same basename are impossible;
      - `refresh --force` produces identical filenames across runs;
      - slugs are short enough to keep `cache/` readable.
    The source URL is always preserved in each `.md`'s `> Source:` header."""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    parsed = urllib.parse.urlparse(url)
    last = Path(parsed.path).name or "page"
    if "." in last:
        last = last.rsplit(".", 1)[0]
    readable = re.sub(r"[^A-Za-z0-9._-]", "-", last).strip("-")[:32] or "page"
    return f"{readable}-{digest}"


def _domain_for(url: str) -> str:
    """Return the cache domain a URL belongs to.

    The three AEAT sections all live under `/Sede/...`, so a naive prefix match
    on `/Sede/` would always classify every URL as the first domain in
    `INDEX_PAGES`. We instead match on the *unique* section basename of each
    index page — e.g. `/Sede/iva.html` ⇒ section `/Sede/iva`. This way
    `/Sede/iva/...` matches `iva` and not `irpf`, and `/Sede/Renta.html`
    (a one-off SEED under IRPF with no nested path) still routes to
    `on-demand` because it does not start with `/Sede/irpf/`."""
    path = urllib.parse.urlparse(url).path
    for domain, index_url in INDEX_PAGES.items():
        index_path = urllib.parse.urlparse(index_url).path
        section = index_path[:-len(".html")] if index_path.endswith(".html") else index_path
        if path == section + ".html" or path == section or path.startswith(section + "/"):
            return domain
    return "on-demand"


# ----------------------------- State file --------------------------------------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"ttl_days": DEFAULT_TTL_DAYS, "domains": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ttl_days": DEFAULT_TTL_DAYS, "domains": {}}


def save_state(state: dict) -> None:
    """Persist `.state.json` atomically (write to .tmp, then replace)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    STATE_TMP.write_text(payload, encoding="utf-8")
    STATE_TMP.replace(STATE_FILE)


def _is_stale(state: dict, domain: str) -> bool:
    info = state.get("domains", {}).get(domain)
    if not info or not info.get("last_refresh"):
        return True
    try:
        last = datetime.fromisoformat(info["last_refresh"])
    except ValueError:
        return True
    ttl_days = state.get("ttl_days", DEFAULT_TTL_DAYS)
    return datetime.now(timezone.utc).astimezone() - last > timedelta(days=ttl_days)


# ----------------------------- File writes -------------------------------------

def write_cache_file(domain: str, slug: str, title: str, source_url: str, body: str) -> Path:
    domain_dir = CACHE_DIR / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    out = domain_dir / f"{slug}.md"
    display_url = _strip_query_fragment(source_url)
    header = (
        f"# {title}\n\n"
        f"> Source: <{display_url}>\n"
        f"> Fetched: {_now_iso()}\n\n"
    )
    out.write_text(header + (body or "_(sin contenido extraído)_") + "\n", encoding="utf-8")
    return out


def _unlink_orphans(prior_pages: list[str], written: set[str]) -> list[str]:
    """Remove stale .md files: prior files in this domain that were NOT rewritten."""
    removed: list[str] = []
    for rel in prior_pages:
        if rel in written:
            continue
        path = SKILL_ROOT / rel
        if path.exists():
            try:
                path.unlink()
                removed.append(rel)
            except OSError:
                pass
    return removed


# ----------------------------- Commands ----------------------------------------

def cmd_status(_args: argparse.Namespace) -> int:
    state = load_state()
    domains = sorted(set(INDEX_PAGES.keys()) | set(state.get("domains", {}).keys()))
    any_stale = False
    print(f"Cache TTL: {state.get('ttl_days', DEFAULT_TTL_DAYS)} days")
    for d in domains:
        info = state.get("domains", {}).get(d, {})
        last = info.get("last_refresh", "(never)")
        status = info.get("last_status", "—")
        pages = len(info.get("pages", []))
        pdf_warns = len(info.get("pdf_warnings", []))
        stale = _is_stale(state, d)
        marker = "STALE" if stale else "ok"
        if stale:
            any_stale = True
        suffix = f"  pdf_warns={pdf_warns}" if pdf_warns else ""
        print(f"  [{marker}] {d:<10} last_refresh={last}  status={status}  pages={pages}{suffix}")
    if any_stale:
        print("\nRun `uv run scripts/fetch_aeat.py refresh` to update stale domains.")
        return 1
    print("\nAll known domains are fresh.")
    return 0


def _do_fetch(
    domain: str,
    urls: list[str],
    *,
    skip_pdfs: bool,
) -> tuple[list[str], list[str]]:
    """Fetch a list of URLs (HTML or PDF). Returns (relative_paths, warnings)."""
    written: list[str] = []
    warnings: list[str] = []
    pdfs_to_fetch: list[str] = []
    for url in urls:
        if _is_pdf_url(url):
            pdfs_to_fetch.append(url)
            continue
        try:
            title, body, pdf_links = extract_html(url)
        except Exception as exc:
            warnings.append(f"HTML fetch failed for {url}: {exc}")
            continue
        slug = _slug_for(url)
        path = write_cache_file(domain, slug, title, url, body)
        written.append(str(path.relative_to(SKILL_ROOT)))
        for p in pdf_links:
            if p not in pdfs_to_fetch:
                pdfs_to_fetch.append(p)

    if not skip_pdfs:
        for pdf_url in pdfs_to_fetch:
            try:
                title, body = extract_pdf(pdf_url)
            except Exception as exc:
                warnings.append(f"PDF fetch failed for {pdf_url}: {exc}")
                continue
            slug = _slug_for(pdf_url)
            path = write_cache_file(domain, slug, title, pdf_url, body)
            written.append(str(path.relative_to(SKILL_ROOT)))
    return written, warnings


def _refresh_all(scopes: list[str], *, skip_pdfs: bool, force: bool, keep_orphans: bool) -> int:
    state = load_state()
    warnings: list[str] = []

    for domain in scopes:
        urls = [INDEX_PAGES[domain], *SEED_SUBPAGES.get(domain, [])]
        if not force and not _is_stale(state, domain):
            print(f"[skip] {domain}: cache fresh ({state['domains'].get(domain, {}).get('last_refresh')})")
            continue

        prior_pages = list(state.get("domains", {}).get(domain, {}).get("pages", []))
        print(f"[refresh] {domain}: {len(urls)} URLs", end="")
        written, w = _do_fetch(domain, urls, skip_pdfs=skip_pdfs)
        warnings.extend(w)

        written_set = set(written)
        any_html_failure = any("HTML fetch failed" in s for s in w)
        any_pdf_failure = any("PDF fetch failed" in s for s in w)
        status = "ok"
        if any_html_failure and not written:
            status = "network-error"
        elif any_html_failure or any_pdf_failure:
            status = "partial"

        if written:
            prior_last = state.get("domains", {}).get(domain, {}).get("last_refresh")
            entry = state.setdefault("domains", {}).setdefault(domain, {})
            entry["last_refresh"] = _now_iso()
            entry["last_status"] = status
            entry["pages"] = written
            if any_pdf_failure:
                entry["pdf_warnings"] = [w for w in w if w.startswith("PDF fetch failed")]
            else:
                entry.pop("pdf_warnings", None)
            print(f" → {len(written)} files (status={status})")
        else:
            # Total failure: don't stamp last_refresh; preserve prior value.
            entry = state.setdefault("domains", {}).setdefault(domain, {})
            entry["last_status"] = status
            print(f" → 0 files (status={status}, preserving previous last_refresh)")

        if not keep_orphans:
            removed = _unlink_orphans(prior_pages, written_set)
            if removed:
                print(f"    unlinked {len(removed)} orphan(s)")

    state["ttl_days"] = state.get("ttl_days", DEFAULT_TTL_DAYS)
    save_state(state)

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
    print("\nDone.")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    scope = args.scope or "all"
    if scope == "all":
        scopes = list(INDEX_PAGES.keys())
    else:
        scopes = [scope]
    for s in scopes:
        if s not in INDEX_PAGES:
            print(f"unknown scope: {s}", file=sys.stderr)
            return 2
    return _refresh_all(
        scopes,
        skip_pdfs=args.skip_pdfs,
        force=args.force,
        keep_orphans=args.keep_orphans,
    )


def cmd_verify(args: argparse.Namespace) -> int:
    """Cross-check `cache/<domain>/*.md` against `.state.json`.

    Two classes of drift are detected:

    * `misfiled` — a file lives under `cache/<X>/` but its `> Source:` URL
      resolves to a different domain `Y`. This is the failure mode the
      `_domain_for` rewrite fixes; `--fix` moves such files to the correct
      directory and rewrites the state.
    * `unregistered` — a file exists on disk but is not listed in the
      domain's `pages` array in `.state.json`. `--fix` registers it.

    Exits 0 if the cache is clean, 1 otherwise (or 2 if `--fix` could not
    resolve all drift)."""
    import shutil  # local import: only needed by `verify --fix`.

    state = load_state()
    state_pages: dict[str, set[str]] = {
        d: set(state.get("domains", {}).get(d, {}).get("pages", []))
        for d in INDEX_PAGES
    }
    on_demand_pages: set[str] = set(state.get("domains", {}).get("on-demand", {}).get("pages", []))

    misfiled: list[tuple[Path, str, str]] = []   # (path, actual_dir_domain, expected_domain)
    unregistered: list[tuple[Path, str]] = []    # (path, expected_domain)

    for domain in INDEX_PAGES:
        dom_dir = CACHE_DIR / domain
        if not dom_dir.is_dir():
            continue
        for md in sorted(dom_dir.glob("*.md")):
            rel = str(md.relative_to(SKILL_ROOT))
            source_url = _read_source_url(md)
            if source_url is None:
                print(f"[warn] {rel}: no `> Source:` header; skipping", file=sys.stderr)
                continue
            expected = _domain_for(source_url)
            registered_domains = []
            for d, pages in state_pages.items():
                if rel in pages:
                    registered_domains.append(d)
            # Misfiled = file sits under a domain dir but its source URL
            # belongs to a *different* domain — including `on-demand` (an
            # index-domain file whose URL doesn't match any section is
            # genuinely on-demand and shouldn't be living in `cache/irpf/`).
            if expected != domain:
                misfiled.append((md, domain, expected))
            if not registered_domains:
                unregistered.append((md, expected))

    on_demand_dir = CACHE_DIR / "on-demand"
    if on_demand_dir.is_dir():
        for md in sorted(on_demand_dir.glob("*.md")):
            rel = str(md.relative_to(SKILL_ROOT))
            if rel not in on_demand_pages:
                source_url = _read_source_url(md)
                expected = _domain_for(source_url) if source_url else "on-demand"
                unregistered.append((md, expected))

    if misfiled:
        for path, actual, expected in misfiled:
            print(f"[misfiled] {path.relative_to(SKILL_ROOT)} → expected domain '{expected}' (currently in '{actual}')")
    if unregistered:
        for path, expected in unregistered:
            print(f"[unregistered] {path.relative_to(SKILL_ROOT)} (expected domain '{expected}')")

    if not misfiled and not unregistered:
        print("ok: cache directories are consistent with .state.json.")
        return 0

    if not args.fix:
        print("\nRun with --fix to move misfiled files and register unregistered ones.", file=sys.stderr)
        return 1

    # --fix: relocate and re-register.
    changed = False
    for path, _actual, expected in misfiled:
        target_dir = CACHE_DIR / expected
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            print(f"[skip] {path.name}: already exists in {expected}/", file=sys.stderr)
            continue
        shutil.move(str(path), str(target))
        rel_new = str(target.relative_to(SKILL_ROOT))
        rel_old = str(path.relative_to(SKILL_ROOT))
        for d, pages in state_pages.items():
            if rel_old in pages:
                pages.discard(rel_old)
        if expected == "on-demand":
            on_demand_pages.add(rel_new)
        else:
            state_pages.setdefault(expected, set()).add(rel_new)
        print(f"[moved] {rel_old} → {rel_new}")
        changed = True

    for path, expected in unregistered:
        rel = str(path.relative_to(SKILL_ROOT))
        if expected == "on-demand":
            if rel not in on_demand_pages:
                on_demand_pages.add(rel)
                print(f"[registered] {rel} → on-demand")
                changed = True
        else:
            state_pages.setdefault(expected, set()).add(rel)
            print(f"[registered] {rel} → {expected}")
            changed = True

    if changed:
        for d in INDEX_PAGES:
            entry = state.setdefault("domains", {}).setdefault(d, {})
            entry["pages"] = sorted(state_pages.get(d, set()))
        state.setdefault("domains", {})["on-demand"] = {
            "pages": sorted(on_demand_pages),
            "last_refresh": _now_iso(),
            "last_status": "ok",
        }
        save_state(state)
        print("\nState updated.")
    return 0


def _read_source_url(md_path: Path) -> str | None:
    """Extract the `> Source: <url>` line from a cached `.md`. Returns None if absent.

    Header layout is `# Title`, blank, `> Source: …`, `> Fetched: …`, blank, body.
    We keep scanning past non-`>` lines (e.g. the title) until we either find the
    source line or hit a blank followed by body content."""
    try:
        with md_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("> Source:"):
                    return stripped[len("> Source:"):].strip()
    except OSError:
        return None
    return None


def cmd_url(args: argparse.Namespace) -> int:
    url = args.url
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in ALLOWED_NETLOCS:
        print(f"refusing to fetch non-AEAT URL: {parsed.netloc}", file=sys.stderr)
        return 2
    if parsed.scheme != "https":
        print(f"refusing non-HTTPS URL: {parsed.scheme}://...", file=sys.stderr)
        return 2
    if parsed.query or parsed.fragment:
        print(
            f"warning: query/fragment stripped from cache header "
            f"(stored URL: {_strip_query_fragment(url)})",
            file=sys.stderr,
        )

    state = load_state()
    domain = _domain_for(url)
    try:
        if _is_pdf_url(url):
            if args.skip_pdfs:
                print("--skip-pdfs set; ignoring PDF", file=sys.stderr)
                return 2
            title, body = extract_pdf(url)
            slug = _slug_for(url)
            path = write_cache_file(domain, slug, title, url, body)
        else:
            title, body, pdfs = extract_html(url)
            slug = _slug_for(url)
            path = write_cache_file(domain, slug, title, url, body)
            for p in pdfs:
                try:
                    pt, pb = extract_pdf(p)
                    pslug = _slug_for(p)
                    write_cache_file(domain, pslug, pt, p, pb)
                except Exception as exc:
                    print(f"warning: PDF fetch failed for {p}: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1
    rel = str(path.relative_to(SKILL_ROOT))
    state.setdefault("domains", {}).setdefault(domain, {})
    pages = state["domains"][domain].setdefault("pages", [])
    if rel not in pages:
        pages.append(rel)
    state["domains"][domain]["last_refresh"] = _now_iso()
    state["domains"][domain]["last_status"] = "ok"
    save_state(state)
    print(f"wrote {rel}")
    return 0


# ----------------------------- Main ---------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="aeat-knowledge-base cache helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Print per-domain cache age; exit 1 if any stale.")

    refresh_p = sub.add_parser("refresh", help="Refresh stale (or all, with --force) domains.")
    refresh_p.add_argument("--scope", choices=list(INDEX_PAGES.keys()) + ["all"], help="Limit refresh to one domain.")
    refresh_p.add_argument("--skip-pdfs", action="store_true", help="Do not download linked PDFs.")
    refresh_p.add_argument("--force", action="store_true", help="Refetch every URL, ignoring TTL.")
    refresh_p.add_argument("--keep-orphans", action="store_true",
                           help="Do not remove old .md files whose source URL no longer writes.")

    url_p = sub.add_parser("url", help="Fetch a single AEAT URL and add it to the cache.")
    url_p.add_argument("url", help="Absolute HTTPS URL on sede.agenciatributaria.gob.es")
    url_p.add_argument("--skip-pdfs", action="store_true", help="Do not download linked PDFs.")

    verify_p = sub.add_parser(
        "verify",
        help="Cross-check cache/<domain>/ against .state.json; --fix corrects drift.",
    )
    verify_p.add_argument(
        "--fix", action="store_true",
        help="Move misfiled files to the correct domain dir and register unregistered ones.",
    )

    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "refresh":
        return cmd_refresh(args)
    if args.cmd == "url":
        return cmd_url(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
