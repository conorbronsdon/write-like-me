# Agent instructions: write-like-me

This repo ships one skill, `SKILL.md`, plus a profile template and an optional measurement script.

## Layout

- `SKILL.md`: the skill. The only file consumers need.
- `templates/voice.md`: the profile format `calibrate` writes. Every rule in it cites evidence.
- `scripts/voice_stats.py`: stdlib-only measurement. `profile` writes `voice.json` and warns (stderr) about samples that look like another register; `compare` exits 1 on drift, 0 on voice, 2 on bad input; `diff` reports what a writer's edits changed across (AI draft, sent) pairs and exits 0, or 2 on bad input.
- `tests/test_voice_stats.py`: run with `python3 -m unittest discover -s tests -v`.
- `examples/samples/`: three short invented samples in one voice, and `examples/off-voice-draft.md`, a generic draft that must drift. The CLI test depends on both; keep them in sync.
- `.claude-plugin/plugin.json`: Claude Code plugin manifest. Its `version` must match the `SKILL.md` frontmatter `version`.

## Rules

- Every profile rule needs evidence: a measurement, a quote, `writer edited`, or `writer said`. Do not add template sections that invite unbacked adjectives ("warm," "authoritative").
- An absence seen only in samples is provisional until the writer confirms it. Do not promote it to a hard rule in tooling or templates.
- Installing the skill must stay inert: no step reads files or writes a profile until the user asks.
- Calibrate only from text the user wrote. Do not add a mode that imitates a named third party.
- Keep the script dependency-free and Python 3.9-compatible. CI runs 3.9 and 3.13.
- A new measured feature needs a test that separates a varied sample from an even one, and a range rule that tolerates a single stray use.
- A new warning or detector ships with a must-fire test and a must-not-fire test (see `Registers` in the tests).
- When mutation-testing the script, set `PYTHONDONTWRITEBYTECODE=1`. A same-size edit restored within the same second can leave a stale `.pyc` that runs the mutant.
- Version bumps: update `SKILL.md`, `.claude-plugin/plugin.json`, and `CHANGELOG.md` together.
