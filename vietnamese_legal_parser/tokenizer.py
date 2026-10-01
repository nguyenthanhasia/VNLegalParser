from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .normalization import is_probably_flattened, normalize_text

# Vietnamese point lettering in conventional legal order. ASCII letters outside this list are
# still accepted at true line starts for legacy/specialized documents.
VI_POINT_ORDER = [
    "a", "b", "c", "d", "đ", "e", "g", "h", "i", "k", "l", "m", "n", "o",
    "p", "q", "r", "s", "t", "u", "v", "x", "y",
]
_POINT_RANK = {letter: idx for idx, letter in enumerate(VI_POINT_ORDER)}

ROMAN_RE = r"[IVXLCDM]+"
ARABIC_RE = r"\d+"
LETTER_RE = r"[A-ZĐ]"
ORDINAL_WORD_RE = r"[^\s,:;.\-]+"
ARTICLE_NUM_RE = r"\d+(?:[a-zđ])?"
CLAUSE_NUM_RE = r"\d{1,3}(?:[a-zđ])?"
POINT_NUM_RE = r"[a-zđ](?:\d+)?"

KW_PART = r"(?:Phần|Phan)"
KW_CHAPTER = r"(?:Chương|Chuong)"
KW_SECTION = r"(?:Mục|Muc)"
KW_SUBSECTION = r"(?:Tiểu\s+mục|Tieu\s+muc)"
KW_DIVISION = r"(?:Tiết|Tiet)"
KW_ANNEX = r"(?:Phụ\s+lục|Phu\s+luc)"
KW_ARTICLE = r"(?:Điều|Dieu)"
KW_CLAUSE = r"(?:Khoản|Khoan)"
KW_POINT = r"(?:Điểm|Diem)"
KW_THU = r"(?:thứ|thu)"
KW_SO = r"(?:số|so)"

ORDINAL_RE = rf"{KW_THU}\s+(?:{ARABIC_RE}|{ROMAN_RE}|{ORDINAL_WORD_RE})"
PART_CHAPTER_NUM_RE = rf"(?:{ORDINAL_RE}|{ROMAN_RE}|{ARABIC_RE})"
SECTION_NUM_RE = rf"(?:{ORDINAL_RE}|{ROMAN_RE}|{ARABIC_RE}|{LETTER_RE})"
ARTICLE_FULL_NUM_RE = rf"(?:{ORDINAL_RE}|{ARTICLE_NUM_RE})"

# Anchored marker patterns. They cover modern drafting as well as historical Sắc lệnh/Hiến pháp
# forms such as "Điều thứ 1", "Chương thứ nhất", "Tiết thứ nhất" and "Mục A". Accentless
# structural keywords are accepted for degraded PDF/OCR text (Dieu, Chuong, Muc, Phu luc).
_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("part", re.compile(rf"^\s*{KW_PART}\s+(?P<number>{PART_CHAPTER_NUM_RE})\b\s*[.:\-]?\s*(?P<rest>.*)$", re.I)),
    ("chapter", re.compile(rf"^\s*{KW_CHAPTER}\s+(?P<number>{PART_CHAPTER_NUM_RE})\b\s*[.:\-]?\s*(?P<rest>.*)$", re.I)),
    ("subsection", re.compile(rf"^\s*{KW_SUBSECTION}\s+(?P<number>{SECTION_NUM_RE})\b\s*[.:\-]?\s*(?P<rest>.*)$", re.I)),
    ("section", re.compile(rf"^\s*{KW_SECTION}\s+(?P<number>{SECTION_NUM_RE})\b\s*[.:\-]?\s*(?P<rest>.*)$", re.I)),
    ("division", re.compile(rf"^\s*{KW_DIVISION}\s+(?P<number>{SECTION_NUM_RE})\b\s*[.:\-]?\s*(?P<rest>.*)$", re.I)),
    ("annex", re.compile(rf"^\s*{KW_ANNEX}(?:\s+(?:{KW_SO}\s+)?)?(?P<number>{ROMAN_RE}|{ARABIC_RE}|{LETTER_RE})?\b\s*[.:\-]?\s*(?P<rest>.*)$", re.I)),
    ("article", re.compile(rf"^\s*{KW_ARTICLE}\s+(?P<number>{ARTICLE_FULL_NUM_RE})\s*[.:]?\s*(?P<rest>.*)$", re.I)),
    ("clause", re.compile(rf"^\s*(?:{KW_CLAUSE}\s+)?(?P<number>{CLAUSE_NUM_RE})\s*[.)]\s*(?P<rest>.*)$", re.I)),
    ("point", re.compile(rf"^\s*(?:{KW_POINT}\s+)?(?P<number>{POINT_NUM_RE})\s*[).]\s*(?P<rest>.*)$", re.I)),
]

# Inline mode is only for text whose line boundaries were destroyed. Candidate matching is broad,
# then context/sequence rules reject ordinary citations and numeric prose.
_INLINE_MAJOR_CANDIDATE = re.compile(
    rf"(?i)(?P<marker>{KW_PART}\s+{PART_CHAPTER_NUM_RE}(?=\s|[.:\-]|$)|"
    rf"{KW_CHAPTER}\s+{PART_CHAPTER_NUM_RE}(?=\s|[.:\-]|$)|"
    rf"{KW_SUBSECTION}\s+{SECTION_NUM_RE}(?=\s|[.:\-]|$)|"
    rf"{KW_SECTION}\s+{SECTION_NUM_RE}(?=\s|[.:\-]|$)|"
    rf"{KW_DIVISION}\s+{SECTION_NUM_RE}(?=\s|[.:\-]|$)|"
    rf"{KW_ANNEX}(?:\s+(?:{KW_SO}\s+)?)?(?:{ROMAN_RE}|{ARABIC_RE}|{LETTER_RE})?|"
    rf"{KW_ARTICLE}\s+{ARTICLE_FULL_NUM_RE}(?=\s|[.:]|$)\s*[.:]?)"
)
_INLINE_MINOR_CANDIDATE = re.compile(rf"(?i)(?P<marker>(?:(?:(?<!\w)|(?<=[^\W\d_])){CLAUSE_NUM_RE}[.)])|(?:(?<!\w){POINT_NUM_RE}[).]))\s*")


@dataclass(slots=True)
class Marker:
    element_type: str
    number: str
    marker: str
    rest: str
    line_no: int
    start: int
    end: int
    inside_quote: bool = False
    source: str = "line"
    raw_line: str = ""
    raw_number: str = ""


@dataclass(slots=True)
class Segment:
    kind: str  # marker | text
    text: str
    line_no: int
    marker: Marker | None = None


@dataclass(slots=True)
class LogicalLine:
    text: str
    source: str = "line"


def _canonical_number(element_type: str, number: str | None) -> str:
    value = (number or "").strip().rstrip(".:)")
    if element_type in {"point", "article", "clause"}:
        return value.lower()
    if element_type in {"part", "chapter", "section", "subsection", "division", "annex"}:
        # Structural numbers are semantic identifiers, not presentation text. Canonicalize Roman
        # numerals/lettered sections so OCR/case noise does not change the parsed identity.
        if re.fullmatch(r"[ivxlcdm]+", value, re.I):
            return value.upper()
        if re.fullmatch(r"[a-zđ]", value, re.I):
            return value.upper()
        if re.match(r"(?i)^(?:thứ|thu)\s+", value):
            return value.lower()
        return value
    return value


def recognize_line_marker(line: str, line_no: int = 0) -> Marker | None:
    # Accept opening quotes in the raw line, but mark them as embedded so the parser can keep
    # amendment quotations out of the document's primary hierarchy.
    stripped = line.lstrip()
    inside_quote = stripped.startswith(("“", '"', "‘", "'"))
    probe = stripped[1:].lstrip() if inside_quote else stripped

    for element_type, rx in _MARKERS:
        match = rx.match(probe)
        if not match:
            continue
        raw_number = (match.groupdict().get("number") or "").strip().rstrip(".:)")
        number = _canonical_number(element_type, raw_number)
        marker_text = probe[: match.start("rest")].strip()
        return Marker(
            element_type=element_type,
            number=number,
            marker=marker_text,
            rest=(match.groupdict().get("rest") or "").strip(),
            line_no=line_no,
            start=0,
            end=len(line),
            inside_quote=inside_quote,
            source="line",
            raw_line=line,
            raw_number=raw_number,
        )
    return None


def _quote_mask(text: str) -> list[bool]:
    """Return a mask indicating whether each position is inside a quotation.

    Handles Vietnamese curly quotes and common ASCII quotes. Apostrophes inside words are ignored.
    """
    mask = [False] * (len(text) + 1)
    curly = 0
    single_curly = 0
    ascii_double = False
    ascii_single = False
    for i, ch in enumerate(text):
        mask[i] = bool(curly or single_curly or ascii_double or ascii_single)
        if ch == "“":
            curly += 1
        elif ch == "”" and curly:
            curly -= 1
        elif ch == "‘":
            single_curly += 1
        elif ch == "’" and single_curly:
            single_curly -= 1
        elif ch == '"':
            ascii_double = not ascii_double
        elif ch == "'":
            prev_word = i > 0 and text[i - 1].isalnum()
            next_word = i + 1 < len(text) and text[i + 1].isalnum()
            if not (prev_word and next_word):
                ascii_single = not ascii_single
    mask[len(text)] = bool(curly or single_curly or ascii_double or ascii_single)
    return mask


def _fold_ascii(value: str) -> str:
    import unicodedata
    folded = unicodedata.normalize("NFKD", value)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return folded.replace("đ", "d").replace("Đ", "D").lower()


def _major_kind(marker: str) -> str:
    lower = _fold_ascii(marker)
    if lower.startswith("phan"):
        return "part"
    if lower.startswith("chuong"):
        return "chapter"
    if lower.startswith("tieu muc"):
        return "subsection"
    if lower.startswith("muc"):
        return "section"
    if lower.startswith("tiet"):
        return "division"
    if lower.startswith("phu luc"):
        return "annex"
    return "article"


def _upper_heading_between(value: str) -> bool:
    clean = value.strip(" \t\n.,;:-_–—")
    if not clean or len(clean) > 220:
        return False
    letters = [c for c in clean if c.isalpha()]
    if not letters:
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= 0.72


def _suffix_rank(value: str) -> int | None:
    if not value:
        return -1
    return _POINT_RANK.get(value.lower())


def clause_follows(previous: str | None, current: str) -> bool:
    """Conservative numbering transition for flattened text.

    Supports 1, 2, 2a, 2b, 3 while rejecting years and unrelated numbered prose.
    """
    try:
        base, suffix = split_clause_number(current)
    except ValueError:
        return False
    if base > 300:
        return False
    if previous is None:
        return base == 1 and suffix == ""
    try:
        pbase, psuffix = split_clause_number(previous)
    except ValueError:
        return False
    if base == pbase:
        sr = _suffix_rank(suffix)
        pr = _suffix_rank(psuffix)
        return bool(suffix) and sr is not None and pr is not None and sr == pr + 1
    return base == pbase + 1 and suffix == ""


def point_follows(previous: str | None, current: str) -> bool:
    """Conservative transition for a), a1), a2), b), ... in flattened text."""
    rank, suffix = split_point_number(current)
    if rank is None or suffix is None:
        return False
    if previous is None:
        return rank == 0 and suffix == 0
    prank, psuffix = split_point_number(previous)
    if prank is None or psuffix is None:
        return False
    if rank == prank:
        return suffix == psuffix + 1 and suffix > 0
    return rank == prank + 1 and suffix == 0


_INLINE_REFERENCE_CUE = re.compile(
    r"(?ix)^\s*(?:của|cua|thuộc|thuoc|tại|tai|đến|den|theo|ban\s+hành|ban\s+hanh|kèm\s+theo|kem\s+theo|"
    r"nêu\s+tại|neu\s+tai|nêu\s+trên|neu\s+tren|"
    r"(?:Bộ\s+luật|Bo\s+luat|Luật|Luat|Nghị\s+định|Nghi\s+dinh|Thông\s+tư|Thong\s+tu|"
    r"Nghị\s+quyết|Nghi\s+quyet|Quyết\s+định|Quyet\s+dinh|văn\s+bản|van\s+ban)\b)"
)


def _previous_boundary_char(text: str, pos: int) -> str:
    """Return the meaningful character before a candidate, skipping closing quote/bracket glyphs."""
    prefix = text[:pos].rstrip()
    while prefix and prefix[-1] in '”’"\')]}»':
        prefix = prefix[:-1].rstrip()
    return prefix[-1:] if prefix else ""


def _inline_major_looks_like_reference(text: str, marker_end: int, kind: str, marker_text: str) -> bool:
    tail = text[marker_end: marker_end + 120]
    # A punctuation-terminated article/chapter number is strong heading syntax. Annex headings are
    # special because references commonly use `Phụ lục I ban hành kèm theo ...` without punctuation.
    if kind != "annex" and marker_text.rstrip().endswith((".", ":")):
        return False
    return bool(_INLINE_REFERENCE_CUE.match(tail))


def _split_flattened(text: str) -> list[str]:
    """Reconstruct likely structural boundaries in flattened legal text.

    Major candidates are accepted only at strong boundaries, or when an article follows a clearly
    uppercase heading. Minor enumerators use strict sequence validation, which rejects years such as
    2023. without requiring fragile punctuation assumptions.
    """
    quote_mask = _quote_mask(text)
    cuts: list[int] = [0]
    accepted_majors: list[tuple[int, int, str, str]] = []

    for match in _INLINE_MAJOR_CANDIDATE.finditer(text):
        pos = match.start("marker")
        end = match.end("marker")
        if quote_mask[pos]:
            continue
        marker = match.group("marker")
        kind = _major_kind(marker)
        prev_nonspace = _previous_boundary_char(text, pos)
        strong_boundary = pos == 0 or prev_nonspace in ".;:!?"
        if _inline_major_looks_like_reference(text, end, kind, marker):
            continue

        heading_boundary = False
        # Partial PDF extraction often merges an uppercase title with the next structural marker,
        # e.g. `QUY ĐỊNH CHUNG Điều 1...`. The uppercase prefix is strong layout evidence even when
        # there is no earlier marker in the same physical line.
        if pos > 0 and not accepted_majors and kind in {"chapter", "section", "subsection", "division", "article"}:
            heading_boundary = _upper_heading_between(text[:pos])
        if kind == "article" and accepted_majors:
            pstart, pend, pkind, _ = accepted_majors[-1]
            if pkind in {"part", "chapter", "section", "subsection", "division", "annex"}:
                heading_boundary = _upper_heading_between(text[pend:pos])

        # A new major structural container can also follow an uppercase title of the previous major.
        if kind in {"chapter", "section", "subsection", "division"} and accepted_majors:
            _, pend, pkind, _ = accepted_majors[-1]
            if pkind in {"part", "chapter", "section", "subsection", "division"}:
                heading_boundary = heading_boundary or _upper_heading_between(text[pend:pos])

        if not (strong_boundary or heading_boundary):
            continue
        accepted_majors.append((pos, end, kind, marker))
        cuts.append(pos)

    # Scan minor markers within each accepted article span. Search is broad; sequence is strict.
    for idx, (major_pos, major_end, kind, _) in enumerate(accepted_majors):
        if kind != "article":
            continue
        span_end = accepted_majors[idx + 1][0] if idx + 1 < len(accepted_majors) else len(text)
        last_clause_marker: str | None = None
        last_point_marker: str | None = None
        for match in _INLINE_MINOR_CANDIDATE.finditer(text, major_end, span_end):
            pos = match.start("marker")
            if quote_mask[pos]:
                continue
            raw_marker = match.group("marker")
            marker = raw_marker.rstrip(".)").lower()
            prev_nonspace = _previous_boundary_char(text, pos)
            # The first minor marker may directly follow an article title after whitespace. Once a
            # sequence has started, require punctuation before later candidates so phrases like
            # `sửa đổi khoản 3.` are not promoted to hierarchy.
            sequence_started = last_clause_marker is not None or last_point_marker is not None
            if sequence_started and prev_nonspace not in ".;:!?":
                continue
            if marker[0].isdigit():
                if _minor_marker_payload_is_numeric(text, match.end("marker")):
                    continue
                if clause_follows(last_clause_marker, marker):
                    cuts.append(pos)
                    last_clause_marker = marker
                    last_point_marker = None
                continue
            # Vietnamese legal points canonically use `a)`. In flattened excerpts points can jump
            # (a -> đ) or sit directly under an Article, so parenthesized points are accepted at a
            # strong boundary even when intermediate letters are missing. Dotted points still need
            # sequential evidence because `a.` is ambiguous with ordinary prose/list notation.
            canonical_parenthesis = raw_marker.rstrip().endswith(")")
            if canonical_parenthesis and (prev_nonspace in ".;:!?" or last_clause_marker is not None or last_point_marker is not None):
                cuts.append(pos)
                last_point_marker = marker
                continue
            if point_follows(last_point_marker, marker):
                cuts.append(pos)
                last_point_marker = marker

    cuts = sorted(set(cuts))
    chunks: list[str] = []
    for i, start in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _minor_marker_payload_is_numeric(text: str, marker_end: int) -> bool:
    rest = text[marker_end:].lstrip()
    if not rest:
        return False
    if rest.startswith(("|", "¦", "│", "┆", "┊")):
        return True
    return bool(re.match(r"^\d+(?:[.,/%‰]|\b)", rest))


def _split_generic_minor_candidates(line: str) -> list[str]:
    """Split strong inline minor candidates and let the parser classify them later.

    This is intentionally candidate-oriented: a split does not mean a node will be created. The
    contextual parser still rejects bad sequence transitions, numeric payloads and quoted markers.
    """
    matches = list(_INLINE_MINOR_CANDIDATE.finditer(line))
    if not matches:
        return [line]
    quote_mask = _quote_mask(line)
    cuts = [0]
    for match in matches:
        pos = match.start("marker")
        if pos == 0:
            continue
        # Same-line quote state is known here. Cross-line quote state is handled later by tokenize().
        if quote_mask[pos]:
            continue
        if _previous_boundary_char(line, pos) not in ".;:!?":
            continue
        raw = match.group("marker")
        if raw[0].isdigit():
            if _minor_marker_payload_is_numeric(line, match.end("marker")):
                continue
            cuts.append(pos)
        elif raw.rstrip().endswith(")"):
            cuts.append(pos)
        else:
            # Dotted letters are ambiguous; exposing them as candidates is safe because context.py
            # requires neighboring sequence evidence before promoting them.
            cuts.append(pos)
    cuts = sorted(set(cuts))
    if len(cuts) == 1:
        return [line]
    out: list[str] = []
    for idx, start in enumerate(cuts):
        end = cuts[idx + 1] if idx + 1 < len(cuts) else len(line)
        chunk = line[start:end].strip()
        if chunk:
            out.append(chunk)
    return out or [line]


def _split_partially_flattened_line(line: str) -> list[str]:
    """Recover boundaries inside one physical line without assuming the whole document is flat.

    This catches PDF extraction such as ``1. A. 2. B.`` while preserving ordinary decimal/date
    prose. The whole-line flattened splitter is tried first because it has stronger major-heading
    context. A second pass handles lines that begin with an already-known clause/point marker.
    """
    if not line.strip() or line.lstrip().startswith("[TABLE]"):
        return [line]

    direct = recognize_line_marker(line, line_no=0)
    major_count = sum(1 for _ in _INLINE_MAJOR_CANDIDATE.finditer(line))
    minor_matches = list(_INLINE_MINOR_CANDIDATE.finditer(line))

    # Major markers or an inline article with clauses can be reconstructed by the existing strict
    # flattened-text algorithm even when surrounding physical lines are healthy.
    if major_count >= 1 and (major_count >= 2 or direct is None or len(minor_matches) >= 2):
        chunks = _split_flattened(line)
        if len(chunks) > 1:
            return chunks

    if direct is not None and direct.element_type in {"part", "chapter", "section", "subsection", "division", "annex", "article"}:
        # A structural reference can be merged with the following real clause by PDF extraction:
        # `Phụ lục I ban hành kèm theo ... . 2. Nội dung`. Split the later candidate so the parser
        # can reject the reference but still see the genuine clause in article context.
        if _INLINE_REFERENCE_CUE.match(direct.rest or ""):
            ref_cuts = [0]
            for match in minor_matches:
                pos = match.start("marker")
                if pos == 0 or _quote_mask(line)[pos]:
                    continue
                if _previous_boundary_char(line, pos) not in ".;:!?":
                    continue
                raw = match.group("marker")
                if raw[0].isdigit() and not _minor_marker_payload_is_numeric(line, match.end("marker")):
                    ref_cuts.append(pos)
            if len(ref_cuts) > 1:
                out = []
                ref_cuts = sorted(set(ref_cuts))
                for idx, start in enumerate(ref_cuts):
                    end = ref_cuts[idx + 1] if idx + 1 < len(ref_cuts) else len(line)
                    chunk = line[start:end].strip()
                    if chunk:
                        out.append(chunk)
                return out
        return _split_generic_minor_candidates(line)
    if direct is None or direct.element_type not in {"clause", "point"}:
        return _split_generic_minor_candidates(line)

    quote_mask = _quote_mask(line)
    cuts = [0]
    last_clause: str | None = direct.number if direct.element_type == "clause" else None
    last_point: str | None = direct.number if direct.element_type == "point" else None

    for match in minor_matches:
        pos = match.start("marker")
        if pos == 0 or quote_mask[pos]:
            continue
        marker_text = match.group("marker")
        number = marker_text.rstrip(".)").lower()
        prev_nonspace = _previous_boundary_char(line, pos)
        if prev_nonspace not in ".;:!?":
            continue
        if number[0].isdigit():
            if _minor_marker_payload_is_numeric(line, match.end("marker")):
                continue
            if last_clause is not None and clause_follows(last_clause, number):
                cuts.append(pos)
                last_clause = number
                last_point = None
            continue
        canonical_parenthesis = marker_text.rstrip().endswith(")")
        if canonical_parenthesis:
            cuts.append(pos)
            last_point = number
            continue
        if point_follows(last_point, number):
            cuts.append(pos)
            last_point = number

    cuts = sorted(set(cuts))
    if len(cuts) == 1:
        return _split_generic_minor_candidates(line)
    out: list[str] = []
    for idx, start in enumerate(cuts):
        end = cuts[idx + 1] if idx + 1 < len(cuts) else len(line)
        chunk = line[start:end].strip()
        if chunk:
            out.append(chunk)
    return out or [line]


def _expand_partial_line(line: str, *, max_rounds: int = 4) -> list[str]:
    chunks = [line]
    for _ in range(max_rounds):
        changed = False
        next_chunks: list[str] = []
        for chunk in chunks:
            split = _split_partially_flattened_line(chunk)
            if len(split) > 1:
                changed = True
            next_chunks.extend(split)
        chunks = next_chunks
        if not changed:
            break
    return chunks


def logical_lines(text: str) -> tuple[list[LogicalLine], bool, dict]:
    normalized = normalize_text(text)
    raw_lines = [line for line in normalized.splitlines() if line.strip()]
    flattened = is_probably_flattened(normalized)
    if len(raw_lines) == 1 and raw_lines:
        line = raw_lines[0]
        direct = recognize_line_marker(line, line_no=1)
        major_count = sum(1 for _ in _INLINE_MAJOR_CANDIDATE.finditer(line))
        minor_count = sum(1 for _ in _INLINE_MINOR_CANDIDATE.finditer(line))
        # Short copy/paste snippets are often fully flattened even when below the generic length
        # threshold. Trigger fallback when structure is visible inside a single physical line.
        if (direct is None and major_count >= 1) or major_count >= 2 or (direct is not None and minor_count >= 2):
            flattened = True
    if flattened:
        # Once the document has been classified as layout-flattened, remaining physical newlines are
        # no longer trustworthy boundaries. Collapse them before candidate reconstruction so a chunk
        # never contains an embedded newline that would defeat anchored marker recognition.
        flat_text = re.sub(r"\s*\n\s*", " ", normalized).strip()
        chunks = _split_flattened(flat_text)
        return (
            [LogicalLine(chunk, "inline_fallback") for chunk in chunks],
            True,
            {
                "reconstructed_boundary_count": max(0, len(chunks) - 1),
                "reconstructed_physical_line_count": 1 if len(chunks) > 1 else 0,
            },
        )

    logical: list[LogicalLine] = []
    reconstructed_boundaries = 0
    reconstructed_physical_lines = 0
    for line in raw_lines:
        chunks = _expand_partial_line(line)
        if len(chunks) > 1:
            reconstructed_physical_lines += 1
            reconstructed_boundaries += len(chunks) - 1
            logical.extend(LogicalLine(chunk, "boundary_reconstruction") for chunk in chunks)
        else:
            logical.append(LogicalLine(line, "line"))
    return logical, False, {
        "reconstructed_boundary_count": reconstructed_boundaries,
        "reconstructed_physical_line_count": reconstructed_physical_lines,
    }


def _update_quote_state(line: str, state: dict[str, int | bool]) -> None:
    # Stateful across lines so multi-line amendment quotations stay embedded.
    for i, ch in enumerate(line):
        if ch == "“":
            state["curly"] = int(state["curly"]) + 1
        elif ch == "”" and int(state["curly"]) > 0:
            state["curly"] = int(state["curly"]) - 1
        elif ch == '"':
            state["double"] = not bool(state["double"])
        elif ch == "‘":
            state["single_curly"] = int(state["single_curly"]) + 1
        elif ch == "’" and int(state["single_curly"]) > 0:
            state["single_curly"] = int(state["single_curly"]) - 1
        elif ch == "'":
            prev_word = i > 0 and line[i - 1].isalnum()
            next_word = i + 1 < len(line) and line[i + 1].isalnum()
            if not (prev_word and next_word):
                state["single"] = not bool(state["single"])


def tokenize(text: str) -> tuple[list[Segment], dict]:
    lines, flattened, reconstruction_stats = logical_lines(text)
    segments: list[Segment] = []
    quote_state: dict[str, int | bool] = {"curly": 0, "single_curly": 0, "double": False, "single": False}
    for line_no, logical in enumerate(lines, 1):
        line = logical.text
        was_inside_quote = bool(quote_state["curly"] or quote_state["single_curly"] or quote_state["double"] or quote_state["single"])
        marker = recognize_line_marker(line, line_no=line_no)
        if marker:
            marker.inside_quote = marker.inside_quote or was_inside_quote
            marker.source = logical.source
            segments.append(Segment(kind="marker", text=line, line_no=line_no, marker=marker))
        else:
            segments.append(Segment(kind="text", text=line, line_no=line_no))
        _update_quote_state(line, quote_state)
    return segments, {
        "flattened_input": flattened,
        "logical_line_count": len(lines),
        **reconstruction_stats,
    }


def point_rank(value: str) -> int | None:
    match = re.match(r"^([a-zđ])", value.lower())
    return _POINT_RANK.get(match.group(1)) if match else None


def split_clause_number(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d{1,3})([a-zđ]?)", value.lower())
    if not match:
        raise ValueError(value)
    return int(match.group(1)), match.group(2)


def split_point_number(value: str) -> tuple[int | None, int | None]:
    match = re.fullmatch(r"([a-zđ])(\d*)", value.lower())
    if not match:
        return None, None
    rank = _POINT_RANK.get(match.group(1))
    suffix = int(match.group(2)) if match.group(2) else 0
    return rank, suffix


def iter_markers(segments: Iterable[Segment]) -> Iterable[Marker]:
    for segment in segments:
        if segment.marker is not None:
            yield segment.marker
