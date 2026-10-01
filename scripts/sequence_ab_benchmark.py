from __future__ import annotations

import json
import os
import random
from pathlib import Path

from vietnamese_legal_parser import parse_document, parse_structure


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def nums(text: str, element_type: str):
    return [n["number"] for n in walk(parse_structure(text)) if n["element_type"] == element_type]


def score_false_positive_suite(n_each: int = 150):
    results = {}

    def run_cat(name, builder, element_type, expected):
        passed = 0
        for i in range(n_each):
            text = builder(i)
            got = nums(text, element_type)
            if got == expected(i) if callable(expected) else got == expected:
                passed += 1
        results[name] = {"passed": passed, "total": n_each, "rate": passed / n_each}

    run_cat("article_reference", lambda i: f"Điều 1. Phạm vi\n1. Nội dung.\nĐiều {15+i} của Luật số 01/2020/QH14 được áp dụng.\n2. Nội dung.", "article", ["1"])
    run_cat("chapter_reference", lambda i: f"Chương I\nĐiều 1. Phạm vi\n1. Nội dung.\nChương II của Luật số {i+1}/2020/QH14 được viện dẫn.", "chapter", ["I"])
    run_cat("section_reference", lambda i: f"Mục 1\nĐiều 1. Phạm vi\n1. Nội dung.\nMục {2+i} của Phụ lục I được viện dẫn.", "section", ["1"])
    run_cat("date", lambda i: f"Điều 1. Dữ liệu\n1. Nội dung.\n01.{(i%12)+1:02d}.2025 là ngày tham chiếu.\n2. Nội dung.", "clause", ["1", "2"])
    run_cat("decimal", lambda i: f"Điều 1. Dữ liệu\n1. Nội dung.\n3.{14+i%80:02d} là giá trị đo.\n2. Nội dung.", "clause", ["1", "2"])
    run_cat("money", lambda i: f"Điều 1. Dữ liệu\n1. Nội dung.\n2.000.{i:03d} đồng là mức chi.\n2. Nội dung.", "clause", ["1", "2"])
    run_cat("percent", lambda i: f"Điều 1. Dữ liệu\n1. Nội dung.\n5.{25+i%70:02d}% là tỷ lệ.\n2. Nội dung.", "clause", ["1", "2"])
    run_cat("tableish", lambda i: f"Điều 1. Danh mục\n1. Nội dung.\n1. | Hàng bảng {i} | Giá trị |\n2. Nội dung.", "clause", ["1", "2"])
    run_cat("year", lambda i: f"Điều 1. Hiệu lực\n1. Văn bản áp dụng trong năm {2020+i%20}.\n2. Nội dung.", "clause", ["1", "2"])
    run_cat("chuong_trinh", lambda i: f"Điều 1. Kế hoạch\n1. Chương trình công tác số {i}.\n2. Nội dung.", "chapter", [])
    run_cat("dieu_chinh", lambda i: f"Điều 1. Phạm vi\n1. Điều chỉnh mức số {i}.\n2. Nội dung.", "article", ["1"])
    run_cat("muc_tieu", lambda i: f"Điều 1. Phạm vi\n1. Mục tiêu thứ {i}.\n2. Nội dung.", "section", [])
    run_cat("diem_chuan", lambda i: f"Điều 1. Phạm vi\n1. Điểm chuẩn là {i}.\n2. Nội dung.", "point", [])
    run_cat("inline_refs", lambda i: f"Điều 1. Phạm vi\n1. Thực hiện theo khoản 1 Điều {5+i} của Luật liên quan.\n2. Nội dung.", "article", ["1"])
    run_cat("annex_reference", lambda i: f"Điều 1. Phạm vi\n1. Nội dung.\nPHỤ LỤC I ban hành kèm theo Thông tư số {i+1}/2025/TT-BCA được viện dẫn.\n2. Nội dung.", "annex", [])
    run_cat("letter_sentence", lambda i: f"Điều 1. Dữ liệu\n1. Nội dung.\na. Đây là ký hiệu biến a trong ví dụ số {i}, không phải điểm pháp lý.\n2. Nội dung.", "point", [])
    return results


def score_generated_grammar(total: int = 3000):
    rnd = random.Random(20261001)
    passed = 0
    roman = ["I", "II", "III", "IV", "V", "VI"]
    for _ in range(total):
        chapters = rnd.randint(1, 4)
        lines = []
        expected_chapters = []
        expected_articles = []
        expected_clauses = []
        article_no = 1
        for c in range(chapters):
            lines.append(f"Chương {roman[c]}")
            expected_chapters.append(roman[c])
            article_count = rnd.randint(1, 3)
            for _a in range(article_count):
                lines.append(f"Điều {article_no}. Điều kiểm thử {article_no}")
                expected_articles.append(str(article_no))
                clause_count = rnd.randint(1, 4)
                for k in range(1, clause_count + 1):
                    lines.append(f"{k}. Nội dung khoản {k}.")
                    expected_clauses.append(str(k))
                    if rnd.random() < 0.45:
                        lines.extend(["a) Điểm a.", "b) Điểm b.", "c) Điểm c.", "d) Điểm d."])
                article_no += 1
        text = "\n".join(lines)
        if nums(text, "chapter") == expected_chapters and nums(text, "article") == expected_articles and nums(text, "clause") == expected_clauses:
            passed += 1
    return {"passed": passed, "total": total, "rate": passed / total}


def score_source_fixtures(path: str):
    data = json.loads(Path(path).read_text())
    # Compare only cases whose expected primary-body semantics did not change in v0.5.
    data = [x for x in data if "annex_block" not in x.get("expect", {})]
    passed = 0
    failures = []
    for case in data:
        out = parse_document({"document_id": case["id"], "content": case["content"], "source_url": case.get("source_url", "")})
        got_by_type = {}
        for node in walk(out["structure"]):
            got_by_type.setdefault(node["element_type"], []).append(node["number"])
        ok = True
        for t in ["part", "chapter", "section", "subsection", "division", "annex", "article", "clause", "point"]:
            if t in case["expect"] and got_by_type.get(t, []) != case["expect"][t]:
                ok = False
        if ok:
            passed += 1
        else:
            failures.append(case["id"])
    return {"passed": passed, "total": len(data), "rate": passed / len(data), "failures": failures}


def main():
    false_pos = score_false_positive_suite()
    fp_pass = sum(v["passed"] for v in false_pos.values())
    fp_total = sum(v["total"] for v in false_pos.values())
    result = {
        "false_positive": {
            "passed": fp_pass,
            "total": fp_total,
            "rate": fp_pass / fp_total,
            "categories": false_pos,
        },
        "generated_legal_grammar": score_generated_grammar(),
    }
    fixture = os.environ.get("FIXTURE_PATH")
    if fixture:
        result["source_fixtures_unchanged_semantics"] = score_source_fixtures(fixture)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
