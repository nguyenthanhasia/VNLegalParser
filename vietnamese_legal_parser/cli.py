from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .ingest import load_records
from .parser import __version__, parse_document


def _parse_one(record: dict) -> dict:
    return parse_document(record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse Vietnamese legal documents into hierarchical JSON.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-i", "--input", required=True, help="Input .jsonl/.json/.txt/.html/.pdf/.docx")
    parser.add_argument("-o", "--output", required=True, help="Output .jsonl or .json")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print .json output.")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Return exit code 2 if any document falls below this confidence threshold.",
    )
    args = parser.parse_args(argv)

    if not 0.0 <= args.min_confidence <= 1.0:
        parser.error("--min-confidence must be between 0 and 1")

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")

    output_path = Path(args.output)
    if output_path.suffix.lower() not in {".json", ".jsonl"}:
        parser.error("Output extension must be .json or .jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(output_path.name + ".tmp")

    processed = 0
    low_confidence = 0
    try:
        if output_path.suffix.lower() == ".jsonl":
            # Stream JSONL so multi-gigabyte corpora do not need to fit in memory. The temporary
            # file is atomically renamed only after a complete successful parse.
            with tmp_path.open("w", encoding="utf-8") as f:
                for record in load_records(input_path):
                    item = _parse_one(record)
                    processed += 1
                    low_confidence += item["parser"]["confidence"] < args.min_confidence
                    f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        else:
            # A JSON array necessarily needs a materialized result. Use JSONL for large corpora.
            parsed: list[dict] = []
            for record in load_records(input_path):
                item = _parse_one(record)
                parsed.append(item)
                processed += 1
                low_confidence += item["parser"]["confidence"] < args.min_confidence
            payload = parsed[0] if len(parsed) == 1 else parsed
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None),
                encoding="utf-8",
            )
        tmp_path.replace(output_path)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"vlp: error: {exc}", file=sys.stderr)
        return 1

    print(f"Processed {processed} document(s) -> {output_path}")
    if low_confidence:
        print(
            f"{low_confidence} document(s) below confidence threshold {args.min_confidence}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
