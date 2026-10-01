from __future__ import annotations

import json

from vietnamese_legal_parser.cli import main


def test_cli_streams_jsonl_and_applies_confidence_gate(tmp_path):
    src = tmp_path / "in.jsonl"
    dst = tmp_path / "out.jsonl"
    rows = [
        {"document_id": "ok", "content": "Điều 1. Phạm vi\n1. Nội dung."},
        {"document_id": "empty", "content": ""},
    ]
    src.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

    code = main(["-i", str(src), "-o", str(dst), "--min-confidence", "0.8"])
    assert code == 2
    parsed = [json.loads(line) for line in dst.read_text(encoding="utf-8").splitlines()]
    assert [x["document"]["document_id"] for x in parsed] == ["ok", "empty"]
    assert parsed[0]["parser"]["confidence"] >= 0.8
    assert parsed[1]["parser"]["confidence"] == 0.0


def test_cli_rejects_bad_jsonl_without_leaving_partial_output(tmp_path):
    src = tmp_path / "bad.jsonl"
    dst = tmp_path / "out.jsonl"
    src.write_text('{"content":"Điều 1. A"}\nnot-json\n', encoding="utf-8")
    code = main(["-i", str(src), "-o", str(dst)])
    assert code == 1
    assert not dst.exists()
