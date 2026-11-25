"""Convertit un document Markdown de docs/ en PDF.

Usage : pip install -e ".[doc]" puis python docs/pdf.py docs/dossier_technique.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown
from xhtml2pdf import pisa

STYLE = """
@page { size: a4; margin: 2cm 2cm 2.2cm 2cm;
        @frame pied { -pdf-frame-content: pied; bottom: 1cm; height: 1cm; } }
body { font-family: Helvetica; font-size: 10.5pt; line-height: 1.35; }
h1 { font-size: 17pt; margin-top: 0; -pdf-keep-with-next: true; }
h1.partie { page-break-before: always; }
h2 { font-size: 13pt; margin-top: 14pt; -pdf-keep-with-next: true; }
h3 { font-size: 11pt; -pdf-keep-with-next: true; }
table { border: 0.5pt solid #888; margin: 6pt 0; }
th { background-color: #e8e8e8; padding: 3pt; font-size: 9pt; }
td { padding: 3pt; font-size: 9pt; vertical-align: top; }
pre { background-color: #f4f4f4; font-family: Courier; font-size: 8.5pt;
      padding: 6pt; border: 0.5pt solid #ccc; }
code { font-family: Courier; font-size: 9pt; }
#pied { text-align: center; font-size: 8pt; color: #666; }
"""


def convertir(source: Path) -> Path:
    texte = source.read_text(encoding="utf-8")
    # L'en-tête YAML ne sert qu'à d'autres outils : on le retire.
    texte = re.sub(r"\A---\n.*?\n---\n", "", texte, flags=re.S)
    corps = markdown.markdown(texte, extensions=["tables", "fenced_code"])
    # Chaque grande partie (h1 numéroté) commence sur une nouvelle page.
    corps = re.sub(r"<h1>(\d\.)", r'<h1 class="partie">\1', corps)
    html = (
        f"<html><head><meta charset='utf-8'><style>{STYLE}</style></head><body>"
        f"<div id='pied'>page <pdf:pagenumber/></div>{corps}</body></html>"
    )
    cible = source.with_suffix(".pdf")
    with cible.open("wb") as f:
        resultat = pisa.CreatePDF(html, dest=f, encoding="utf-8")
    if resultat.err:
        raise SystemExit(f"échec de la conversion de {source}")
    return cible


if __name__ == "__main__":
    for nom in sys.argv[1:]:
        print(convertir(Path(nom)))
