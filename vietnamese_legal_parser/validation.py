from __future__ import annotations

from collections import Counter
import re
from typing import Iterable


def walk(nodes: Iterable[dict]):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def _numeric_prefix(value: object) -> int | None:
    """Return the leading Arabic number from a legal number such as 12, 12a or "thứ 12"."""
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def _validate_article_order(nodes: list[dict], warnings: list[dict], *, scope: str) -> None:
    """Validate article order within one structural scope.

    Annexes are independent legal containers, so their article numbering must not be compared with
    the primary body. Nested annexes are validated recursively as separate scopes.
    """
    last_article: int | None = None

    def visit(items: list[dict]) -> None:
        nonlocal last_article
        for node in items:
            node_type = node.get("element_type")
            if node_type == "annex":
                _validate_article_order(node.get("children", []), warnings, scope=node.get("element_id", "annex"))
                continue
            if node_type == "article":
                current = _numeric_prefix(node.get("number"))
                if current is not None:
                    # Allow immediately repeated base numbers such as 5, 5a, 5b. Warn only on a
                    # meaningful backward jump, which is a strong signal of OCR/reordering damage.
                    if last_article is not None and current + 1 < last_article:
                        warnings.append({
                            "code": "article_number_reversal",
                            "message": (
                                f"Article numbering in {scope} moves backward from {last_article} "
                                f"to {node.get('number')}; source may be reordered, quoted, or OCR-corrupted."
                            ),
                            "severity": "warning",
                        })
                    last_article = current
            visit(node.get("children", []))

    visit(nodes)


def validate_structure(nodes: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    all_nodes = list(walk(nodes))
    ids = [n.get("element_id", "") for n in all_nodes]
    for element_id, count in Counter(ids).items():
        if element_id and count > 1:
            warnings.append({
                "code": "duplicate_element_id",
                "message": f"Duplicate element_id: {element_id}",
                "severity": "error",
            })

    _validate_article_order(nodes, warnings, scope="primary body")
    return warnings


def confidence_score(
    warnings: list[dict],
    *,
    flattened_input: bool,
    embedded_markers: int,
    reconstructed_boundaries: int = 0,
) -> float:
    score = 1.0
    if flattened_input:
        score -= 0.08
    else:
        # Partial boundary reconstruction is lower-risk than whole-document flattening, but it still
        # means source layout was degraded. Keep the penalty small and capped.
        score -= min(0.06, reconstructed_boundaries * 0.005)
    score -= min(0.20, embedded_markers * 0.005)
    for warning in warnings:
        severity = warning.get("severity")
        if severity == "error":
            score -= 0.18
        elif severity == "warning":
            score -= 0.04
        else:
            # Informational diagnostics document conservative decisions and should not make a clean
            # parse look substantially unreliable.
            score -= 0.005
    return round(max(0.0, min(1.0, score)), 3)
