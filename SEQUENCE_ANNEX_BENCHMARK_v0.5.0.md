# Sequence + Annex A/B Benchmark — v0.5.0

## A/B summary

| Suite | v0.4.0 | v0.5.0 |
|---|---:|---:|
| Adversarial false-positive (2,400 trials) | 43.75% | 93.75% |
| Generated legal grammar (3,000 trials) | 100.00% | 100.00% |
| Source fixtures, unchanged semantics (19 cases) | 100.00% | 100.00% |
| Extraction mutations (3,400 trials, 17 source-linked cases) | 79.97% | 79.97% |

The false-positive improvement is concentrated in line-start article/chapter/section references and numeric data that resemble clauses. The only deliberately unresolved adversarial category is a standalone `a. Sentence...` line, because hard-rejecting all period-style letter markers would risk historical/excerpt recall.

## Annex isolation

A separate 400-trial annex-boundary stress check passed 400/400 cases covering:

- numbered annex headings;
- generic `PHỤ LỤC` followed by `PHỤ LỤC I`;
- in-body annex references followed later by a real annex;
- reference-only documents that must not be split.

## Mutation breakdown (v0.5.0)

- whitespace: **425/425 = 100.00%**
- unicode: **385/425 = 90.59%**
- html_wrapped: **425/425 = 100.00%**
- markdown_noise: **425/425 = 100.00%**
- marker_case_punct: **332/425 = 78.12%**
- flattened: **325/425 = 76.47%**
- partial_line_loss: **192/425 = 45.18%**
- mixed: **210/425 = 49.41%**

These rates are stress-test category rates, not a calibrated estimate of accuracy across all Vietnamese legal documents.
