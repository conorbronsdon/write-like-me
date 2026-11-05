# Changelog

## 0.1.0 (unreleased)

- First public version: `calibrate`, `write`, `edit`, and `check` modes; evidence-backed voice profile template (`templates/voice.md`) where every rule cites a measurement, a quoted excerpt, or the writer's own answer.
- Register-aware profiles: sort samples by register, calibrate each with `--register` into `voice.<register>.md`; profile lookup picks the matching one.
- `profile` holds each sample out and warns when one drifts on 3+ features (likely another register). Samples under 300 words are recorded but not warned about.
- `diff` command: mine (AI draft, sent version) pairs for the features and words the writer's edits moved. New evidence source, `writer edited`.
- Absences seen only in samples are provisional until the writer confirms them; `check` reports a broken provisional absence as a note, not a drift.
- `refine` mode: change one rule, test it on one paragraph, log it in the profile's change log.
- Optional blind test during calibration: held-out sample vs. generated passage, judged by a fresh-context reader.
- `write` and `edit` revise at most twice after `check`, then report what still drifts.
- `compare` tolerates one missing use as well as one stray use: in a short draft, lacking a feature the profile uses less than once per draft length is not drift. Widened bounds are rounded.
- Install is inert; anti-overcorrection rule (no typos, fake anecdotes, or invented experiences).
- `scripts/voice_stats.py`: dependency-free measurement of sentence rhythm, punctuation rates, contractions, person, and openers; `profile` builds per-feature ranges from samples, `compare` flags drift and exits 1.
