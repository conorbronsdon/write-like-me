# Agent instructions: write-like-me

This repo ships one skill, `SKILL.md`, plus a profile template and an optional measurement script.

## Layout

- `SKILL.md`: the skill. The only file consumers need.
- `templates/voice.md`: the profile format `calibrate` writes. Every rule in it cites evidence.
- `scripts/voice_stats.py`: stdlib-only measurement. `profile` writes `voice.json`; `compare` exits 1 on drift, 0 on voice, 2 on bad input.
- `tests/test_voice_stats.py`: run with `python3 -m unittest discover -s tests -v`.
- `examples/samples/`: three short invented samples in one voice, and `examples/off-voice-draft.md`, a generic draft that must drift. The CLI test depends on both; keep them in sync.
- `.claude-plugin/plugin.json`: Claude Code plugin manifest. Its `version` must match the `SKILL.md` frontmatter `version`.

## Rules

- Every profile rule needs evidence. Do not add template sections that invite unbacked adjectives ("warm," "authoritative").
- Calibrate only from text the user wrote. Do not add a mode that imitates a named third party.
- Keep the script dependency-free and Python 3.9-compatible. CI runs 3.9 and 3.13.
- A new measured feature needs a test that separates a varied sample from an even one, and a range rule that tolerates a single stray use.
- Version bumps: update `SKILL.md`, `.claude-plugin/plugin.json`, and `CHANGELOG.md` together.
