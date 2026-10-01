from __future__ import annotations

import html
import re
import unicodedata
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "div", "dl", "dt", "dd",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4",
    "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
    "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}


class _LegalHTMLTextExtractor(HTMLParser):
    """HTML-to-text extractor that preserves legal block boundaries and table semantics.

    Multi-cell table rows are prefixed with ``[TABLE]`` so row numbers such as ``1.`` or ``a)``
    cannot be mistaken for legal clauses/points. The data is preserved for downstream indexing.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._table_depth = 0
        self._row_depth = 0
        self._cell_depth = 0
        self._row_cells: list[str] = []
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if tag == "table":
            self._table_depth += 1
            self.parts.append("\n")
            return
        if self._table_depth:
            if tag == "tr":
                self._row_depth += 1
                self._row_cells = []
            elif tag in {"td", "th"} and self._row_depth:
                self._cell_depth += 1
                self._cell_parts = []
            elif tag == "br" and self._cell_depth:
                self._cell_parts.append(" ")
            return

        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return

        if self._table_depth:
            if tag in {"td", "th"} and self._cell_depth:
                value = re.sub(r"\s+", " ", "".join(self._cell_parts)).strip()
                self._row_cells.append(value)
                self._cell_parts = []
                self._cell_depth = max(0, self._cell_depth - 1)
                return
            if tag == "tr" and self._row_depth:
                cells = [cell for cell in self._row_cells if cell]
                if cells:
                    # Prefix every table row, including one-cell rows. A real structural heading
                    # should live in document paragraphs, not be inferred from tabular data.
                    self.parts.append("\n[TABLE] " + " | ".join(cells) + "\n")
                self._row_cells = []
                self._row_depth = max(0, self._row_depth - 1)
                return
            if tag == "table":
                self._table_depth = max(0, self._table_depth - 1)
                self.parts.append("\n")
                return
            return

        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._table_depth:
            if self._cell_depth:
                self._cell_parts.append(data)
            return
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def html_to_text(value: str) -> str:
    parser = _LegalHTMLTextExtractor()
    parser.feed(value)
    parser.close()
    return html.unescape(parser.get_text())


def looks_like_html(value: str) -> bool:
    head = value[:4096].lower()
    return bool(re.search(r"<(?:html|body|div|p|table|br|span|h[1-6])\b", head))


_PDF_SPLIT_LEGAL_CUES = (
    (re.compile(r"(?iu)\bc\s+ủa\b"), "của"),
    (re.compile(r"(?iu)\blu\s+ật\b"), "luật"),
    (re.compile(r"(?iu)\bđi\s+ều\b"), "điều"),
    (re.compile(r"(?iu)\bkho\s+ản\b"), "khoản"),
    (re.compile(r"(?iu)\bđi\s+ểm\b"), "điểm"),
    (re.compile(r"(?iu)\bch\s+ương\b"), "chương"),
    (re.compile(r"(?iu)\bm\s+ục\b"), "mục"),
)


def _repair_pdf_split_legal_cues(value: str) -> str:
    """Repair conservative PDF extraction splits inside high-value Vietnamese legal cue words.

    Some PDF text extractors emit forms such as ``c ủa Lu ật``.  The repair is deliberately
    limited to legal cue words used by the contextual classifier, avoiding broad word-joining
    heuristics that could corrupt legitimate prose.
    """
    def repl(match: re.Match[str], replacement: str) -> str:
        compact = re.sub(r"\s+", "", match.group(0))
        letters = "".join(ch for ch in compact if ch.isalpha())
        if letters and letters.isupper():
            return replacement.upper()
        if compact[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    for rx, replacement in _PDF_SPLIT_LEGAL_CUES:
        value = rx.sub(lambda m, word=replacement: repl(m, word), value)
    return value


def normalize_text(text: str | None, *, detect_html: bool = True) -> str:
    """Normalize text without destroying legal structure.

    Key rule: preserve newlines. The previous implementation collapsed whitespace before parsing,
    which made years and references indistinguishable from structural markers.
    """
    if not text:
        return ""
    value = str(text)
    if detect_html and looks_like_html(value):
        value = html_to_text(value)

    value = unicodedata.normalize("NFC", value)
    value = value.replace("\ufeff", "").replace("\u200b", "")
    # Collapse every Unicode horizontal separator (NBSP, thin space, figure space, etc.) to a
    # regular space. PDF/OCR extractors use these interchangeably with ASCII spaces.
    value = "".join(" " if unicodedata.category(ch) == "Zs" else ch for ch in value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u201c", "“").replace("\u201d", "”")
    value = value.replace("\u2018", "‘").replace("\u2019", "’")
    value = _repair_pdf_split_legal_cues(value)

    # Remove Markdown heading/list decoration while keeping the text itself.
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", value)

    # Conservative cleanup for common Công báo/PDF headers. Never remove bare numbers because
    # they can be genuine legal enumerators after imperfect extraction.
    value = re.sub(r"(?im)^\s*CÔNG\s+BÁO\s*/\s*Số[^\n]*$", "", value)

    lines: list[str] = []
    for raw in value.split("\n"):
        line = re.sub(r"[\t\f\v ]+", " ", raw).strip()
        lines.append(line)

    # Collapse 3+ blank lines to one blank separator, preserve single newlines.
    value = "\n".join(lines)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def is_probably_flattened(text: str) -> bool:
    if not text:
        return False
    nonempty = [line for line in text.splitlines() if line.strip()]
    if not nonempty:
        return False
    longest = max(len(line) for line in nonempty)
    avg = sum(map(len, nonempty)) / len(nonempty)
    return (len(nonempty) == 1 and len(text) >= 120) or (len(nonempty) <= 3 and len(text) >= 250) or longest >= 500 or avg >= 300


def normalized_for_matching(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
