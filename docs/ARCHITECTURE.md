# Architecture

The parser is deliberately hybrid rule-based rather than a single permissive regex.

1. **Normalization** preserves legal line boundaries, Unicode, and quotation marks. HTML/DOCX table rows are retained as data rows and are not allowed to masquerade as legal enumerators.
2. **Annex boundary extraction** finds the first conservative standalone `PHỤ LỤC` heading and removes the entire attachment tail from primary-body parsing. The tail is returned raw in `annex_blocks`; parsing individual annexes is intentionally deferred.
3. **Tokenizer + boundary reconstruction** recognizes strong line-start markers and can recover boundaries inside only the damaged physical lines. Whole-document flattened fallback remains available when line layout is broadly lost. Candidate splitting is deliberately separate from acceptance.
4. **Quote state** tracks multi-line Vietnamese/ASCII quotation marks. Structural-looking text inside amendment quotations is preserved as payload instead of promoted into the primary tree.
5. **Sequence evidence** models Arabic numbering, Arabic suffixes, Vietnamese point order (`a,b,c,d,đ,...`), and Roman numerals. Bare clause numbering uses sequence as a conservative guard; point/major sequence gaps are normally diagnostics rather than hard failures so excerpts remain parseable.
6. **Context classifier** combines lexical cues, sequence state, delimiter strength and one-marker look-ahead. It rejects line-start legal references, numeric data (`3.14`, dates, percentages, money, raw table rows), and isolated ambiguous `a.` lines while retaining confirmed dotted point sequences. Each accepted node stores an auditable context score/reason list.
7. **State machine** attaches accepted markers to the nearest valid parent and resets minor state when a new major structural scope begins. Path IDs use per-parent collision counters so malformed duplicate numbering never creates duplicate `element_id` values.
8. **Reference extraction** identifies common Điều/Khoản/Điểm references independently of structural parsing.
9. **Validation** checks path-ID uniqueness and suspicious numbering reversals.
10. **Diagnostics/confidence** expose conservative decisions. Confidence is a heuristic quality signal, not a calibrated probability.

## Design invariant

False structure is more damaging than missing structure for search/RAG because it produces wrong citations and parent-child relationships. Therefore relaxed recognition rules must be paired with negative tests.

Sequence must not become a brittle grammar. Full documents normally progress sequentially, but excerpts, amendments, OCR loss, and minimized snippets can skip values. Hard rejection is therefore reserved for strong ambiguity cases; otherwise sequence anomalies are diagnostics.

## Extension points

- Add marker variants in `tokenizer.py` only with positive + false-positive fixtures.
- Add numbering semantics in `sequence.py` and test both contiguous and skipped/excerpt cases.
- Add annex-boundary rules in `annex.py`; do not parse annex contents into the primary body.
- Add normalization for a source format in `normalization.py`/`ingest.py` without collapsing legal newlines. All Unicode space-separator characters are canonicalized before parsing.
- Add contextual acceptance/rejection logic in `context.py`; tokenizer rules should expose candidates rather than silently promote weak markers.
- Add structural validation in `validation.py`; do not silently rewrite source text.
- Treat OCR/layout recovery as upstream unless a recovery rule can be made deterministic and testable.
