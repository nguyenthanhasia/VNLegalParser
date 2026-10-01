# Real-PDF regression — v0.7.0

A 93-page Công báo PDF containing Luật Nhà ở 27/2023/QH15 was used as a release smoke test after v0.6.0 exposed false structural nodes caused by PDF extraction and wrapped legal references.

## v0.7.0 result

- Chapters: 7
- Sections: 20
- Articles: 117
- Clauses: 497
- Points: 390
- Article sequence: exact 1 → 117
- Warning/error diagnostics: 0
- Informational diagnostics: 31, all `structural_reference_kept_as_text`
- Heuristic confidence: 0.845

## Fixes exercised by this PDF

1. PyMuPDF is now the preferred PDF text extractor; pypdf remains a compatibility fallback.
2. A conservative normalization pass repairs extractor-split legal cue words such as `c ủa Lu ật`.
3. Wrapped citation lists such as `Điều 112, khoản 1 Điều 113...` are kept as references rather than promoted to Articles.
4. Wrapped section citations such as `Mục 3, 4 và 5 Chương này...` are kept as text rather than promoted to Sections.

This is a regression result for one real PDF, not a claim of universal accuracy across arbitrary PDFs/OCR.
