from __future__ import annotations

import json
import time

from vietnamese_legal_parser import parse_structure


def build_document(article_count: int = 2000) -> str:
    lines = ["Chương I", "QUY ĐỊNH STRESS TEST"]
    for article in range(1, article_count + 1):
        lines.append(f"Điều {article}. Điều kiểm thử {article}")
        for clause in range(1, 4):
            lines.append(f"{clause}. Nội dung khoản {clause} của điều {article}.")
            lines.append("a) Nội dung điểm a.")
            lines.append("b) Nội dung điểm b.")
    return "\n".join(lines)


def main() -> None:
    text = build_document()
    started = time.perf_counter()
    result = parse_structure(text, include_diagnostics=True)
    elapsed = time.perf_counter() - started
    print(json.dumps({
        "characters": len(text),
        "nodes": result["stats"]["node_count"],
        "articles": result["stats"]["element_counts"].get("article", 0),
        "confidence": result["confidence"],
        "diagnostics": len(result["diagnostics"]),
        "elapsed_seconds": round(elapsed, 4),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
