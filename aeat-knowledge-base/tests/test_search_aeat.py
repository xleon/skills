#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "fastembed"]
# ///
"""Unit tests for `scripts/search_aeat.py`.

The tests build an isolated mini-cache under a temporary directory, embed it
with the real `fastembed` model, and assert that canonical queries surface
chunks from the expected domain.

First run downloads `paraphrase-multilingual-MiniLM-L12-v2` (~220 MB) into
`~/.cache/fastembed/`. Subsequent runs are fully offline.

Run with:

    uv run tests/test_search_aeat.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import search_aeat as sa  # type: ignore[import-not-found]  # noqa: E402


FIXTURES = {
    "irpf": [
        {
            "slug": "declaracion-renta",
            "title": "Mínimos personales y familiares en el IRPF",
            "source": "https://sede.agenciatributaria.gob.es/Sede/Renta.html",
            "body": (
                "El IRPF grava la renta de las personas físicas residentes en España.\n\n"
                "## Mínimos personales y familiares\n\n"
                "El mínimo personal es de 5550 euros, incrementado por descendientes o ascendientes y por discapacidad.\n\n"
                "## Reducciones por aportaciones\n\n"
                "Las aportaciones a planes de pensiones y los rendimientos del trabajo con reducción por movilidad geográfica minoran la base imponible del ahorro."
            ),
        },
    ],
    "iva": [
        {
            "slug": "modelo-303-plazos",
            "title": "Plazos de presentación del modelo 303",
            "source": "https://sede.agenciatributaria.gob.es/Sede/iva/modelo-303.html",
            "body": (
                "El modelo 303 es la autoliquidación trimestral del IVA.\n\n"
                "## Plazo de presentación\n\n"
                "Se presenta entre los días 1 y 20 del mes siguiente al trimestre natural.\n\n"
                "## IVA repercutido y soportado\n\n"
                "La cuota a ingresar es el IVA repercutido en las entregas de bienes y prestaciones de servicios menos el IVA soportado en las adquisiciones deducibles."
            ),
        },
        {
            "slug": "verifactu",
            "title": "Sistemas Informáticos de Facturación (SIF) y VeriFactu",
            "source": "https://sede.agenciatributaria.gob.es/Sede/iva/verifactu.html",
            "body": (
                "VeriFactu es el sistema de la AEAT para remitir facturas electrónicas en tiempo real.\n\n"
                "## Requisitos técnicos\n\n"
                "Los sistemas deben garantizar la integridad, trazabilidad, conservación y no manipulación de los registros de facturación."
            ),
        },
    ],
    "vivienda": [
        {
            "slug": "imputacion-rentas",
            "title": "Valor catastral e imputación de rentas por inmuebles urbanos",
            "source": "https://sede.agenciatributaria.gob.es/Sede/vivienda/imputacion-rentas.html",
            "body": (
                "Los titulares de bienes inmuebles urbanos no arrendados tributan en el IRPF por imputación de rentas inmobiliarias.\n\n"
                "## Cálculo por valor catastral\n\n"
                "El rendimiento se obtiene aplicando un porcentaje (el 1,1 por ciento en general) sobre el valor catastral del inmueble revisado.\n\n"
                "## Inmuebles rústicos y arrendados\n\n"
                "Para fincas rústicas el porcentaje es del 0,5 por ciento y para inmuebles arrendados la imputación se sustituye por el rendimiento del capital inmobiliario declarado."
            ),
        },
    ],
}


def _write_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for domain, pages in FIXTURES.items():
        dom_dir = cache_dir / domain
        dom_dir.mkdir(parents=True, exist_ok=True)
        for page in pages:
            md_path = dom_dir / f"{page['slug']}.md"
            md_path.write_text(
                f"# {page['title']}\n\n"
                f"> Source: <{page['source']}>\n"
                "> Fetched: 2026-06-29T22:30:00+02:00\n\n"
                f"{page['body']}\n",
                encoding="utf-8",
            )


def _build_index_in(cache_dir: Path) -> None:
    """Run `build_index` against the given cache directory by monkey-patching the module constants."""
    real_cache = sa.CACHE_DIR
    sa.CACHE_DIR = cache_dir
    sa.EMBEDDINGS_PATH = cache_dir / ".embeddings.npy"
    sa.CHUNKS_PATH = cache_dir / ".chunks.jsonl"
    sa.META_PATH = cache_dir / ".search_meta.json"
    try:
        rc = sa.build_index(force=True, scope="all", verbose=False)
        if rc != 0:
            raise RuntimeError(f"build_index exited {rc}")
    finally:
        sa.CACHE_DIR = real_cache
        sa.EMBEDDINGS_PATH = real_cache / ".embeddings.npy"
        sa.CHUNKS_PATH = real_cache / ".chunks.jsonl"
        sa.META_PATH = real_cache / ".search_meta.json"


def _search_in(cache_dir: Path, query: str, *, k: int = 3, domain: str | None = None):
    real_cache = sa.CACHE_DIR
    sa.CACHE_DIR = cache_dir
    sa.EMBEDDINGS_PATH = cache_dir / ".embeddings.npy"
    sa.CHUNKS_PATH = cache_dir / ".chunks.jsonl"
    sa.META_PATH = cache_dir / ".search_meta.json"
    try:
        return sa.search(query, k=k, domain=domain)
    finally:
        sa.CACHE_DIR = real_cache
        sa.EMBEDDINGS_PATH = real_cache / ".embeddings.npy"
        sa.CHUNKS_PATH = real_cache / ".chunks.jsonl"
        sa.META_PATH = real_cache / ".search_meta.json"


class TestChunker(unittest.TestCase):
    """Pure-logic tests for the heading-bounded chunker — no embeddings involved."""

    def test_split_markdown_tracks_heading_hierarchy(self) -> None:
        body = (
            "# top\n\n"
            "intro\n\n"
            "## A\n\n"
            "para a\n\n"
            "### A.1\n\n"
            "para a.1\n\n"
            "## B\n\n"
            "para b"
        )
        out = sa._split_markdown(body)
        # 3 flushes: under #top, under ##A, under ###A.1. para b is the tail
        # under ##B (no closing flush needed, end-of-input flushes it).
        self.assertEqual(len(out), 4)
        # Lead para carries the first heading as its path.
        self.assertTrue(out[0][0].startswith("# top"))
        self.assertEqual(out[0][1], "intro")
        self.assertTrue(out[1][0].startswith("# top > ## A"))
        self.assertTrue(out[2][0].startswith("# top > ## A > ### A.1"))
        self.assertTrue(out[3][0].startswith("# top > ## B"))
        # B resets A.1 — no inheritance from deeper sections.
        self.assertNotIn("A.1", out[3][0])

    def test_split_long_section_windows_with_overlap(self) -> None:
        text = " ".join(f"palabra{i}" for i in range(1000))
        chunks = sa._split_long_section(text, max_words=200, overlap_words=40)
        # Roughly (1000 - 40) / (200 - 40) ≈ 6 windows.
        self.assertGreaterEqual(len(chunks), 5)
        self.assertLessEqual(len(chunks), 9)
        # Every window is at most `max_words` long.
        for c in chunks:
            self.assertLessEqual(len(c.split()), 200)

    def test_short_section_returns_one_chunk(self) -> None:
        text = "pocas palabras aquí"
        self.assertEqual(sa._split_long_section(text), [text])


class TestBuildChunks(unittest.TestCase):
    """Verify `build_chunks` parses a fixture cache, carries headings, and assigns stable IDs."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aeat_search_test_"))
        _write_cache(self.tmp)
        # `build_chunks` reads the module-level CACHE_DIR; patch it for the duration.
        self._real = sa.CACHE_DIR
        sa.CACHE_DIR = self.tmp
        self.addCleanup(self._restore)
        self.chunks = sa.build_chunks(self.tmp)

    def _restore(self) -> None:
        sa.CACHE_DIR = self._real
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_collects_one_chunk_per_heading_section(self) -> None:
        domains = {c.domain for c in self.chunks}
        self.assertEqual(domains, {"irpf", "iva", "vivienda"})

    def test_chunks_carry_source_url_and_title(self) -> None:
        # Source URL is mandatory on every chunk; heading_path may be empty
        # for intro chunks that sit before the first H2; title is mandatory.
        for c in self.chunks:
            self.assertTrue(c.source_url.startswith("https://sede.agenciatributaria.gob.es/"))
            self.assertTrue(c.title)
            self.assertTrue(c.text)
            self.assertIn(c.domain, {"irpf", "iva", "vivienda"})

    def test_chunk_ids_are_stable(self) -> None:
        again = sa.build_chunks(self.tmp)
        self.assertEqual(
            [c.id for c in self.chunks],
            [c.id for c in again],
        )


class TestSearchEndToEnd(unittest.TestCase):
    """End-to-end test: build an index from fixtures and assert semantic recall.

    Skipped automatically if `fastembed` is not importable in the test venv
    (e.g. when `uv run` was invoked without the optional deps)."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import fastembed  # noqa: F401
        except Exception:
            raise unittest.SkipTest("fastembed not installed; skipping end-to-end search test")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aeat_search_e2e_"))
        _write_cache(self.tmp)
        _build_index_in(self.tmp)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _top_domain(self, query: str, *, domain: str | None = None) -> tuple[str, float]:
        hits = _search_in(self.tmp, query, k=1, domain=domain)
        self.assertTrue(hits, f"no results for {query!r}")
        chunk, score = hits[0]
        return chunk.domain, score

    def test_plazo_modelo_303_routes_to_iva(self) -> None:
        domain, _ = self._top_domain("plazo presentación modelo 303 autoliquidación trimestral")
        self.assertEqual(domain, "iva")

    def test_verifactu_sif_routes_to_iva(self) -> None:
        domain, _ = self._top_domain("Verifactu SIF facturación electrónica integridad")
        self.assertEqual(domain, "iva")

    def test_declaracion_renta_minimos_routes_to_irpf(self) -> None:
        domain, _ = self._top_domain("mínimos personales descendientes planes de pensiones")
        self.assertEqual(domain, "irpf")

    def test_imputacion_rentas_inmobiliarias_routes_to_vivienda(self) -> None:
        domain, _ = self._top_domain("valor catastral inmueble urbano imputación rústico")
        self.assertEqual(domain, "vivienda")

    def test_domain_filter_is_honoured(self) -> None:
        hits = _search_in(self.tmp, "trimestral IVA", k=3, domain="iva")
        # Filtering to iva must return only iva results.
        self.assertTrue(hits)
        for chunk, _score in hits:
            self.assertEqual(chunk.domain, "iva")


class TestMetaArtifacts(unittest.TestCase):
    """Verify the .npy / .jsonl / .search_meta.json layout matches what the docs promise."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aeat_search_meta_"))
        _write_cache(self.tmp)
        try:
            import fastembed  # noqa: F401
        except Exception:
            self.skipTest("fastembed not installed; skipping meta artifacts test")
        _build_index_in(self.tmp)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_artifact_files_exist(self) -> None:
        self.assertTrue((self.tmp / ".embeddings.npy").is_file())
        self.assertTrue((self.tmp / ".chunks.jsonl").is_file())
        self.assertTrue((self.tmp / ".search_meta.json").is_file())

    def test_chunk_metadata_round_trips(self) -> None:
        with (self.tmp / ".chunks.jsonl").open(encoding="utf-8") as fh:
            records = [json.loads(line) for line in fh if line.strip()]
        self.assertGreater(len(records), 0)
        for rec in records:
            for key in ("id", "text", "source_url", "domain", "slug", "title", "heading_path", "fetched_at"):
                self.assertIn(key, rec)
            self.assertIn(rec["domain"], {"irpf", "iva", "vivienda"})

    def test_meta_documents_model_and_dim(self) -> None:
        meta = json.loads((self.tmp / ".search_meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["model"], sa.EMBED_MODEL)
        self.assertEqual(meta["dim"], 384)
        self.assertGreater(meta["num_chunks"], 0)


if __name__ == "__main__":
    unittest.main()
