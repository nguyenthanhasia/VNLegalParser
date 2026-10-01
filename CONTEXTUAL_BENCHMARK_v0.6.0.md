# Contextual / layout benchmark — v0.6.0

This report is a regression/stress benchmark, **not a claim of universal parser accuracy**. The corpus is finite and many trials are deterministic mutations of known public-source snippets.

## Release results

| Suite | v0.6.0 |
|---|---:|
| Pytest | 62 / 62 |
| Source-linked regression cases | 23 / 23 |
| Adversarial false-positive trials | 2,400 / 2,400 |
| Generated legal grammar | 3,000 / 3,000 |
| Extraction mutations across 21 source-linked non-annex cases | 4,200 / 4,200 |
| Contextual boundary/disambiguation suite | 1,600 / 1,600 |
| Random crash/unique-ID fuzz | 5,000 / 5,000 |

The 4,200 extraction mutations are evenly split across whitespace, Unicode spacing, HTML wrapping, Markdown noise, marker case/punctuation noise, fully flattened text, partial line loss, and mixed noise. Each category passed 525/525.

## A/B evidence versus v0.5.0

The previously measured v0.5.0 extraction-mutation suite on 17 source-linked non-annex cases scored 2,719/3,400 (79.97%). Before the final v0.6 hardening, the same legacy set reached 3,400/3,400 after contextual reconstruction was introduced.

The targeted contextual suite contains 1,600 cases covering partial clause merges, inline point merges, mixed major boundaries, isolated `a.` false positives, legitimate dotted-point sequences, legal-noun references, `nêu trên` references, and clause boundaries following closing amendment quotes. On this suite:

- v0.5.0: 200 / 1,600 (12.5%)
- v0.6.0: 1,600 / 1,600 (100%)

This targeted suite is intentionally constructed around the failure modes v0.6 addresses and therefore must not be interpreted as an unbiased overall accuracy comparison.

## Large-document performance smoke test

A generated document with 10,000 Articles produced 100,001 nodes from ~2.54 million characters with zero diagnostics in ~8.52 seconds in the release environment. This is a smoke measurement, not an SLA or cross-machine benchmark.

## Remaining risk

Passing the current suites does not prove correctness for arbitrary source material. Multi-column PDF ordering loss, severe OCR corruption, missing pages, exotic historical notation, and unseen table/layout conventions remain external or under-sampled risks. The parser continues to expose diagnostics, confidence, source provenance and reconstruction statistics for downstream review gates.
