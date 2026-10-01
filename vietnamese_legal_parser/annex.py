from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from .normalization import normalize_text, normalized_for_matching
from .tokenizer import Marker, recognize_line_marker

_REFERENCE_CUE = re.compile(
    r"(?i)^(?:ban\s+hành|kèm\s+theo|được\s+viện\s+dẫn|tại\b|của\b|theo\b|thuộc\b)"
)


@dataclass(slots=True)
class AnnexBlock:
    index: int
    number: str
    heading: str
    raw_text: str
    normalized_text: str
    start_line: int
    parsed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def is_structural_annex_marker(marker: Marker) -> bool:
    """Conservatively decide whether a standalone Phụ lục line starts the attachment tail."""
    if marker.element_type != "annex" or marker.inside_quote:
        return False
    raw = marker.raw_line.strip()
    rest = marker.rest.strip()
    # A naked/generic "PHỤ LỤC" is a valid boundary. This intentionally solves real sources where
    # a generic heading is followed by "PHỤ LỤC I" on the next line.
    if not rest or rest.startswith("("):
        return True
    # Same-line "PHỤ LỤC I ban hành kèm theo ..." inside body text is commonly a reference.
    if _REFERENCE_CUE.match(rest):
        return False
    first_words = " ".join(raw.split()[:2])
    uppercase_heading = first_words.upper() == first_words and any(ch.isalpha() for ch in first_words)
    return uppercase_heading and len(rest) <= 180


def split_annex_tail(text: str) -> tuple[str, list[dict]]:
    """Split the document at the first structural annex heading.

    Everything from that first annex heading to EOF is preserved as one raw attachment block and is
    deliberately not parsed. Later versions may opt into parsing/splitting individual annexes.
    """
    normalized = normalize_text(text)
    if not normalized:
        return "", []
    lines = normalized.splitlines()
    for idx, line in enumerate(lines):
        marker = recognize_line_marker(line, line_no=idx + 1)
        if marker is None or marker.element_type != "annex":
            continue
        if not is_structural_annex_marker(marker):
            continue
        main = "\n".join(lines[:idx]).strip()
        annex_text = "\n".join(lines[idx:]).strip()
        block_number = marker.number
        if not block_number:
            # Some real annex PDFs use a generic cover line `PHỤ LỤC` immediately followed by
            # `PHỤ LỤC I`. Keep one raw tail block, but expose the first concrete annex number as
            # metadata when it is adjacent to the generic heading.
            for lookahead in lines[idx + 1 : idx + 4]:
                nested = recognize_line_marker(lookahead, line_no=idx + 2)
                if nested is not None and nested.element_type == "annex" and nested.number and is_structural_annex_marker(nested):
                    block_number = nested.number
                    break
        block = AnnexBlock(
            index=1,
            number=block_number,
            heading=line.strip(),
            raw_text=annex_text,
            normalized_text=normalized_for_matching(annex_text),
            start_line=idx + 1,
            parsed=False,
        )
        return main, [block.to_dict()]
    return normalized, []
