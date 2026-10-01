# Changelog

## 0.7.0

- Prefer PyMuPDF for PDF ingestion, with pypdf compatibility fallback.
- Repair a conservative set of PDF-split Vietnamese legal cue words such as `c ủa Lu ật`.
- Reject wrapped citation-list markers such as `Điều 112, khoản 1 Điều 113...` and `Mục 3, 4 và 5 Chương này...`.
- Add regressions derived from a 93-page Công báo PDF of Luật Nhà ở 27/2023/QH15.
- Preserve reciprocal GitHub ↔ Hugging Face Space links in release metadata and docs.

## 0.6.0

- Added partial-line boundary reconstruction for PDF/OCR extraction where only some legal boundaries are lost.
- Added a dedicated contextual marker classifier with lexical, sequence, delimiter and look-ahead evidence plus auditable `context_score` / `context_reasons`.
- Resolved isolated dotted-letter ambiguity: `a.` is rejected without sequence evidence while `a., b., c.` sequences remain parseable.
- Expanded structural-reference guards to forms such as `Điều 15 Luật ...` and `Điều 15 nêu trên ...`.
- Hardened flattened-text recovery around closing quotes, amendment payloads, annex references and skipped Vietnamese point sequences.
- Canonicalized Unicode space separators and structural Roman/letter identifiers while preserving `raw_number` metadata.
- Guaranteed unique path IDs even when malformed source repeats the same numbering under one parent.
- Expanded source-linked regression corpus to 23 cases and added contextual A/B plus 5,000-case crash-fuzz tooling.

## 0.5.0

- Added sequence-aware numbering evidence for Arabic clauses/articles, Vietnamese point order (`a,b,c,d,đ,...`), Roman numerals, and suffix forms.
- Added contextual guards for line-start structural references and numeric-data false positives such as decimals, dates, percentages, money and raw table rows.
- Split the document at the first structural annex heading before primary parsing; the annex tail is returned as an unparsed raw `annex_blocks` payload.
- Generic `PHỤ LỤC` followed by `PHỤ LỤC I` is preserved as one annex block and inherits the first adjacent concrete annex number as metadata.
- Added A/B benchmark scripts for false-positive, generated-grammar and extraction-mutation testing.
- Preserved excerpt tolerance by treating point/major sequence gaps as soft evidence rather than universal hard failures.

## 0.4.0

- Hardened annex-reference detection and article-order validation by independent scope.
- Added empty/unstructured-input diagnostics and input SHA-256 provenance.
- Added table-aware HTML and DOCX ingestion; DOCX tables are no longer silently discarded.
- Streamed JSONL CLI output with atomic destination replacement and contextual malformed-JSONL errors.
- Expanded source-linked regression coverage through 2026 and added large-document stress benchmarking.
- Added a versioned JSON Schema and architecture documentation.

## 0.3.0

- Replaced global `re.split` parser with line-aware tokenizer and hierarchy state machine.
- Added conservative fallback for flattened PDF/HTML text.
- Added support for `Điều 1a`, Vietnamese `đ)`, `Tiểu mục`, `Tiết`, annexes, numeric-parenthesis clauses, HTML and Markdown normalization.
- Added quote-aware amendment handling so inserted/amended articles inside quotations do not corrupt the primary hierarchy.
- Added unique path-based element IDs, cross-reference extraction, confidence/diagnostics, richer metadata mapping and CLI confidence thresholds.
- Added optional PDF/DOCX ingestion and GitHub CI.
- Added real-world regression fixtures plus adversarial and deterministic fuzz tests.
