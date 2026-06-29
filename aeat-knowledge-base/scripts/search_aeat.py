#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["fastembed", "numpy"]
# ///
"""
Semantic search helper for the `aeat-knowledge-base` skill.

Embeds every chunk of every cached page (`cache/<domain>/*.md`) with
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
(multilingual incl. Spanish, ONNX-backed, MIT, 220 MB) and stores:

    cache/.embeddings.npy     # float32 (num_chunks, dim)
    cache/.chunks.jsonl       # one JSON per line: id, text, source_url,
                              #   domain, slug, title, heading_path, fetched_at
    cache/.search_meta.json   # model, built_at, dim, counts

The index is opt-in: build it once via `build`, then `search` runs
entirely offline. Re-run `build` after `fetch_aeat.py refresh` / `url`
to pick up new pages (the `fetch_aeat.py` `index` subcommand does this
automatically — see `scripts/fetch_aeat.py index`).

Commands:

    uv run scripts/search_aeat.py build  [--force] [--scope X|all]
    uv run scripts/search_aeat.py info
    uv run scripts/search_aeat.py search "<query>" [--domain X] [--k 5] [--json]
    uv run scripts/search_aeat.py stats

Chunking:

    Each `.md` is split on its headings (H1-H6). Sections longer than
    `CHUNK_WORDS` are window-split into overlapping chunks
    (`CHUNK_OVERLAP_WORDS`). Every chunk carries the original `> Source:`
    URL, domain, fetched_at and a cumulative heading path so answers can
    be cited verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Default search mode. BM25 (stdlib-only, ~0.2 s cold) is the right default
# for the agent workflow because every `uv run scripts/search_aeat.py
# search …` adds a fixed ~1.7 s of Python startup + `fastembed` import
# when the semantic path is used. Pass `--mode semantic` (or `--mode
# hybrid`) for queries where paraphrasing beats literal token overlap.
DEFAULT_MODE = "bm25"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_WORDS = 220
CHUNK_OVERLAP_WORDS = 30
TOPK_DEFAULT = 5

SKILL_ROOT: Path = Path(__file__).resolve().parent.parent
CACHE_DIR: Path = SKILL_ROOT / "cache"
EMBEDDINGS_PATH: Path = CACHE_DIR / ".embeddings.npy"
CHUNKS_PATH: Path = CACHE_DIR / ".chunks.jsonl"
META_PATH: Path = CACHE_DIR / ".search_meta.json"


@dataclass
class Chunk:
    id: str
    text: str
    source_url: str
    domain: str
    slug: str
    title: str
    heading_path: str
    fetched_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


# ----------------------------- Cache parsing -----------------------------------

def _read_header_field(path: Path, field: str) -> str | None:
    """Find a `> Field: value` line in a cached `.md`.

    `fetch_aeat.write_cache_file` wraps URLs in `<…>`; strip them so the
    stored value is the bare URL the citation needs."""
    prefix = f"> {field}:"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(prefix):
                value = s[len(prefix):].strip()
                if len(value) >= 2 and value.startswith("<") and value.endswith(">"):
                    value = value[1:-1]
                return value
    except OSError:
        return None
    return None


# Suppress the "mean pooling instead of CLS embedding" advisory emitted by
# fastembed >= 0.6 for `paraphrase-multilingual-MiniLM-L12-v2`. Behaviour is
# unchanged (and arguably better with mean pooling); the message is noisy.
# fastembed occasionally re-installs its own filters on TextEmbedding()
# instantiation, so we re-apply this filter inside `build_index` and
# `search` to keep the CLI output clean.
warnings.filterwarnings(
    "ignore",
    message=r".*mean pooling instead of CLS embedding.*",
)


def _silence_mean_pool_warning() -> None:
    """Re-apply the filter after `fastembed` has reset it."""
    warnings.filterwarnings(
        "ignore",
        message=r".*mean pooling instead of CLS embedding.*",
    )

# ----------------------------- Cache parsing -----------------------------------

def _extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _strip_header_block(text: str) -> str:
    """Drop the H1 title and the `> Source:` / `> Fetched:` block, returning the body."""
    lines = text.splitlines()
    out: list[str] = []
    skipped_title = False
    for line in lines:
        if not skipped_title and line.startswith("# "):
            skipped_title = True
            continue
        if line.strip().startswith("> Source:") or line.strip().startswith("> Fetched:"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def _split_markdown(body: str) -> list[tuple[str, str]]:
    """Return list of (heading_path, section_text) tuples.

    heading_path is cumulative, e.g. "## A > ### A.1".
    """
    sections: list[tuple[str, str]] = []
    current_path: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append((
                " > ".join(current_path) if current_path else "",
                text,
            ))
        buf.clear()

    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            level = len(m.group(1))
            heading = m.group(2).strip()
            current_path = current_path[: max(0, level - 1)] + [f"{m.group(1)} {heading}"]
            continue
        buf.append(line)
    flush()
    return sections


def _split_long_section(
    text: str,
    max_words: int = CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Window-split a long section into overlapping word-bounded chunks."""
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks: list[str] = []
    step = max(1, max_words - overlap_words)
    for start in range(0, len(words), step):
        window = words[start : start + max_words]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + max_words >= len(words):
            break
    return chunks


def build_chunks(cache_dir: Path) -> list[Chunk]:
    """Walk cache_dir, parse every .md, return a flat list of Chunk."""
    chunks: list[Chunk] = []
    for domain_dir in sorted(p for p in cache_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for md_path in sorted(domain_dir.glob("*.md")):
            source_url = _read_header_field(md_path, "Source")
            if not source_url:
                continue
            fetched_at = _read_header_field(md_path, "Fetched") or ""
            text = md_path.read_text(encoding="utf-8")
            title = _extract_title(text) or md_path.stem
            body = _strip_header_block(text)
            for heading_path, section_text in _split_markdown(body):
                for idx, piece in enumerate(_split_long_section(section_text)):
                    if not piece.strip():
                        continue
                    cid_src = f"{md_path.name}|{heading_path}|{idx}"
                    cid = hashlib.sha1(cid_src.encode("utf-8")).hexdigest()[:16]
                    chunks.append(Chunk(
                        id=cid,
                        text=piece.strip(),
                        source_url=source_url,
                        domain=domain_dir.name,
                        slug=md_path.stem,
                        title=title,
                        heading_path=heading_path,
                        fetched_at=fetched_at,
                    ))
    return chunks


# ----------------------------- Index build -------------------------------------

def build_index(force: bool = False, scope: str = "all", verbose: bool = True) -> int:
    if not CACHE_DIR.is_dir():
        print(f"cache directory not found: {CACHE_DIR}", file=sys.stderr)
        return 1
    existing = EMBEDDINGS_PATH.exists() and CHUNKS_PATH.exists() and META_PATH.exists()
    if existing and not force:
        print("Index already exists. Pass --force to rebuild.")
        return 0

    chunks = build_chunks(CACHE_DIR)
    if scope != "all":
        chunks = [c for c in chunks if c.domain == scope]
    if not chunks:
        print("No chunks to embed. Run `uv run scripts/fetch_aeat.py refresh` first.")
        return 1

    if verbose:
        print(f"Embedding {len(chunks)} chunks with {EMBED_MODEL} …")

    from fastembed import TextEmbedding  # imported lazily: keeps cold import cheap

    # fastembed re-installs warning filters when TextEmbedding is constructed;
    # re-silence BEFORE the warning can fire.
    _silence_mean_pool_warning()
    embedder = TextEmbedding(model_name=EMBED_MODEL)
    _silence_mean_pool_warning()
    t0 = time.time()
    vecs = list(embedder.embed([c.text for c in chunks], batch_size=32, parallel=0))
    arr = np.asarray(vecs, dtype=np.float32)
    elapsed = time.time() - t0
    if verbose:
        print(f"  done in {elapsed:.1f}s, shape={arr.shape}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_PATH, arr)
    with CHUNKS_PATH.open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(c.to_json() + "\n")
    META_PATH.write_text(
        json.dumps({
            "model": EMBED_MODEL,
            "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "num_chunks": len(chunks),
            "dim": int(arr.shape[1]),
            "domains": sorted({c.domain for c in chunks}),
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if verbose:
        print(f"Wrote {EMBEDDINGS_PATH.name} and {CHUNKS_PATH.name} ({len(chunks)} chunks).")
    return 0


# ----------------------------- Index load --------------------------------------

def load_chunks() -> list[Chunk]:
    """Load the persisted chunk metadata. Works regardless of whether the
    embedding matrix exists (cheap, stdlib-only — used by both modes)."""
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError("no chunks; run `build` first (or rebuild via `refresh`)")
    chunks: list[Chunk] = []
    with CHUNKS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(Chunk(**json.loads(line)))
    return chunks


def load_index() -> tuple[np.ndarray, list[Chunk], dict]:
    if not (EMBEDDINGS_PATH.exists() and META_PATH.exists()):
        raise FileNotFoundError("no embedding index; run `build` first")
    arr = np.load(EMBEDDINGS_PATH)
    chunks = load_chunks()
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    return arr, chunks, meta


# ----------------------------- BM25 fallback -----------------------------------
# Pure-stdlib BM25 so that `search` returns useful results without ever loading
# the embedding model. Good enough for the small, focused AEAT cache and ~30x
# faster on cold start (no `fastembed` import, ~100 ms vs ~2 s).

_BM25_K1 = 1.5
_BM25_B = 0.75
_BM25_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def bm25_tokenize(text: str) -> list[str]:
    """Lowercase, strip accents, tokenize on word boundaries."""
    return _BM25_TOKEN_RE.findall(_strip_accents(text.lower()))


def bm25_search(
    query: str,
    chunks: list[Chunk],
    *,
    domain: str | None = None,
    k: int = TOPK_DEFAULT,
) -> list[tuple[Chunk, float]]:
    if not chunks:
        return []
    query_tokens = bm25_tokenize(query)
    if not query_tokens:
        return []

    doc_tokens = [bm25_tokenize(c.text) for c in chunks]
    N = len(doc_tokens)
    avgdl = sum(len(d) for d in doc_tokens) / N

    # Document frequencies over all chunks (cheap: 185 docs × ~few hundred tokens).
    df: dict[str, int] = {}
    for doc in doc_tokens:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1

    scores: list[float] = [-math.inf] * N
    for i, doc in enumerate(doc_tokens):
        if domain and chunks[i].domain != domain:
            continue
        if not doc:
            continue
        dl = len(doc)
        tf: dict[str, int] = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for qt in query_tokens:
            f = tf.get(qt, 0)
            if f == 0:
                continue
            n = df.get(qt, 0)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1.0)
            denom = f + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / avgdl)
            s += idf * f * (_BM25_K1 + 1.0) / denom
        scores[i] = s

    topk_idx = sorted(range(N), key=lambda i: -scores[i])[:k]
    out: list[tuple[Chunk, float]] = []
    for i in topk_idx:
        if scores[i] == -math.inf or scores[i] <= 0:
            continue
        out.append((chunks[i], scores[i]))
    return out


def _semantic_search(
    query: str,
    chunks: list[Chunk],
    *,
    domain: str | None = None,
    k: int = TOPK_DEFAULT,
) -> list[tuple[Chunk, float]]:
    from fastembed import TextEmbedding

    arr, _, meta = load_index()
    _silence_mean_pool_warning()
    embedder = TextEmbedding(model_name=meta["model"])
    _silence_mean_pool_warning()
    q_vec = np.asarray(list(embedder.embed([query]))[0], dtype=np.float32)

    a_norm = np.linalg.norm(arr, axis=1, keepdims=True)
    safe_a = np.where(a_norm > 0, a_norm, 1.0)
    arr_n = arr / safe_a
    q_n = q_vec / (np.linalg.norm(q_vec) or 1.0)
    sims = (arr_n @ q_n)
    if domain:
        mask = np.array([c.domain == domain for c in chunks], dtype=bool)
        sims = np.where(mask, sims, -np.inf)
    topk = np.argsort(-sims)[:k]
    out: list[tuple[Chunk, float]] = []
    for idx in topk:
        s = float(sims[int(idx)])
        if not math.isfinite(s) or s == -math.inf:
            continue
        out.append((chunks[int(idx)], s))
    return out


# ----------------------------- Search dispatcher --------------------------------

def search(
    query: str,
    *,
    domain: str | None = None,
    k: int = TOPK_DEFAULT,
    mode: str = DEFAULT_MODE,
) -> list[tuple[Chunk, float]]:
    """Run a search and return `(chunk, score)` pairs sorted by score desc.

    `mode`:
      - "auto"     — semantic if an index exists on disk, otherwise BM25
      - "bm25"     — pure-Python BM25 (chunks are parsed from `cache/*.md`
                     on demand; falls back to the persisted `.chunks.jsonl`
                     when one exists)
      - "semantic" — sentence-transformers cosine; raises FileNotFoundError
                     if no embedding index exists
      - "hybrid"   — runs both and re-ranks by reciprocal-rank fusion
    """
    if mode == "auto":
        mode = "semantic" if EMBEDDINGS_PATH.exists() else "bm25"

    if mode == "bm25":
        chunks = _chunks_for_search()
        return bm25_search(query, chunks, domain=domain, k=k)
    if mode == "semantic":
        chunks = _chunks_for_search()
        return _semantic_search(query, chunks, domain=domain, k=k)
    if mode == "hybrid":
        chunks = _chunks_for_search()
        sem = _semantic_search(query, chunks, domain=domain, k=max(k, 10))
        bm = bm25_search(query, chunks, domain=domain, k=max(k, 10))
        # Reciprocal-rank fusion.
        seen: dict[str, float] = {}
        by_chunk: dict[str, Chunk] = {}
        for r, (chunk, _) in enumerate(sem):
            by_chunk[chunk.id] = chunk
            seen[chunk.id] = seen.get(chunk.id, 0.0) + 1.0 / (r + 60.0)
        for r, (chunk, _) in enumerate(bm):
            by_chunk[chunk.id] = chunk
            seen[chunk.id] = seen.get(chunk.id, 0.0) + 1.0 / (r + 60.0)
        ordered = sorted(seen.items(), key=lambda kv: -kv[1])
        return [(by_chunk[cid], s) for cid, s in ordered[:k]]
    raise ValueError(f"unknown mode: {mode!r}")


def _chunks_for_search() -> list[Chunk]:
    """Prefer the persisted chunks (one .jsonl parse, no .md walk). Fall back
    to building from the live cache so BM25 works on a fresh install too."""
    if CHUNKS_PATH.exists():
        return load_chunks()
    if CACHE_DIR.is_dir():
        return build_chunks(CACHE_DIR)
    raise FileNotFoundError("no cache found; run `fetch_aeat.py refresh` first")


# ----------------------------- Commands ----------------------------------------

def cmd_build(args: argparse.Namespace) -> int:
    return build_index(force=args.force, scope=args.scope)


def cmd_info(_args: argparse.Namespace) -> int:
    if not META_PATH.exists():
        print("No index. Run `build` first.")
        return 1
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    print(json.dumps(meta, indent=2, sort_keys=True))
    return 0


def cmd_stats(_args: argparse.Namespace) -> int:
    if not META_PATH.exists():
        print("No index. Run `build` first.")
        return 1
    arr, chunks, meta = load_index()
    by_domain: dict[str, int] = {}
    for c in chunks:
        by_domain[c.domain] = by_domain.get(c.domain, 0) + 1
    print(f"Model:      {meta['model']}")
    print(f"Built at:   {meta['built_at']}")
    print(f"Chunks:     {len(chunks)}")
    print(f"Dim:        {meta['dim']}")
    print(f"Matrix:     {arr.shape} {arr.dtype}")
    print(f"By domain:  {', '.join(f'{d}={n}' for d, n in sorted(by_domain.items()))}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    try:
        results = search(args.query, domain=args.domain, k=args.k, mode=args.mode)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not results:
        print("(no matches)")
        return 0
    effective = args.mode if args.mode != "auto" else ("semantic" if EMBEDDINGS_PATH.exists() else "bm25")
    if args.json:
        payload = [
            {
                "score": round(score, 4),
                "domain": chunk.domain,
                "source_url": chunk.source_url,
                "slug": chunk.slug,
                "title": chunk.title,
                "heading_path": chunk.heading_path,
                "text": chunk.text,
            }
            for chunk, score in results
        ]
        print(json.dumps({"mode": effective, "results": payload}, ensure_ascii=False, indent=2))
        return 0
    print(f"[mode={effective}, k={len(results)}]")
    for chunk, score in results:
        print(f"[{score:.3f}] {chunk.domain}/{chunk.slug}")
        print(f"  title:  {chunk.title}")
        print(f"  source: {chunk.source_url}")
        print(f"  path:   {chunk.heading_path or '(lead)'}")
        # Print the whole chunk (≤CHUNK_WORDS ≈ 220 ≈ ~1400 chars). The chunk
        # is already the unit we indexed, so the agent gets the citation-ready
        # text in one shot and does not need a follow-up read_file.
        print(f"  text:")
        for line in chunk.text.splitlines() or [chunk.text]:
            print(f"    {line}")
        print()
    return 0


# ----------------------------- Main -------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Semantic search over the aeat cache.")
    sub = p.add_subparsers(dest="cmd", required=True)

    bp = sub.add_parser("build", help="Embed every cache chunk and persist the index.")
    bp.add_argument("--force", action="store_true", help="Rebuild even if index exists.")
    bp.add_argument("--scope", default="all", help="Limit to a single cache domain (irpf|iva|vivienda|on-demand|all).")

    sub.add_parser("info", help="Print index metadata as JSON (model, built_at, num_chunks, dim, domains).")
    sub.add_parser("stats", help="Print one-line-per-field stats: model, chunk counts by domain.")

    sp = sub.add_parser("search", help="Run a query against the chunk index.")
    sp.add_argument("query", help="Question or phrase to match.")
    sp.add_argument("--domain", help="Restrict results to one cache domain.")
    sp.add_argument("--k", type=int, default=TOPK_DEFAULT, help="Number of chunks to return (default 5).")
    sp.add_argument(
        "--mode",
        choices=["auto", "bm25", "semantic", "hybrid"],
        default=DEFAULT_MODE,
        help=(
            "auto=semantic if an embedding index exists on disk, else BM25. "
            "BM25 is stdlib-only and ~30x faster on cold start; "
            "semantic requires `build`. hybrid re-ranks both."
        ),
    )
    sp.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text.")

    args = p.parse_args()
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "info":
        return cmd_info(args)
    if args.cmd == "stats":
        return cmd_stats(args)
    if args.cmd == "search":
        return cmd_search(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
