from vietnamese_legal_parser.normalization import html_to_text, normalize_text
from vietnamese_legal_parser.references import extract_cross_references


def test_html_preserves_block_boundaries():
    text = html_to_text("<h1>Chương I</h1><p>Điều 1. Test</p><p>1. Nội dung</p>")
    assert "Chương I" in text and "\n" in text


def test_unicode_nbsp_and_markdown_normalized():
    text = normalize_text("# Chương\u00a0I\r\n## Điều 1. Test")
    assert text == "Chương I\nĐiều 1. Test"


def test_cross_reference_longest_match_wins():
    refs = extract_cross_references("theo điểm b khoản 5 Điều 111 và khoản 1 Điều 15")
    assert len(refs) == 2
    assert refs[0]["target"] == {"point": "b", "clause": "5", "article": "111"}


def test_cross_reference_suffixes_and_historical_forms():
    refs = extract_cross_references("điểm a1 khoản 2a Điều 49 và Điều thứ 3")
    assert refs[0]["target"] == {"point": "a1", "clause": "2a", "article": "49"}
    assert refs[1]["target"] == {"article": "thứ 3"}


def test_html_table_row_numbers_do_not_become_legal_clauses():
    from vietnamese_legal_parser import parse_structure

    html = """<p>Điều 1. Danh mục</p>
    <table><tr><th>STT</th><th>Nội dung</th></tr><tr><td>1.</td><td>Dòng dữ liệu</td></tr><tr><td>a)</td><td>Mã dữ liệu</td></tr></table>
    <p>1. Khoản pháp lý thật.</p>"""
    out = parse_structure(html)
    clauses = [n["number"] for n in _walk(out) if n["element_type"] == "clause"]
    points = [n["number"] for n in _walk(out) if n["element_type"] == "point"]
    assert clauses == ["1"]
    assert points == []
    article = next(n for n in _walk(out) if n["element_type"] == "article")
    assert "[TABLE] 1. | Dòng dữ liệu" in article["content"]["raw_text"]


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.get("children", []))


def test_docx_ingestion_preserves_tables_without_promoting_row_numbers(tmp_path):
    pytest = __import__("pytest")
    docx = pytest.importorskip("docx")
    from vietnamese_legal_parser import parse_structure
    from vietnamese_legal_parser.ingest import read_text_file

    doc = docx.Document()
    doc.add_paragraph("Điều 1. Danh mục")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "STT"
    table.cell(0, 1).text = "Nội dung"
    table.cell(1, 0).text = "1."
    table.cell(1, 1).text = "Dữ liệu bảng"
    doc.add_paragraph("1. Khoản pháp lý thật.")
    path = tmp_path / "sample.docx"
    doc.save(path)

    extracted = read_text_file(path)
    assert "[TABLE] 1. | Dữ liệu bảng" in extracted
    out = parse_structure(extracted)
    clauses = [n["number"] for n in _walk(out) if n["element_type"] == "clause"]
    assert clauses == ["1"]
