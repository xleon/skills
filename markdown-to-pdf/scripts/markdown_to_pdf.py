#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "markdown>=3.10",
#     "playwright>=1.49.0",
# ]
# ///

from __future__ import annotations

import argparse
import html
import re
import tempfile
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright


PDF_CSS = """
@page {
  size: A4;
  margin: 20mm 18mm 22mm 18mm;
}

* {
  box-sizing: border-box;
}

html {
  font-size: 11pt;
}

body {
  margin: 0;
  color: #1a1a2e;
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.5;
  background: #fff;
}

main {
  width: 100%;
}

h1, h2, h3, h4 {
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.2;
  margin-top: 0;
}

h1 {
  font-size: 18pt;
  margin-bottom: 0.3rem;
  text-align: center;
  color: #fff;
  background: #1a3a5c;
  padding: 0.9rem 1.2rem;
  border-radius: 4px;
  letter-spacing: 0.04em;
}

h2 {
  font-size: 12pt;
  margin-top: 1.8rem;
  margin-bottom: 0.6rem;
  padding: 0.3rem 0.7rem;
  background: #e8f0f8;
  border-left: 4px solid #1a3a5c;
  color: #1a3a5c;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

h3 {
  font-size: 11pt;
  margin-top: 1.2rem;
  margin-bottom: 0.4rem;
  color: #2c5f8a;
}

p, ul, ol, blockquote, hr, figure {
  margin-top: 0;
  margin-bottom: 0.9rem;
}

p, ul, ol, blockquote {
  font-size: 10.5pt;
}

ul, ol {
  padding-left: 1.3rem;
}

li + li {
  margin-top: 0.2rem;
}

blockquote {
  padding: 0.5rem 0.9rem;
  border-left: 3px solid #2c5f8a;
  background: #f0f6fc;
  color: #1a3a5c;
  margin-left: 0;
  margin-right: 0;
}

blockquote p:last-child {
  margin-bottom: 0;
}

strong {
  color: #1a1a2e;
}

hr {
  border: 0;
  border-top: 2px solid #1a3a5c;
  margin: 1.5rem 0;
  opacity: 0.25;
}

img {
  display: block;
  max-width: 100%;
  max-height: 160mm;
  height: auto;
  margin: 0.5rem auto;
}

a {
  color: #2c5f8a;
  text-decoration: underline;
}

.table-block {
  width: 100%;
  break-inside: avoid;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 9.5pt;
  line-height: 1.35;
}

thead {
  display: table-header-group;
}

tr {
  break-inside: avoid;
}

th, td {
  border: 1px solid #a8c4de;
  padding: 5px 7px;
  vertical-align: top;
  text-align: left;
}

th {
  background: #1a3a5c;
  color: #fff;
  font-weight: bold;
}

tbody tr:nth-child(even) td {
  background: #f0f6fc;
}

tbody tr:last-child td {
  font-weight: bold;
  background: #ddeaf5;
}

td img {
  max-height: 14mm;
  width: auto;
  margin: 0 auto;
}

"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Markdown file to a styled PDF.")
    parser.add_argument("input", help="Markdown file to render")
    parser.add_argument("-o", "--output", help="Output PDF path")
    parser.add_argument(
        "--title",
        help="Optional PDF title. Defaults to the first H1 or the input file stem.",
    )
    return parser.parse_args()


def markdown_to_html(markdown_text: str) -> str:
    renderer = markdown.Markdown(
        extensions=["extra", "tables", "sane_lists", "smarty"],
        output_format="html",
    )
    html_body = renderer.convert(markdown_text)
    return re.sub(
        r"(<table>.*?</table>)",
        lambda match: f'<div class="table-block">{match.group(1)}</div>',
        html_body,
        flags=re.DOTALL,
    )


def rewrite_local_urls(html_body: str, base_dir: Path) -> str:
    def replace_attr(match: re.Match[str]) -> str:
        attr = match.group(1)
        url = match.group(2)
        if re.match(r"^(?:[a-z]+:|#|//)", url, re.IGNORECASE):
            return match.group(0)

        resolved = (base_dir / url).resolve().as_uri()
        return f'{attr}="{resolved}"'

    return re.sub(r'(src|href)="([^"]+)"', replace_attr, html_body)


def extract_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def build_html_document(title: str, body_html: str, base_dir: Path, source_name: str) -> str:
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_title}</title>
    <base href="{base_dir.as_uri()}/">
    <style>{PDF_CSS}</style>
  </head>
  <body>
    <main>
      {body_html}
    </main>
  </body>
</html>
"""


def wait_for_assets(page) -> None:
    page.wait_for_load_state("networkidle")
    page.evaluate(
        """
        async () => {
          await document.fonts.ready;
          const images = Array.from(document.images);
          await Promise.all(images.map((img) => {
            if (img.complete) {
              return Promise.resolve();
            }
            return new Promise((resolve) => {
              img.addEventListener('load', resolve, { once: true });
              img.addEventListener('error', resolve, { once: true });
            });
          }));
        }
        """
    )


def render_pdf(input_path: Path, output_path: Path, title: str) -> None:
    markdown_text = input_path.read_text(encoding="utf-8")
    body_html = markdown_to_html(markdown_text)
    body_html = rewrite_local_urls(body_html, input_path.parent)
    html_document = build_html_document(title, body_html, input_path.parent, input_path.name)

    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as handle:
        handle.write(html_document)
        html_path = Path(handle.name)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--allow-file-access-from-files"])
            page = browser.new_page()
            page.goto(html_path.as_uri(), wait_until="load")
            wait_for_assets(page)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            page.pdf(
                path=str(output_path),
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=False,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            browser.close()
    finally:
        html_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"Markdown file not found: {input_path}")

    default_output = input_path.with_suffix(".pdf")
    output_path = Path(args.output).expanduser().resolve() if args.output else default_output

    markdown_text = input_path.read_text(encoding="utf-8")
    title = args.title or extract_title(markdown_text, input_path.stem)
    render_pdf(input_path, output_path, title)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
