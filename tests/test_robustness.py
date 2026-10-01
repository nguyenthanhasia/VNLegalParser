from __future__ import annotations

import random
import re

from vietnamese_legal_parser import parse_structure


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def nums(text, element_type):
    out = parse_structure(text)
    return [n["number"] for n in walk(out) if n["element_type"] == element_type]


def test_adversarial_years_decimals_dates_are_not_clauses():
    text = """Điều 1. Dữ liệu số
1. Văn bản có hiệu lực năm 2023. Giá trị là 1.000.000 đồng, tỷ lệ 3.14 và ngày 01.07.2025.
2. Nội dung thứ hai."""
    assert nums(text, "clause") == ["1", "2"]


def test_references_at_line_start_do_not_create_chapter_from_chuong_trinh():
    text = """Điều 1. Kế hoạch
1. Chương trình công tác năm 2026 được ban hành.
2. Thực hiện theo Chương II của văn bản khác."""
    assert nums(text, "chapter") == []


def test_flattened_references_do_not_become_articles():
    text = (
        "QUYẾT ĐỊNH: Điều 1. Phạm vi 1. Thực hiện theo Điều 15 đến Điều 21a Nghị định số 99/2020/NĐ-CP; "
        "khoản 1 Điều 5 của Luật liên quan. 2. Nội dung tiếp theo. Điều 2. Hiệu lực 1. Quyết định có hiệu lực từ ngày ký."
    )
    assert nums(text, "article") == ["1", "2"]
    assert nums(text, "clause") == ["1", "2", "1"]


def test_clause_and_point_content_is_content_not_title():
    out = parse_structure("Điều 1. Phạm vi\n1. Nội dung khoản\na) Nội dung điểm")
    nodes = list(walk(out))
    clause = next(n for n in nodes if n["element_type"] == "clause")
    point = next(n for n in nodes if n["element_type"] == "point")
    assert clause["title"] == "Khoản 1"
    assert clause["content"]["normalized_text"] == "Nội dung khoản"
    assert point["title"] == "Điểm a"
    assert point["content"]["normalized_text"] == "Nội dung điểm"


def test_common_whitespace_mutations_keep_structure():
    base = """Chương I
QUY ĐỊNH CHUNG
Mục 1
PHẠM VI
Tiểu mục 1
NGUYÊN TẮC
Điều 1. Phạm vi điều chỉnh
1. Nội dung thứ nhất.
a) Điểm a;
b) Điểm b;
đ) Điểm đ.
2. Nội dung thứ hai.
Điều 2. Hiệu lực
1. Có hiệu lực từ ngày ký."""
    expected_articles = ["1", "2"]
    expected_clauses = ["1", "2", "1"]

    variants = [
        base,
        base.replace("\n", "\r\n"),
        base.replace(" ", "\u00a0"),
        "\n\n".join(base.splitlines()),
        "\n".join("   " + line + "   " for line in base.splitlines()),
        "\n".join(("# " + line) if re.match(r"^(Chương|Mục|Tiểu mục|Điều)", line) else line for line in base.splitlines()),
    ]
    for value in variants:
        assert nums(value, "article") == expected_articles
        assert nums(value, "clause") == expected_clauses


def test_deterministic_noise_fuzz_500_variants():
    base_lines = [
        "Chương I",
        "QUY ĐỊNH CHUNG",
        "Điều 1. Phạm vi",
        "1. Nội dung một.",
        "a) Điểm a.",
        "b) Điểm b.",
        "2. Nội dung hai.",
        "Điều 2. Hiệu lực",
        "1. Có hiệu lực năm 2026.",
    ]
    rnd = random.Random(20261001)
    for _ in range(500):
        lines = []
        for line in base_lines:
            lead = " " * rnd.randint(0, 3)
            tail = " " * rnd.randint(0, 3)
            line = lead + line + tail
            if rnd.random() < 0.15:
                line = line.replace(" ", "\u00a0")
            lines.append(line)
            if rnd.random() < 0.20:
                lines.append("")
        sep = "\r\n" if rnd.random() < 0.5 else "\n"
        text = sep.join(lines)
        assert nums(text, "article") == ["1", "2"]
        assert nums(text, "clause") == ["1", "2", "1"]
        assert nums(text, "point") == ["a", "b"]


def test_clause_suffix_and_point_suffix_numbering():
    text = """Điều 49. Thủ tục
1. Nội dung một.
2. Nội dung hai.
2a. Nội dung được bổ sung.
3. Nội dung ba.
Điều 52. Trình tự
1. Danh sách gồm:
a) Điểm a;
a1) Điểm a1 được bổ sung;
b) Điểm b."""
    assert nums(text, "clause") == ["1", "2", "2a", "3", "1"]
    assert nums(text, "point") == ["a", "a1", "b"]


def test_flattened_clause_suffix_sequence():
    text = (
        "QUYẾT ĐỊNH: Điều 49. Thủ tục 1. Nội dung một. 2. Nội dung hai. "
        "2a. Nội dung bổ sung. 3. Nội dung ba. Điều 50. Hiệu lực 1. Có hiệu lực."
    )
    assert nums(text, "article") == ["49", "50"]
    assert nums(text, "clause") == ["1", "2", "2a", "3", "1"]


def test_article_title_can_be_on_next_line():
    out = parse_structure("Điều 10.\nPHẠM VI ÁP DỤNG\n1. Nội dung")
    article = next(n for n in walk(out) if n["element_type"] == "article")
    assert article["title"] == "PHẠM VI ÁP DỤNG"
    assert article["content"]["normalized_text"] == ""


def test_empty_clause_marker_can_take_next_line_content():
    out = parse_structure("Điều 1. Phạm vi\n1.\nNội dung của khoản một.")
    clause = next(n for n in walk(out) if n["element_type"] == "clause")
    assert clause["content"]["normalized_text"] == "Nội dung của khoản một."


def test_uppercase_annex_reference_inside_article_is_not_structural():
    text = """Điều 1. Phạm vi
1. Nội dung áp dụng theo tài liệu sau:
PHỤ LỤC I ban hành kèm theo Thông tư này được sử dụng để đối chiếu.
2. Nội dung tiếp theo."""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "annex") == []
    assert nums(text, "clause") == ["1", "2"]
    assert any(d["code"] == "annex_reference_kept_as_text" for d in out["diagnostics"])


def test_annex_tail_is_split_before_primary_parse():
    text = """Điều 98. Điều cuối của phần chính
1. Nội dung.
PHỤ LỤC I
DANH MỤC
Điều 1. Quy định trong phụ lục
1. Nội dung.
Điều 2. Quy định tiếp theo
1. Nội dung."""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "annex") == []
    assert nums(text, "article") == ["98"]
    assert len(out["annex_blocks"]) == 1
    assert out["annex_blocks"][0]["number"] == "I"
    assert "Điều 1. Quy định trong phụ lục" in out["annex_blocks"][0]["raw_text"]
    assert out["annex_blocks"][0]["parsed"] is False


def test_generic_annex_then_numbered_annex_is_one_raw_block():
    text = """Điều 1. Hiệu lực
1. Có hiệu lực từ ngày ký.
PHỤ LỤC
PHỤ LỤC I
DANH MỤC
1. | Dòng bảng |"""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "article") == ["1"]
    assert nums(text, "annex") == []
    assert len(out["annex_blocks"]) == 1
    assert out["annex_blocks"][0]["number"] == "I"
    assert "PHỤ LỤC I" in out["annex_blocks"][0]["raw_text"]


def test_sequence_rejects_numeric_data_and_line_start_references():
    text = """Chương I
QUY ĐỊNH CHUNG
Điều 1. Dữ liệu
1. Nội dung.
3.14 là giá trị đo.
01.07.2025 là ngày tham chiếu.
2.000.000 đồng là mức chi.
1. | Hàng bảng |
2. Nội dung tiếp theo.
Điều 15 của Luật số 01/2020/QH14 được áp dụng.
Chương II của Luật khác được viện dẫn.
Mục 1 của Phụ lục I được viện dẫn."""
    assert nums(text, "article") == ["1"]
    assert nums(text, "chapter") == ["I"]
    assert nums(text, "section") == []
    assert nums(text, "clause") == ["1", "2"]


def test_sequence_supports_arabic_point_and_roman_orders_without_hard_rejecting_excerpt_gaps():
    text = """Chương I
Điều 1. Một
1. A
a) A
b) B
c) C
d) D
đ) DD
2. B
Chương II
Điều 2. Hai
1. X
Chương III
Điều 3. Ba
1. Y
Chương IV
Điều 4. Bốn
1. Z"""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "chapter") == ["I", "II", "III", "IV"]
    assert nums(text, "clause") == ["1", "2", "1", "1", "1"]
    assert nums(text, "point") == ["a", "b", "c", "d", "đ"]
    assert not any(d["code"].startswith("chapter_sequence_") for d in out["diagnostics"])

    excerpt = parse_structure("Điều 9. Trích đoạn\n1. Nội dung\nd) Điểm d\nđ) Điểm đ")
    assert [n["number"] for n in walk(excerpt) if n["element_type"] == "point"] == ["d", "đ"]


def test_empty_input_is_not_high_confidence():
    out = parse_structure("   \n\t", include_diagnostics=True)
    assert out["structure"] == []
    assert out["confidence"] == 0.0
    assert out["diagnostics"][0]["code"] == "empty_input"


def test_unstructured_text_is_preserved_but_flagged():
    out = parse_structure("Đây là đoạn văn không chứa marker cấu trúc pháp lý.", include_diagnostics=True)
    assert out["structure"][0]["element_type"] == "preamble"
    assert any(d["code"] == "no_structural_markers" for d in out["diagnostics"])
    assert out["confidence"] < 1.0


def test_v060_partial_line_loss_recovers_clause_boundaries():
    text = """Điều 1. Phạm vi
1. Một. 2. Hai. 3. Ba.
Điều 2. Khác
1. Bốn."""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "article") == ["1", "2"]
    assert nums(text, "clause") == ["1", "2", "3", "1"]
    assert out["stats"]["reconstructed_boundary_count"] >= 2
    assert out["stats"]["reconstructed_physical_line_count"] >= 1


def test_v060_partial_line_loss_recovers_inline_point_sequence():
    text = """Điều 1. Danh sách
1. Bao gồm: a) Điểm a; b) Điểm b; c) Điểm c.
2. Nội dung tiếp theo."""
    assert nums(text, "clause") == ["1", "2"]
    assert nums(text, "point") == ["a", "b", "c"]


def test_v060_mixed_major_boundary_recovery_without_flattening_whole_document():
    text = """Lời dẫn. Điều 1. Phạm vi 1. Một. 2. Hai.
Điều 2. Hiệu lực
1. Có hiệu lực."""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "article") == ["1", "2"]
    assert nums(text, "clause") == ["1", "2", "1"]
    assert out["stats"]["flattened_input"] is False
    assert out["stats"]["reconstructed_boundary_count"] >= 3


def test_v060_isolated_dotted_letter_is_not_promoted_without_sequence_evidence():
    text = """Điều 1. Dữ liệu
1. Nội dung.
a. Đây là ký hiệu biến a, không phải điểm pháp lý.
2. Nội dung tiếp theo."""
    out = parse_structure(text, include_diagnostics=True)
    assert nums(text, "point") == []
    assert any(d["code"] == "ambiguous_dotted_point" for d in out["diagnostics"])


def test_v060_dotted_point_sequence_is_kept_when_neighbors_confirm_it():
    text = """Điều 1. Danh sách
1. Bao gồm:
a. Điểm a
b. Điểm b
c. Điểm c
2. Kết thúc."""
    assert nums(text, "point") == ["a", "b", "c"]


def test_v060_legal_noun_and_neu_tren_reference_variants_are_not_articles():
    variants = [
        "Điều 15 Luật số 01/2020/QH14 được áp dụng.",
        "Điều 15 nêu trên tiếp tục được áp dụng.",
        "Điều 15 Nghị định số 99/2020/NĐ-CP được viện dẫn.",
    ]
    for ref in variants:
        text = f"Điều 1. Phạm vi\n1. Nội dung.\n{ref}\n2. Nội dung tiếp theo."
        assert nums(text, "article") == ["1"]
        assert nums(text, "clause") == ["1", "2"]


def test_duplicate_numbering_never_produces_duplicate_element_ids():
    text = """Điều 1. Dữ liệu lỗi
1. Khoản đầu.
1. Khoản lặp.
a) Điểm đầu.
a) Điểm lặp."""
    out = parse_structure(text, include_diagnostics=True)
    ids = [n["element_id"] for n in walk(out["structure"])]
    assert len(ids) == len(set(ids))
