# Release validation — v0.6.0

- `pytest -q`: 62 passed.
- Source-linked regression corpus: 23/23.
- Adversarial false-positive suite: 2,400/2,400.
- Generated legal grammar: 3,000/3,000.
- Extraction mutation suite: 4,200/4,200 across 21 source-linked non-annex cases.
- Contextual boundary/disambiguation suite: 1,600/1,600.
- Crash + unique-ID fuzz: 5,000/5,000.
- Large-document smoke: 10,000 Articles, 100,001 nodes, ~2.54M chars, zero diagnostics, ~8.52 s in the release environment.
- Annex-tail behavior remains opt-out parsing: first structural annex boundary is returned in `annex_blocks` with `parsed=false`.
- Confidence remains a heuristic quality signal and is lightly penalized when partial boundary reconstruction is required.

See `CONTEXTUAL_BENCHMARK_v0.6.0.md` for interpretation and limitations.
- Wheel built with `pip wheel --no-build-isolation --no-deps` and installed into a fresh virtualenv.
- Fresh-venv smoke: `vlp --version` => `0.6.0`; inline point reconstruction and annex isolation both verified.
