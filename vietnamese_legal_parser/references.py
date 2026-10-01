from __future__ import annotations

import re

_ARTICLE = r"(?:\d+(?:[a-zđ])?|(?:thứ|thu)\s+(?:\d+|[a-zà-ỹ]+))"
_CLAUSE = r"\d+(?:[a-zđ])?"
_POINT = r"[a-zđ](?:\d+)?"
_KW_POINT = r"(?:điểm|diem)"
_KW_CLAUSE = r"(?:khoản|khoan)"
_KW_ARTICLE = r"(?:Điều|Dieu)"

_PATTERNS = [
    re.compile(rf"(?i)\b{_KW_POINT}\s+(?P<point>{_POINT})\s+{_KW_CLAUSE}\s+(?P<clause>{_CLAUSE})\s+{_KW_ARTICLE}\s+(?P<article>{_ARTICLE})\b"),
    re.compile(rf"(?i)\b{_KW_CLAUSE}\s+(?P<clause>{_CLAUSE})\s+{_KW_ARTICLE}\s+(?P<article>{_ARTICLE})\b"),
    re.compile(rf"(?i)\b{_KW_ARTICLE}\s+(?P<article>{_ARTICLE})\b"),
]


def extract_cross_references(text: str) -> list[dict]:
    """Extract intra-/inter-document structural references from Vietnamese legal prose.

    The function intentionally does not resolve a reference to a specific external document. It
    returns normalized structural coordinates that downstream indexing/resolution can use.
    """
    refs: list[dict] = []
    occupied: list[tuple[int, int]] = []
    for rx in _PATTERNS:
        for match in rx.finditer(text or ""):
            span = match.span()
            if any(not (span[1] <= a or span[0] >= b) for a, b in occupied):
                continue
            occupied.append(span)
            target = {
                k: v.lower() if k in {"article", "point", "clause"} else v
                for k, v in match.groupdict().items()
                if v
            }
            refs.append({
                "text": match.group(0),
                "target": target,
                "start": span[0],
                "end": span[1],
            })
    refs.sort(key=lambda x: x["start"])
    return refs
