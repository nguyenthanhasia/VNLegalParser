from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Vietnamese legal point order. Note that "đ" is a distinct legal letter after d.
VI_POINT_ORDER = (
    "a", "b", "c", "d", "đ", "e", "g", "h", "i", "k", "l", "m", "n", "o",
    "p", "q", "r", "s", "t", "u", "v", "x", "y",
)
POINT_RANK = {value: idx + 1 for idx, value in enumerate(VI_POINT_ORDER)}

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Common historical ordinal words used after "thứ". This is intentionally small and conservative;
# unknown words remain parseable markers but do not receive a sequence score.
_ORDINAL_WORDS = {
    "nhat": 1,
    "mot": 1,
    "hai": 2,
    "ba": 3,
    "tu": 4,
    "nam": 5,
    "sau": 6,
    "bay": 7,
    "tam": 8,
    "chin": 9,
    "muoi": 10,
}


@dataclass(frozen=True, slots=True)
class SequenceValue:
    base: int
    suffix: int = 0
    raw: str = ""


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.strip().lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.replace("đ", "d")


def roman_to_int(value: str) -> int | None:
    value = value.strip().upper()
    if not value or not re.fullmatch(r"[IVXLCDM]+", value):
        return None
    total = 0
    previous = 0
    for ch in reversed(value):
        current = _ROMAN_VALUES[ch]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    # Canonical round-trip guard blocks malformed strings such as IIX.
    def to_roman(number: int) -> str:
        pairs = (
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
        )
        out = []
        for n, token in pairs:
            while number >= n:
                out.append(token)
                number -= n
        return "".join(out)
    return total if 0 < total < 4000 and to_roman(total) == value else None


def legal_sequence_value(value: str, element_type: str) -> SequenceValue | None:
    """Map legal numbering to an ordinal value usable for transition scoring.

    Supports Arabic numbers, Arabic suffixes (2a/2b), Vietnamese point letters (a/b/.../đ),
    Roman numerals (I/II/III/IV), and common historical "thứ ..." forms.
    """
    raw = (value or "").strip().rstrip(".:)")
    if not raw:
        return None

    if element_type == "point":
        match = re.fullmatch(r"([a-zđ])(\d*)", raw.lower())
        if not match:
            return None
        rank = POINT_RANK.get(match.group(1))
        if rank is None:
            return None
        numeric_suffix = int(match.group(2)) if match.group(2) else 0
        return SequenceValue(rank, numeric_suffix, raw)

    if element_type in {"article", "clause"}:
        match = re.fullmatch(r"(\d{1,4})([a-zđ]?)", raw.lower())
        if not match:
            return None
        suffix = 0
        if match.group(2):
            suffix = POINT_RANK.get(match.group(2), 0)
            if not suffix:
                return None
        return SequenceValue(int(match.group(1)), suffix, raw)

    folded = _fold(raw)
    folded = re.sub(r"^(?:thu)\s+", "", folded).strip()
    if folded.isdigit():
        return SequenceValue(int(folded), 0, raw)
    roman = roman_to_int(raw)
    if roman is not None:
        return SequenceValue(roman, 0, raw)
    ordinal = _ORDINAL_WORDS.get(folded)
    if ordinal is not None:
        return SequenceValue(ordinal, 0, raw)
    # Lettered sections (Mục A, B, C...). Keep ASCII and Vietnamese Đ ordering conservative.
    if len(raw) == 1 and raw.lower() in POINT_RANK:
        return SequenceValue(POINT_RANK[raw.lower()], 0, raw)
    return None


def transition(previous: str | None, current: str, element_type: str) -> str:
    """Classify a numbering transition.

    Returns: first | next | suffix_next | same | jump | backward | unknown.
    The caller decides whether a non-next transition is merely diagnostic or a hard rejection.
    """
    cur = legal_sequence_value(current, element_type)
    if cur is None:
        return "unknown"
    if previous is None:
        return "first"
    prev = legal_sequence_value(previous, element_type)
    if prev is None:
        return "unknown"
    if cur.base == prev.base:
        if cur.suffix == prev.suffix:
            return "same"
        if cur.suffix == prev.suffix + 1 and cur.suffix > 0:
            return "suffix_next"
        return "backward" if cur.suffix < prev.suffix else "jump"
    if cur.base == prev.base + 1 and cur.suffix == 0:
        return "next"
    return "backward" if cur.base < prev.base else "jump"


def starts_expected_sequence(value: str, element_type: str) -> bool:
    cur = legal_sequence_value(value, element_type)
    if cur is None:
        return False
    if element_type == "point":
        return cur.base == 1 and cur.suffix == 0  # a
    return cur.base == 1 and cur.suffix == 0
