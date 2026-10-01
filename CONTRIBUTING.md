# Contributing

1. Add a minimal reproducer for every parser bug.
2. Prefer official Vietnamese legal-document sources for regression fixtures.
3. Do not "fix" one document by weakening marker boundaries globally.
4. Every new structural rule must include at least one positive and one false-positive test.
5. Run `pytest -q` before opening a pull request.

When reporting a parsing failure, include the source URL when public, the smallest failing text span, expected hierarchy, actual hierarchy, and whether the input came from HTML, PDF text extraction, OCR, DOCX, or plain text.
