# Release validation — v0.7.0

## Gates

- `pytest`: **65 / 65 passed**.
- Sequence/adversarial benchmark: **2,400 / 2,400 passed**.
- Generated legal grammar: **3,000 / 3,000 passed**.
- Contextual targeted benchmark: **1,600 / 1,600 passed**.
- Crash + unique-ID fuzz: **5,000 / 5,000 passed**.
- Real PDF smoke: `luat27.pdf` (93-page Công báo extract, Luật Nhà ở 27/2023/QH15) parsed with PyMuPDF-preferred ingestion into **7 chapters, 20 sections, 117 articles, 497 clauses, 390 points**. The Article sequence is exactly **1..117**; wrapped citation-list false Articles found in v0.6.0 are rejected as references.
- All diagnostics on that PDF are informational reference rejections; no article/section sequence anomaly remains.

## Important limitation

These gates validate the current regression/stress distributions. They do **not** establish universal 100% accuracy on arbitrary OCR, malformed PDFs, missing pages, or multi-column reading-order corruption. Confidence remains a heuristic quality signal.

## Packaging smoke

- Built `vietnamese_legal_parser-0.7.0-py3-none-any.whl` with `pip wheel --no-build-isolation --no-deps`.
- Installed the wheel into a fresh virtual environment; `vlp --version` returned `0.7.0` and a basic parse succeeded.
