from __future__ import annotations

from copy import deepcopy
import hashlib
import re
import unicodedata
from typing import Any

from .normalization import normalize_text, normalized_for_matching
from .annex import split_annex_tail
from .references import extract_cross_references
from .tokenizer import Marker, tokenize
from .context import classify_marker
from .sequence import transition
from .validation import confidence_score, validate_structure

__version__ = "0.6.0"

LEVELS = {
    "part": 0,
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "division": 4,
    "article": 5,
    "clause": 6,
    "point": 7,
}

# Annexes are independent top-level containers and can contain their own chapters/articles.
HEADING_TYPES = {"part", "chapter", "section", "subsection", "division", "annex"}
TITLE_PENDING_TYPES = HEADING_TYPES | {"article"}


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("đ", "dd").replace("Đ", "DD")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return value or "x"


def _new_node(marker: Marker, element_id: str) -> dict:
    rest = marker.rest.strip()
    if marker.element_type in {"clause", "point"}:
        title = f"{'Khoản' if marker.element_type == 'clause' else 'Điểm'} {marker.number}"
        raw_text = rest
    else:
        title = rest
        raw_text = ""
    return {
        "element_id": element_id,
        "element_type": marker.element_type,
        "number": marker.number,
        "title": title,
        "content": {
            "raw_text": raw_text,
            "normalized_text": normalized_for_matching(raw_text),
            "provisions": [],
        },
        "children": [],
        "cross_references": [],
        "metadata": {
            "marker": marker.marker,
            "raw_number": marker.raw_number or marker.number,
            "line_no": marker.line_no,
            "source": marker.source,
            "embedded": False,
        },
    }


def _new_preamble() -> dict:
    return {
        "element_id": "preamble",
        "element_type": "preamble",
        "number": "",
        "title": "Preamble",
        "content": {"raw_text": "", "normalized_text": "", "provisions": []},
        "children": [],
        "cross_references": [],
        "metadata": {},
    }


def _append_content(node: dict, text: str) -> None:
    text = text.strip()
    if not text:
        return
    raw = node["content"]["raw_text"]
    node["content"]["raw_text"] = f"{raw}\n{text}".strip() if raw else text
    node["content"]["normalized_text"] = normalized_for_matching(node["content"]["raw_text"])


def _heading_like(text: str) -> bool:
    """Detect likely next-line titles for Phần/Chương/Mục/Tiểu mục.

    Uppercase is strong evidence in official formatting. We also accept short title-case lines without
    sentence punctuation for PDF text extractors that lose font/case information.
    """
    value = text.strip().strip("_-")
    if not value or len(value) > 180:
        return False
    letters = [c for c in value if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    if upper_ratio >= 0.80:
        return True
    return len(value.split()) <= 12 and not re.search(r"[.!?;:]$", value)


def _path_id(parent: dict | None, marker: Marker, path_counts: dict[tuple[str, str], int]) -> str:
    """Allocate a path-stable ID and guarantee uniqueness even for malformed duplicate numbering."""
    base = f"{marker.element_type}-{_slug(marker.number or 'x')}"
    parent_id = parent.get("element_id") if parent and parent.get("element_type") != "preamble" else "__root__"
    key = (str(parent_id), base)
    count = path_counts.get(key, 0) + 1
    path_counts[key] = count
    local = base if count == 1 else f"{base}-{count}"
    if parent_id != "__root__":
        return f"{parent_id}/{local}"
    return local


def _parent_for(marker: Marker, active: dict[int, dict], annex: dict | None) -> dict | None:
    if marker.element_type == "annex":
        return None
    level = LEVELS[marker.element_type]
    if annex is not None:
        # Inside an annex, attach to nearest lower level in the annex; otherwise to annex itself.
        for candidate in range(level - 1, -1, -1):
            if candidate in active:
                return active[candidate]
        return annex
    for candidate in range(level - 1, -1, -1):
        if candidate in active:
            return active[candidate]
    return None


def parse_structure(text: str, *, include_diagnostics: bool = False) -> list[dict] | dict:
    """Parse Vietnamese legal text into a hierarchical tree.

    The default return type remains a list for backward compatibility. Set include_diagnostics=True
    to receive {structure, diagnostics, confidence, stats}.
    """
    normalized = normalize_text(text)
    if not normalized:
        diagnostics = [{
            "code": "empty_input",
            "message": "Input contains no parseable text.",
            "severity": "error",
        }]
        result = {
            "structure": [],
            "annex_blocks": [],
            "diagnostics": diagnostics,
            "confidence": 0.0,
            "stats": {
                "raw_character_count": len(text or ""),
                "normalized_character_count": 0,
                "logical_line_count": 0,
                "flattened_input": False,
                "reconstructed_boundary_count": 0,
                "reconstructed_physical_line_count": 0,
                "node_count": 0,
                "element_counts": {},
                "embedded_marker_count": 0,
                "cross_reference_count": 0,
            },
        }
        return result if include_diagnostics else []

    main_text, annex_blocks = split_annex_tail(normalized)
    segments, token_stats = tokenize(main_text)
    roots: list[dict] = []
    preamble = _new_preamble()
    roots.append(preamble)
    current: dict = preamble
    active: dict[int, dict] = {}
    current_annex: dict | None = None
    path_counts: dict[tuple[str, str], int] = {}
    diagnostics: list[dict] = []
    embedded_markers = 0
    last_clause: str | None = None
    last_point: str | None = None
    current_article: dict | None = None
    pending_heading: dict | None = None
    last_major_by_scope: dict[tuple[str, str], str] = {}

    # Precompute the next marker candidate for contextual look-ahead without O(n^2) scanning.
    next_markers: list[Marker | None] = [None] * len(segments)
    upcoming: Marker | None = None
    for idx in range(len(segments) - 1, -1, -1):
        next_markers[idx] = upcoming
        if segments[idx].marker is not None:
            upcoming = segments[idx].marker

    for segment_index, segment in enumerate(segments):
        marker = segment.marker
        if marker is None:
            if pending_heading is not None and not pending_heading.get("title") and _heading_like(segment.text):
                pending_heading["title"] = segment.text.strip()
                pending_heading = None
                continue
            pending_heading = None
            _append_content(current, segment.text)
            continue

        # Markers that open inside quotes are amendment/consolidation payload, not primary structure.
        # Preserve them verbatim in the current node and surface a diagnostic.
        if marker.inside_quote:
            embedded_markers += 1
            _append_content(current, segment.text)
            diagnostics.append({
                "code": "embedded_quoted_marker",
                "message": f"Kept quoted {marker.element_type} marker as content: {marker.marker}",
                "severity": "info",
                "line_no": marker.line_no,
            })
            continue

        decision = classify_marker(
            marker,
            current_article_exists=current_article is not None,
            last_clause=last_clause,
            last_point=last_point,
            next_marker=next_markers[segment_index],
        )
        if not decision.accepted:
            _append_content(current, segment.text)
            severity = decision.severity
            if marker.source in {"inline_fallback", "boundary_reconstruction"} and severity == "info":
                severity = "warning"
            diagnostics.append({
                "code": decision.code or "context_rejected_marker",
                "message": f"Rejected ambiguous marker and kept it as text: {marker.marker}",
                "severity": severity,
                "line_no": marker.line_no,
                "evidence_score": decision.score,
                "reasons": decision.reasons,
            })
            continue

        if marker.element_type == "annex":
            # Structural annexes should already have been split before tokenization. Any annex marker
            # that remains in the primary body is therefore treated conservatively as content.
            _append_content(current, segment.text)
            diagnostics.append({
                "code": "annex_reference_kept_as_text",
                "message": f"Kept in-body annex reference as content: {marker.marker}",
                "severity": "info",
                "line_no": marker.line_no,
            })
            continue

        level = LEVELS[marker.element_type]
        parent = _parent_for(marker, active, current_annex)

        if marker.element_type in {"part", "chapter", "section", "subsection", "division", "article"}:
            scope = parent["element_id"] if parent is not None else "__root__"
            key = (marker.element_type, scope)
            previous_number = last_major_by_scope.get(key)
            relation = transition(previous_number, marker.number, marker.element_type)
            if previous_number is not None and relation in {"same", "jump", "backward"}:
                diagnostics.append({
                    "code": f"{marker.element_type}_sequence_{relation}",
                    "message": (
                        f"{marker.element_type} numbering in scope {scope} moves from "
                        f"{previous_number} to {marker.number} ({relation})."
                    ),
                    "severity": "info" if relation == "jump" else "warning",
                    "line_no": marker.line_no,
                })
            last_major_by_scope[key] = marker.number

        if marker.element_type == "point" and last_point is not None:
            point_relation = transition(last_point, marker.number, "point")
            if point_relation in {"same", "jump", "backward"}:
                diagnostics.append({
                    "code": f"point_sequence_{point_relation}",
                    "message": f"Point numbering moves from {last_point} to {marker.number} ({point_relation}).",
                    "severity": "info",
                    "line_no": marker.line_no,
                })

        node = _new_node(marker, _path_id(parent, marker, path_counts))
        node["metadata"]["context_score"] = decision.score
        node["metadata"]["context_reasons"] = decision.reasons
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
        current = node
        active[level] = node
        for deeper in [k for k in active if k > level]:
            del active[deeper]

        if marker.element_type in {"part", "chapter", "section", "subsection", "division"}:
            current_article = None
            last_clause = None
            last_point = None
        elif marker.element_type == "article":
            current_article = node
            last_clause = None
            last_point = None
        elif marker.element_type == "clause":
            last_clause = marker.number
            last_point = None
        elif marker.element_type == "point":
            last_point = marker.number

        pending_heading = node if marker.element_type in TITLE_PENDING_TYPES and not node["title"] else None

    if not preamble["content"]["raw_text"] and not preamble["children"]:
        roots.remove(preamble)

    # Cross-references are computed after tree construction so node content is stable.
    def enrich(nodes: list[dict]) -> int:
        count = 0
        for node in nodes:
            ref_text = " ".join(part for part in [node.get("title", ""), node["content"]["normalized_text"]] if part)
            refs = extract_cross_references(ref_text)
            node["cross_references"] = refs
            count += len(refs)
            count += enrich(node["children"])
        return count

    cross_ref_count = enrich(roots)
    diagnostics.extend(validate_structure(roots))
    if not any(node.get("element_type") != "preamble" for node in roots):
        if annex_blocks:
            diagnostics.append({
                "code": "annex_tail_extracted",
                "message": "No primary-body markers were parsed because the document begins with an annex block.",
                "severity": "info",
            })
        else:
            diagnostics.append({
                "code": "no_structural_markers",
                "message": "No legal structural markers were recognized; text was preserved as preamble content.",
                "severity": "warning",
            })
    conf = confidence_score(
        diagnostics,
        flattened_input=token_stats["flattened_input"],
        embedded_markers=embedded_markers,
        reconstructed_boundaries=token_stats.get("reconstructed_boundary_count", 0),
    )

    node_count = 0
    type_counts: dict[str, int] = {}

    def count(nodes: list[dict]) -> None:
        nonlocal node_count
        for node in nodes:
            node_count += 1
            t = node["element_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
            count(node["children"])

    count(roots)
    result = {
        "structure": roots,
        "annex_blocks": annex_blocks,
        "diagnostics": diagnostics,
        "confidence": conf,
        "stats": {
            **token_stats,
            "raw_character_count": len(text),
            "normalized_character_count": len(normalized),
            "main_body_character_count": len(main_text),
            "annex_character_count": sum(len(block["raw_text"]) for block in annex_blocks),
            "annex_block_count": len(annex_blocks),
            "node_count": node_count,
            "element_counts": type_counts,
            "embedded_marker_count": embedded_markers,
            "cross_reference_count": cross_ref_count,
        },
    }
    return result if include_diagnostics else roots


def _first(record: dict[str, Any], *keys: str, default=None):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _date(record: dict[str, Any], *keys: str):
    value = _first(record, *keys)
    return str(value) if value not in (None, "") else None


def parse_document(record: dict[str, Any]) -> dict:
    """Parse a record into a stable document schema while preserving source metadata."""
    parsed = parse_structure(str(record.get("content", "")), include_diagnostics=True)
    doc_id = str(_first(record, "document_id", "id", "doc_id", default=""))
    source_url = _first(record, "source_url", "url", "source", default="")
    if source_url in {"main", "legacy"}:
        source_url = ""

    output = {
        "document": {
            "document_id": doc_id,
            "title": str(_first(record, "title", "name", default="")),
            "document_type": str(_first(record, "document_type", "type", "doc_type", default="")),
            "document_number": str(_first(record, "doc_number", "document_number", "number", default="")),
            "jurisdiction": str(record.get("jurisdiction") or "Vietnam"),
            "language": str(record.get("language") or "vi"),
            "issuing_authority": str(_first(record, "issuer", "issuing_authority", "authority", default="")),
            "status": str(_first(record, "effect_status", "status", default="")),
            "dates": {
                "enactment": _date(record, "enactment_date", "issue_date", "promulgation_date", "date", "year"),
                "effective": _date(record, "effective_date", "date_effective"),
                "expiry": _date(record, "expiry_date", "expiration_date", "date_expiry"),
                "last_amended": _date(record, "last_amended", "amended_date"),
                "consolidation": _date(record, "consolidation_date"),
            },
            "classification": {
                "domain": str(_first(record, "sector", "domain", default="")),
                "sub_domain": str(_first(record, "legal_field", "sub_domain", default="")),
                "keywords": deepcopy(record.get("keywords") or []),
                "subject_areas": deepcopy(record.get("subject_areas") or []),
                "classification_codes": [str(_first(record, "doc_number", "document_number", default=""))] if _first(record, "doc_number", "document_number") else [],
            },
            "source_url": str(source_url or ""),
            "version_history": deepcopy(record.get("version_history") or []),
            "related_documents": deepcopy(record.get("related_documents") or []),
            "source_metadata": {k: deepcopy(v) for k, v in record.items() if k != "content"},
        },
        "structure": parsed["structure"],
        "annex_blocks": parsed.get("annex_blocks", []),
        "cross_references": [],
        "parser": {
            "name": "vietnamese-legal-parser",
            "version": __version__,
            "source_content_sha256": hashlib.sha256(str(record.get("content", "")).encode("utf-8")).hexdigest(),
            "confidence": parsed["confidence"],
            "diagnostics": parsed["diagnostics"],
            "stats": parsed["stats"],
        },
    }
    # Aggregate node-level references for convenient indexing.
    aggregated: list[dict] = []

    def collect(nodes: list[dict]) -> None:
        for node in nodes:
            for ref in node.get("cross_references", []):
                aggregated.append({"source_element_id": node["element_id"], **ref})
            collect(node.get("children", []))

    collect(output["structure"])
    output["cross_references"] = aggregated
    return output
