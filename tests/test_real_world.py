from __future__ import annotations

import json
from pathlib import Path

import pytest

from vietnamese_legal_parser import parse_document, parse_structure

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "real_world_cases.json").read_text(encoding="utf-8"))


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def numbers_by_type(nodes):
    result = {}
    for node in walk(nodes):
        result.setdefault(node["element_type"], []).append(node["number"])
    return result


@pytest.mark.parametrize("case", FIXTURES, ids=[x["id"] for x in FIXTURES])
def test_real_world_cases(case):
    out = parse_document({"document_id": case["id"], "content": case["content"], "source_url": case["source_url"]})
    nums = numbers_by_type(out["structure"])
    exp = case["expect"]
    for element_type in ["part", "chapter", "section", "subsection", "division", "annex", "article", "clause", "point"]:
        if element_type in exp:
            assert nums.get(element_type, []) == exp[element_type]
    if "annex_block" in exp:
        assert [b["number"] for b in out.get("annex_blocks", [])] == exp["annex_block"]
    for forbidden in exp.get("forbid_clause", []):
        assert forbidden not in nums.get("clause", [])
    for forbidden in exp.get("forbid_article", []):
        assert forbidden not in nums.get("article", [])
    if "min_cross_references" in exp:
        assert out["parser"]["stats"]["cross_reference_count"] >= exp["min_cross_references"]
    ids = [n["element_id"] for n in walk(out["structure"])]
    assert len(ids) == len(set(ids)), "element_id values must be unique"


def test_backward_compatible_parse_structure_returns_list():
    assert isinstance(parse_structure("Điều 1. Phạm vi"), list)


def test_diagnostics_mode():
    result = parse_structure("Điều 1. Phạm vi\n1. Nội dung", include_diagnostics=True)
    assert set(result) == {"structure", "annex_blocks", "diagnostics", "confidence", "stats"}
    assert 0 <= result["confidence"] <= 1


def test_quoted_multiline_markers_remain_content():
    text = """Điều 1. Sửa đổi\n1. Bổ sung như sau:\n“Điều 5a. Nội dung mới\n1. Khoản nằm trong nội dung trích dẫn\na) Điểm nằm trong nội dung trích dẫn.”.\n2. Nội dung tiếp theo."""
    out = parse_structure(text, include_diagnostics=True)
    nums = numbers_by_type(out["structure"])
    assert nums.get("article") == ["1"]
    assert nums.get("clause") == ["1", "2"]
    assert not nums.get("point")
    assert out["stats"]["embedded_marker_count"] >= 1


def test_reference_word_chuong_trinh_is_not_chapter():
    out = parse_structure("Điều 1. Điều chỉnh Chương trình công tác năm 2026\n1. Nội dung.")
    nums = numbers_by_type(out)
    assert nums.get("chapter", []) == []


def test_d_and_dd_have_distinct_ids():
    out = parse_structure("Điều 1. X\n1. Y\nd) D\nđ) DD")
    ids = [n["element_id"] for n in walk(out) if n["element_type"] == "point"]
    assert len(ids) == 2 and ids[0] != ids[1]
