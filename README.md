# 🇻🇳 VNLegalParser

**Robust, deterministic parsing infrastructure for Vietnamese law.**

**Live Demo:** [https://huggingface.co/spaces/nguyenthanhasia/VNLegalParser](https://huggingface.co/spaces/nguyenthanhasia/VNLegalParser)  
**Source Code:** [https://github.com/nguyenthanhasia/VNLegalParser](https://github.com/nguyenthanhasia/VNLegalParser)

A dependency-light parser for Vietnamese legal documents. It converts raw Vietnamese legal text into a hierarchical JSON tree suitable for search, RAG, citation, analytics, and downstream legal NLP.

> Status: **beta / production-candidate**. The parser is designed to fail conservatively and emit diagnostics instead of silently inventing structure. No parser can guarantee perfect structure for every OCR/PDF extraction; use `parser.confidence` and `parser.diagnostics` in production. Confidence is a heuristic quality signal, not a calibrated probability of correctness.

## What it parses

Primary hierarchy:

```text
Phần / Part
└── Chương / Chapter
    └── Mục / Section
        └── Tiểu mục / Subsection
            └── Tiết / Division (legacy/specialized)
                └── Điều / Article
                    └── Khoản / Clause
                        └── Điểm / Point
```

Also supported:

- `Điều 1a`, `Điều 2b`, etc.
- `Khoản 2a`, `Khoản 3b`, etc.
- `Điểm a1`, `Điểm c1`, Vietnamese `đ)`.
- Clause markers `1.` and `2)`.
- Historical forms such as `Điều thứ 1`, `Chương thứ nhất`, `TIẾT THỨ NHẤT`, `Mục A`.
- Accent-degraded PDF/OCR markers such as `DIEU`, `CHUONG`, `MUC`, `PHU LUC`.
- Modern `Phần thứ nhất`, Roman numerals, Arabic numerals, Markdown headings, HTML input.
- Annex-tail extraction: the first structural `PHỤ LỤC` boundary is split into `annex_blocks` and preserved raw; annex parsing is deliberately deferred.
- Flattened copy/paste/PDF text where line breaks were destroyed.
- Partial line-loss recovery when only some headings/clauses/points are merged by PDF extraction.
- Contextual disambiguation for isolated `a.` versus real point sequences, legal-noun references, and `nêu trên` references.
- Multi-line amendment quotations: quoted inserted articles/clauses are kept as content instead of corrupting the primary hierarchy.
- Cross-reference extraction such as `điểm a1 khoản 2a Điều 49`.

## Why this parser is not a single regex

Vietnamese legal text has several ambiguity traps:

- `Chương trình` must not become `Chương tr`.
- `2023.` must not become `Khoản 2023`.
- `Điều 5` in `theo Điều 5` is often a reference, not a new article.
- Amendment documents quote entire inserted articles and clauses inside `“...”`.
- Historical documents use different numbering conventions.
- PDF extraction can produce `...thi hành1.` or `...này.Điều 3` with missing whitespace.
- Numbering is evidence, not truth: `1,2,3`, `a,b,c,d,đ`, and `I,II,III,IV` strengthen structural decisions, but excerpts may legitimately skip numbers.

The parser therefore uses a pipeline:

```text
input
  -> conservative Unicode/HTML normalization
  -> first-annex boundary extraction (raw annex tail)
  -> line-aware tokenizer for the primary body
  -> partial/whole-layout boundary reconstruction
  -> contextual marker classifier (lexical + sequence + look-ahead evidence)
  -> quote-aware marker classification
  -> hierarchy state machine
  -> cross-reference extraction
  -> validation + diagnostics + confidence
```

## Install

Core parser has no runtime dependencies:

```bash
pip install -e .
```

Optional file ingestion:

```bash
pip install -e '.[pdf]'
pip install -e '.[docx]'
pip install -e '.[all]'
```

## Python API

```python
from vietnamese_legal_parser import parse_structure, parse_document

text = """
Chương I
QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
1. Nội dung thứ nhất.
a) Điểm a;
đ) Điểm đ.
"""

# Backward-compatible list result
structure = parse_structure(text)

# Recommended production mode
result = parse_structure(text, include_diagnostics=True)
print(result["confidence"])
print(result["diagnostics"])
print(result["structure"])

record = {
    "document_id": "example-1",
    "title": "Văn bản ví dụ",
    "issuer": "Cơ quan ban hành",
    "content": text,
}
parsed_document = parse_document(record)
```

## CLI

JSONL / JSON:

```bash
vlp -i input.jsonl -o parsed.jsonl
vlp -i one_document.json -o parsed.json --pretty
```

Plain text / HTML:

```bash
vlp -i law.txt -o parsed.json --pretty
vlp -i law.html -o parsed.json --pretty
```

PDF / DOCX require optional dependencies. DOCX ingestion preserves both paragraphs and table rows; table rows are tagged as data so row numbering is not promoted into legal hierarchy:

```bash
vlp -i law.pdf -o parsed.json --pretty
vlp -i law.docx -o parsed.json --pretty
```

Confidence gate for pipelines:

```bash
vlp -i corpus.jsonl -o parsed.jsonl --min-confidence 0.85
```

The CLI returns exit code `2` if any parsed document falls below the requested threshold. JSONL output is streamed and written atomically through a temporary file, so large corpora do not need to fit in memory and failed runs do not leave a partial destination file.

## Output contract

Every structural node contains:

```json
{
  "element_id": "chapter-I/article-1/clause-2/point-dd",
  "element_type": "point",
  "number": "đ",
  "title": "Điểm đ",
  "content": {
    "raw_text": "Nội dung điểm.",
    "normalized_text": "Nội dung điểm.",
    "provisions": []
  },
  "children": [],
  "cross_references": [],
  "metadata": {
    "marker": "đ)",
    "raw_number": "đ",
    "line_no": 10,
    "source": "line",
    "embedded": false,
    "context_score": 0.96,
    "context_reasons": ["canonical_point_parenthesis"]
  }
}
```

`parse_document()` additionally returns `annex_blocks` plus parser provenance. Annex blocks are raw attachment tails and are not structurally parsed in v0.6.0:

```json
{
  "annex_blocks": [
    {
      "index": 1,
      "number": "I",
      "heading": "PHỤ LỤC",
      "raw_text": "PHỤ LỤC\nPHỤ LỤC I\n...",
      "normalized_text": "PHỤ LỤC PHỤ LỤC I ...",
      "start_line": 120,
      "parsed": false
    }
  ]
}
```

Parser provenance includes a SHA-256 hash of the exact input content:

```json
{
  "parser": {
    "name": "vietnamese-legal-parser",
    "version": "0.6.0",
    "source_content_sha256": "<64 lowercase hex characters>",
    "confidence": 0.92,
    "diagnostics": [],
    "stats": {}
  }
}
```

### Element IDs

IDs are path-based rather than global short IDs. This prevents collisions between repeated `Khoản 1`, `Điểm a`, etc. Vietnamese `d)` and `đ)` intentionally produce distinct IDs.

## Diagnostics philosophy

The parser prefers **conservative parsing** over false structure. Ambiguous markers can be retained as content and surfaced in `diagnostics`.

Examples:

- `embedded_quoted_marker`: a legal marker was detected inside an amendment quotation and intentionally kept as quoted content.
- `annex_reference_kept_as_text`: a line looked like an annex reference rather than an actual annex heading.
- `numeric_data_not_clause` / `nonsequential_bare_clause`: a bare numeric line looked like data or broke the active clause sequence and was not promoted to structure.
- `structural_reference_kept_as_text`: a line-start `Điều/Chương/Mục ... của ...` reference was preserved as content instead of becoming primary hierarchy.
- `*_sequence_jump/backward/same`: major/point numbering sequence evidence was recorded without blindly rewriting structure.
- `article_number_reversal`: article order moved backward, suggesting OCR/reordering/quotation issues.

## Real-world regression corpus

`tests/fixtures/real_world_cases.json` contains 23 public-source-linked minimized regression cases plus 2 synthetic HTML/Markdown normalization cases, covering:

- Bộ luật / Luật
- Nghị định
- Nghị quyết
- Thông tư
- Sắc lệnh and the 1946 Constitution
- amendment documents with quoted replacement text
- annex-tail boundaries and annex references
- HTML / Markdown / PDF-like text extraction
- `Điều 1a`, `đ)`, historical ordinals, lettered sections
- flattened and missing-whitespace extraction failures

The suite also contains adversarial false-positive tests and deterministic fuzz mutations for whitespace, NBSP, CRLF, blank lines, and formatting noise.

Run:

```bash
pytest -q
python scripts/benchmark.py
python scripts/stress_benchmark.py
python scripts/contextual_ab_benchmark.py
python scripts/crash_fuzz.py 5000
```

## Production guidance

For a legal RAG/search pipeline:

1. Prefer official HTML/DOCX text when available.
2. If parsing PDF, inspect extraction quality before trusting hierarchy.
3. Treat OCR as an upstream concern; this package parses extracted text and only provides limited accent-degraded marker recovery.
4. Store `element_id`, `document_id`, source URL, and parser version with every chunk.
5. Do not drop diagnostics. Route low-confidence documents to review or a second parser/OCR pass.
6. Pin parser version in indexed data so re-parsing is reproducible.

## Known hard limits

The parser cannot infer structure reliably when the source text itself has lost ordering, e.g. multi-column PDF extraction that interleaves columns, severe OCR corruption, missing pages, or tables converted into arbitrary token order. In these cases the correct behavior is to lower confidence / preserve text rather than fabricate a hierarchy.

It is also a structural parser, not legal interpretation, legal advice, named-entity resolution, or semantic amendment consolidation.

## Development rule

Every parser bug should become a regression test. Every new relaxed recognition rule should include a negative test proving it does not introduce a common false positive.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [schema/v0.6.0.json](schema/v0.6.0.json), [CONTRIBUTING.md](CONTRIBUTING.md), and [CHANGELOG.md](CHANGELOG.md).

## License

MIT.
