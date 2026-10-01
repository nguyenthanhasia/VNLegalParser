# Benchmark summary

The release benchmark is intentionally split by failure class rather than collapsed into one misleading accuracy percentage.

- 23 public-source-linked regression cases: 23/23.
- 2,400 adversarial false-positive trials: 100%.
- 3,000 generated legal-grammar trials: 100%.
- 4,200 extraction mutations over 21 source-linked non-annex cases: 100%.
- 1,600 contextual/layout trials: 100%.
- 5,000 random crash/unique-ID fuzz trials: 100%.

These are regression and robustness measurements, not a universal population accuracy estimate. Run the scripts in `scripts/` to reproduce the deterministic suites.
