from __future__ import annotations

import json
import random
import string
import sys

from vietnamese_legal_parser import parse_structure


TOKENS = [
    "Điều", "Khoản", "Điểm", "Chương", "Mục", "Tiểu mục", "Phụ lục", "Luật", "Nghị định",
    "a)", "b)", "đ)", "a.", "1.", "2.", "2026.", "3.14", "01.07.2025", "2.000.000",
    "“", "”", '"', ":", ";", ".", "-", "|", "nội dung", "quy định", "của Luật", "nêu trên",
]
SPACES = [" ", "  ", "\t", "\u00a0", "\u2009"]


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def build_case(rnd: random.Random) -> str:
    line_count = rnd.randint(1, 35)
    lines = []
    for _ in range(line_count):
        pieces = []
        for _ in range(rnd.randint(1, 14)):
            if rnd.random() < 0.75:
                pieces.append(rnd.choice(TOKENS))
            else:
                pieces.append("".join(rnd.choice(string.ascii_letters + string.digits) for _ in range(rnd.randint(1, 10))))
        lines.append(rnd.choice(SPACES).join(pieces))
    if rnd.random() < 0.25:
        return " ".join(lines)
    return rnd.choice(["\n", "\r\n"] ).join(lines)


def main() -> None:
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    rnd = random.Random(20261001)
    failure_count = 0
    failure_samples = []
    for i in range(total):
        text = build_case(rnd)
        failure = None
        try:
            result = parse_structure(text, include_diagnostics=True)
            ids = [n["element_id"] for n in walk(result["structure"])]
            if len(ids) != len(set(ids)):
                failure = {"index": i, "reason": "duplicate_element_id"}
        except Exception as exc:  # noqa: BLE001 - fuzz harness intentionally catches everything
            failure = {"index": i, "reason": type(exc).__name__, "message": str(exc)[:200]}
        if failure is not None:
            failure_count += 1
            if len(failure_samples) < 20:
                failure_samples.append(failure)
    passed = total - failure_count
    print(json.dumps({"passed": passed, "total": total, "rate": passed/total, "failure_count": failure_count, "failures": failure_samples}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
