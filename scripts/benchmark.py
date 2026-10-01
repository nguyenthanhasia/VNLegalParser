from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from vietnamese_legal_parser import parse_document


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default="tests/fixtures/real_world_cases.json")
    args = ap.parse_args()
    cases = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    started = time.perf_counter()
    rows = []
    for case in cases:
        out = parse_document({"document_id": case["id"], "content": case["content"]})
        rows.append({
            "id": case["id"],
            "confidence": out["parser"]["confidence"],
            "nodes": out["parser"]["stats"]["node_count"],
            "diagnostics": len(out["parser"]["diagnostics"]),
        })
    elapsed = time.perf_counter() - started
    print(json.dumps({"documents": len(rows), "elapsed_seconds": round(elapsed, 4), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
