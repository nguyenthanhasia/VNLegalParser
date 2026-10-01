from __future__ import annotations

import json
from pathlib import Path
import sys

from vietnamese_legal_parser import parse_structure


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def numbers(text: str, element_type: str) -> list[str]:
    return [n["number"] for n in walk(parse_structure(text)) if n["element_type"] == element_type]


def score_category(name: str, total: int, builder, checks) -> dict:
    passed = 0
    failures: list[int] = []
    for i in range(total):
        text = builder(i)
        ok = all(numbers(text, element_type) == expected for element_type, expected in checks(i).items())
        if ok:
            passed += 1
        elif len(failures) < 10:
            failures.append(i)
    return {"name": name, "passed": passed, "total": total, "rate": passed / total, "sample_failures": failures}


def main() -> None:
    n = 200
    cats = [
        score_category(
            "partial_clause_merge",
            n,
            lambda i: f"Điều 1. Phạm vi {i}\n1. Một. 2. Hai. 3. Ba.\nĐiều 2. Khác\n1. Bốn.",
            lambda _i: {"article": ["1", "2"], "clause": ["1", "2", "3", "1"]},
        ),
        score_category(
            "partial_point_merge",
            n,
            lambda i: f"Điều 1. Danh sách {i}\n1. Bao gồm: a) Điểm a; b) Điểm b; c) Điểm c.\n2. Kết thúc.",
            lambda _i: {"clause": ["1", "2"], "point": ["a", "b", "c"]},
        ),
        score_category(
            "mixed_major_boundary",
            n,
            lambda i: f"Lời dẫn {i}. Điều 1. Phạm vi 1. Một. 2. Hai.\nĐiều 2. Hiệu lực\n1. Có hiệu lực.",
            lambda _i: {"article": ["1", "2"], "clause": ["1", "2", "1"]},
        ),
        score_category(
            "isolated_dotted_letter",
            n,
            lambda i: f"Điều 1. Dữ liệu\n1. Nội dung.\na. Đây là ký hiệu biến a trong ví dụ {i}.\n2. Nội dung tiếp theo.",
            lambda _i: {"point": [], "clause": ["1", "2"]},
        ),
        score_category(
            "dotted_point_sequence",
            n,
            lambda i: f"Điều 1. Danh sách {i}\n1. Bao gồm:\na. Điểm a\nb. Điểm b\nc. Điểm c\n2. Kết thúc.",
            lambda _i: {"point": ["a", "b", "c"], "clause": ["1", "2"]},
        ),
        score_category(
            "legal_noun_reference",
            n,
            lambda i: f"Điều 1. Phạm vi\n1. Nội dung.\nĐiều {15+i} Luật số 01/2020/QH14 được áp dụng.\n2. Tiếp theo.",
            lambda _i: {"article": ["1"], "clause": ["1", "2"]},
        ),
        score_category(
            "neu_tren_reference",
            n,
            lambda i: f"Điều 1. Phạm vi\n1. Nội dung.\nĐiều {15+i} nêu trên tiếp tục được áp dụng.\n2. Tiếp theo.",
            lambda _i: {"article": ["1"], "clause": ["1", "2"]},
        ),
        score_category(
            "quote_close_then_clause",
            n,
            lambda i: (
                "Điều 3. Sửa đổi\n"
                "1. Bổ sung như sau:\n"
                f"“Điều 1a. Nội dung {i}\n1. Nội dung trong trích dẫn.”. 2. Bãi bỏ quy định cũ."
            ),
            lambda _i: {"article": ["3"], "clause": ["1", "2"]},
        ),
    ]
    passed = sum(c["passed"] for c in cats)
    total = sum(c["total"] for c in cats)
    print(json.dumps({"passed": passed, "total": total, "rate": passed / total, "categories": cats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
