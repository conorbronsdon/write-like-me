# Changelog

## 0.1.0 (unreleased)

- First public version: `calibrate`, `write`, `edit`, and `check` modes; evidence-backed voice profile template (`templates/voice.md`) where every rule cites a measurement, a quoted excerpt, or the writer's own answer.
- `scripts/voice_stats.py`: dependency-free measurement of sentence rhythm, punctuation rates, contractions, person, and openers; `profile` builds per-feature ranges from samples, `compare` flags drift and exits 1.
