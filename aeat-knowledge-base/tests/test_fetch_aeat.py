"""Unit tests for `scripts/fetch_aeat.py`.

These tests cover pure helpers that do not require network access. Run with:

    uv run --with pypdf --with cryptography python tests/test_fetch_aeat.py

or, equivalently, from the skill root:

    uv run tests/test_fetch_aeat.py

The `--with pypdf --with cryptography` flags are only needed for the script's
import-time dependencies; the tests themselves only exercise stdlib paths.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the script importable as a module without invoking its `main()`.
SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_aeat as fa  # type: ignore[import-not-found]  # noqa: E402  (path tweak above)


class TestDomainFor(unittest.TestCase):
    """Regression tests for `_domain_for` — the bug that misfiled IVA pages into `cache/irpf/`.

    Original bug: `index_dir = /Sede/` for every domain, so `irpf` (first in
    INDEX_PAGES) won every prefix match. The fix derives a *unique* section
    basename from each index URL (`/Sede/iva.html` → section `/Sede/iva`)."""

    def test_index_pages_route_to_their_own_domain(self) -> None:
        self.assertEqual(fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/irpf.html"), "irpf")
        self.assertEqual(fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/iva.html"), "iva")
        self.assertEqual(fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/vivienda-otros-inmuebles.html"), "vivienda")

    def test_nested_iva_subpages_route_to_iva(self) -> None:
        # This is the URL that previously landed in `cache/irpf/`.
        self.assertEqual(
            fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias.html"),
            "iva",
        )
        self.assertEqual(
            fa._domain_for(
                "https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias/"
                "alquilo-vivienda-tengo-que-ingresar-iva.html"
            ),
            "iva",
        )
        self.assertEqual(
            fa._domain_for(
                "https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias/"
                "que-tipo-se-aplica-obras-viviendas.html"
            ),
            "iva",
        )

    def test_nested_vivienda_subpages_route_to_vivienda(self) -> None:
        # The `vivienda-otros-inmuebles` section basename is longer than the
        # domain key (`vivienda`); both must be handled correctly.
        self.assertEqual(
            fa._domain_for(
                "https://sede.agenciatributaria.gob.es/Sede/vivienda-otros-inmuebles/"
                "tributacion-arrendador-viviendas-otros-inmuebles/"
                "calculo-rendimiento-alquiler-inmueble.html"
            ),
            "vivienda",
        )

    def test_nested_irpf_subpages_route_to_irpf(self) -> None:
        self.assertEqual(
            fa._domain_for(
                "https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/"
                "pagos-fraccionados/plazos-declaracion-ingreso.html"
            ),
            "irpf",
        )

    def test_on_demand_when_url_matches_no_section(self) -> None:
        # `/Sede/Renta.html` is a real SEED_SUBPAGES entry under `irpf` but
        # it's a flat file with no `/Sede/irpf/` prefix — so it routes to
        # `on-demand`, which is the intended behavior.
        self.assertEqual(fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/Renta.html"), "on-demand")

    def test_on_demand_for_unrelated_aeat_urls(self) -> None:
        # Not under any of the three sections.
        self.assertEqual(fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/familia.html"), "on-demand")
        self.assertEqual(fa._domain_for("https://sede.agenciatributaria.gob.es/Sede/inicio.html"), "on-demand")


class TestSlugFor(unittest.TestCase):
    """`_slug_for` must be deterministic and filesystem-safe."""

    def test_is_deterministic(self) -> None:
        url = "https://sede.agenciatributaria.gob.es/Sede/iva.html"
        self.assertEqual(fa._slug_for(url), fa._slug_for(url))

    def test_includes_hash_prefix_for_uniqueness(self) -> None:
        url = "https://sede.agenciatributaria.gob.es/Sede/iva.html"
        slug = fa._slug_for(url)
        # 12-char hex prefix.
        head = slug.rsplit("-", 1)[-1]
        self.assertEqual(len(head), 12)
        int(head, 16)  # raises if not hex

    def test_html_and_pdf_with_same_basename_have_different_slugs(self) -> None:
        html = "https://sede.agenciatributaria.gob.es/Sede/iva/manual.html"
        pdf = "https://sede.agenciatributaria.gob.es/Sede/iva/manual.pdf"
        self.assertNotEqual(fa._slug_for(html), fa._slug_for(pdf))

    def test_readable_part_is_filesystem_safe(self) -> None:
        slug = fa._slug_for("https://sede.agenciatributaria.gob.es/Sede/iva/página con espacios.html")
        # Should not contain spaces, accented chars, or path separators.
        for ch in (" ", "/", "\\", "á"):
            self.assertNotIn(ch, slug)


class TestReadSourceUrl(unittest.TestCase):
    """`_read_source_url` extracts the `> Source:` line from a cached `.md`."""

    def _write(self, body: str) -> Path:
        path = SCRIPTS_DIR / "_tmp_test_source.md"
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink)
        return path

    def test_extracts_url_from_well_formed_header(self) -> None:
        path = self._write(
            "# Title\n\n"
            "> Source: https://sede.agenciatributaria.gob.es/Sede/iva.html\n"
            "> Fetched: 2026-06-29T19:39:50+02:00\n\n"
            "body\n"
        )
        self.assertEqual(fa._read_source_url(path), "https://sede.agenciatributaria.gob.es/Sede/iva.html")

    def test_finds_source_line_after_title(self) -> None:
        # Regression for an early bug where the parser short-circuited on the
        # first non-`>` line (the `# Title`) before reaching `> Source:`.
        path = self._write(
            "# Agencia Tributaria: IVA\n\n"
            "> Source: https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias.html\n"
            "> Fetched: 2026-06-29T19:40:37+02:00\n\n"
        )
        self.assertEqual(
            fa._read_source_url(path),
            "https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias.html",
        )

    def test_returns_none_when_source_line_missing(self) -> None:
        path = self._write("# Title\n\nbody without a source line\n")
        self.assertIsNone(fa._read_source_url(path))

    def test_returns_none_for_empty_file(self) -> None:
        path = self._write("")
        self.assertIsNone(fa._read_source_url(path))


class TestStripQueryFragment(unittest.TestCase):
    def test_strips_query_and_fragment(self) -> None:
        url = "https://sede.agenciatributaria.gob.es/Sede/iva.html?foo=bar#section-2"
        self.assertEqual(
            fa._strip_query_fragment(url),
            "https://sede.agenciatributaria.gob.es/Sede/iva.html",
        )

    def test_leaves_clean_url_untouched(self) -> None:
        url = "https://sede.agenciatributaria.gob.es/Sede/iva.html"
        self.assertEqual(fa._strip_query_fragment(url), url)


class TestIsPdfUrl(unittest.TestCase):
    def test_detects_pdf_suffix_case_insensitively(self) -> None:
        self.assertTrue(fa._is_pdf_url("https://example.com/file.PDF"))
        self.assertTrue(fa._is_pdf_url("https://example.com/file.pdf"))
        self.assertTrue(fa._is_pdf_url("https://example.com/path/to/Manual.pdf"))

    def test_returns_false_for_non_pdf(self) -> None:
        self.assertFalse(fa._is_pdf_url("https://example.com/file.html"))
        self.assertFalse(fa._is_pdf_url("https://example.com/file"))
        self.assertFalse(fa._is_pdf_url("https://example.com/file.pdfx"))


if __name__ == "__main__":
    unittest.main()