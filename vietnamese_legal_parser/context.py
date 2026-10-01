from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata

from .sequence import starts_expected_sequence, transition
from .tokenizer import Marker, split_clause_number


@dataclass(slots=True)
class MarkerDecision:
    """Contextual classification result for one marker candidate.

    ``accepted`` decides whether the marker becomes hierarchy or remains text. ``score`` is a
    deterministic evidence score, not a calibrated probability. Keeping the score and reasons in
    one place makes ambiguous decisions auditable and benchmarkable.
    """

    accepted: bool
    score: float
    code: str | None = None
    severity: str = "info"
    reasons: list[str] = field(default_factory=list)


def _fold_ascii(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.replace("đ", "d").replace("Đ", "D").lower()


def has_explicit_keyword(marker: Marker) -> bool:
    folded = _fold_ascii(marker.marker).lstrip()
    if marker.element_type == "clause":
        return folded.startswith("khoan ")
    if marker.element_type == "point":
        return folded.startswith("diem ")
    return True


def marker_delimiter(marker: Marker) -> str:
    stripped = marker.marker.rstrip()
    return stripped[-1:] if stripped[-1:] in {".", ")", ":", "-"} else ""


def looks_like_numeric_payload(marker: Marker) -> bool:
    """Detect data rows, dates, decimals and money that resemble a bare clause number."""
    if marker.element_type != "clause" or has_explicit_keyword(marker):
        return False
    rest = marker.rest.lstrip()
    if len(marker.number) > 1 and marker.number.startswith("0"):
        return True
    if not rest:
        return False
    if rest.startswith(("|", "¦", "│", "┆", "┊")):
        return True
    # The clause regexp already consumed one period/parenthesis. An immediate numeric continuation
    # strongly signals a date, decimal, thousands group, version number or table value.
    if re.match(r"^\d+(?:[.,/%‰]|\b)", rest):
        return True
    # Common measurement/currency patterns where OCR inserts a space after the first numeric chunk.
    if re.match(r"^\d+\s*(?:%|‰|đồng|dong|triệu|trieu|tỷ|ty|USD|EUR|VND)\b", rest, re.I):
        return True
    return False


_REFERENCE_REST_RE = re.compile(
    r"(?ix)^\s*(?:"
    r"của|cua|thuộc|thuoc|tại|tai|đến|den|từ|tu|theo|"
    r"nêu\s+tại|neu\s+tai|nêu\s+trên|neu\s+tren|"
    r"quy\s+định\s+tại|quy\s+dinh\s+tai|được\s+quy\s+định\s+tại|duoc\s+quy\s+dinh\s+tai|"
    r"và\s+(?:Điều|Dieu|Chương|Chuong|Mục|Muc)|"
    r"(?:Bộ\s+luật|Bo\s+luat|Luật|Luat|Nghị\s+định|Nghi\s+dinh|Thông\s+tư|Thong\s+tu|"
    r"Nghị\s+quyết|Nghi\s+quyet|Quyết\s+định|Quyet\s+dinh|Phụ\s+lục|Phu\s+luc|văn\s+bản|van\s+ban)\b"
    r")"
)


def looks_like_structural_reference(marker: Marker) -> bool:
    """Detect a line-start legal citation instead of a structural heading.

    A real heading usually terminates its number with a punctuation delimiter (``Điều 5.``), while
    citation lines commonly continue directly with ``của Luật``, ``đến Điều``, ``Nghị định`` ... .
    """
    if marker.element_type not in {"part", "chapter", "section", "subsection", "division", "article"}:
        return False
    if marker_delimiter(marker) in {".", ":"}:
        return False
    return bool(_REFERENCE_REST_RE.match(marker.rest or ""))


def _point_sequence_evidence(
    marker: Marker,
    *,
    last_point: str | None,
    next_marker: Marker | None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if last_point is not None:
        relation = transition(last_point, marker.number, "point")
        if relation in {"next", "suffix_next"}:
            reasons.append(f"continues_point_sequence:{relation}")
            return True, reasons
    if next_marker is not None and next_marker.element_type == "point":
        relation = transition(marker.number, next_marker.number, "point")
        if relation in {"next", "suffix_next"}:
            reasons.append(f"starts_point_sequence:{relation}")
            return True, reasons
    return False, reasons


def classify_marker(
    marker: Marker,
    *,
    current_article_exists: bool,
    last_clause: str | None,
    last_point: str | None,
    next_marker: Marker | None = None,
) -> MarkerDecision:
    """Classify one marker candidate using lexical, sequence and neighboring-marker evidence."""

    if looks_like_structural_reference(marker):
        return MarkerDecision(
            False,
            0.05,
            code="structural_reference_kept_as_text",
            reasons=["reference_lexical_cue"],
        )

    if marker.element_type == "clause":
        if not current_article_exists:
            return MarkerDecision(False, 0.05, code="clause_without_article", reasons=["no_article_scope"])
        try:
            base, _suffix = split_clause_number(marker.number)
        except ValueError:
            return MarkerDecision(False, 0.0, code="invalid_clause_number", severity="warning")
        if base > 300:
            return MarkerDecision(False, 0.05, code="implausible_clause_number", reasons=["clause_number_gt_300"])
        if looks_like_numeric_payload(marker):
            return MarkerDecision(False, 0.02, code="numeric_data_not_clause", reasons=["numeric_payload_shape"])

        explicit = has_explicit_keyword(marker)
        if not explicit:
            if last_clause is None:
                if not starts_expected_sequence(marker.number, "clause"):
                    return MarkerDecision(
                        False,
                        0.20,
                        code="noninitial_bare_clause",
                        reasons=["bare_clause_does_not_start_at_1"],
                    )
            else:
                relation = transition(last_clause, marker.number, "clause")
                if relation not in {"next", "suffix_next"}:
                    return MarkerDecision(
                        False,
                        0.20,
                        code="nonsequential_bare_clause",
                        reasons=[f"clause_sequence:{relation}"],
                    )
        return MarkerDecision(
            True,
            0.98 if explicit else 0.93,
            reasons=["explicit_clause_keyword" if explicit else "valid_bare_clause_sequence"],
        )

    if marker.element_type == "point":
        if not current_article_exists:
            return MarkerDecision(False, 0.05, code="point_without_article", reasons=["no_article_scope"])
        explicit = has_explicit_keyword(marker)
        delim = marker_delimiter(marker)
        if explicit:
            return MarkerDecision(True, 0.99, reasons=["explicit_point_keyword"])
        if delim == ")":
            # Parenthesis is the canonical modern drafting form and is strong enough by itself.
            return MarkerDecision(True, 0.96, reasons=["canonical_point_parenthesis"])
        if delim == ".":
            sequence_ok, reasons = _point_sequence_evidence(
                marker,
                last_point=last_point,
                next_marker=next_marker,
            )
            if sequence_ok:
                return MarkerDecision(True, 0.88, reasons=reasons + ["ambiguous_dot_resolved_by_sequence"])
            return MarkerDecision(
                False,
                0.35,
                code="ambiguous_dotted_point",
                reasons=["isolated_bare_letter_dot"],
            )
        # Unknown delimiter: keep conservative behavior and require explicit evidence.
        return MarkerDecision(False, 0.30, code="ambiguous_point_marker", reasons=["weak_point_delimiter"])

    # Major headings use explicit Vietnamese structural keywords. Contextual reference filtering above
    # is the main precision guard; sequence anomalies remain diagnostics rather than hard rejection.
    return MarkerDecision(True, 0.98, reasons=["explicit_major_keyword"])
