<div align="center">

# write-like-me

**Your agent needs to stop sounding like AI. Make it sound like you.**

[![GitHub stars](https://img.shields.io/github/stars/conorbronsdon/write-like-me?style=social)](https://github.com/conorbronsdon/write-like-me/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Podcast](https://img.shields.io/badge/Podcast-Chain_of_Thought-purple?style=flat-square)](https://chainofthought.show/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me)
[![X](https://img.shields.io/badge/X-@ConorBronsdon-1DA1F2?logo=x)](https://x.com/ConorBronsdon)

</div>

## TL;DR

A portable agent skill ([SKILL.md](SKILL.md)) that learns your voice from your own writing and holds the agent to it. Install:

```bash
git clone https://github.com/conorbronsdon/write-like-me ~/.claude/skills/write-like-me
```

Then:

1. **Calibrate once:** "build my voice profile from these posts" (point it at 3 to 10 pieces you wrote, 1,500+ words total). It writes `voice.md`.
2. **Write:** "draft the launch post in my voice."
3. **Check:** "does this sound like me?" It reports where the draft drifts and why.

Works with Claude Code, Cursor, Codex, OpenClaw, Hermes Agent, and anything that reads the [agentskills.io](https://agentskills.io) format. Companion to [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me).

---

## Why this exists

Removing AI patterns gets you neutral prose. It reads as if nobody wrote it, which is better than reading like a model but still isn't you.

Most "write in my voice" prompts fail the same way. You paste three posts, the model writes "conversational, authoritative, punchy" into its notes, and every draft comes out conversational, authoritative, and punchy in exactly the way the model already writes. Adjectives don't constrain a model. Evidence does.

So every rule this skill writes into your profile has to cite one of three things:

- **A measurement** of your samples: how much your sentence lengths vary, how often you use em dashes, questions, contractions, "I," "you."
- **A verbatim quote** from your samples showing the habit.
- **Your own answer** to a question the samples couldn't settle ("you never use emoji; is that a rule?").

A rule with none of those gets cut.

## What a check looks like

> **Mostly off voice. Sentences are too even (spread 1.7 vs. your 6.2), and there's no "I" or "you" anywhere; your samples average 52 and 25 per 1,000 words.**

The measurement half is a script you can run yourself:

```bash
python3 scripts/voice_stats.py profile examples/samples/*.md --out voice.json
python3 scripts/voice_stats.py compare examples/off-voice-draft.md --profile voice.json
```

```text
drift: Sentence length, spread (std dev): draft 1.71, profile 6.2 (range 3.64–8.94)
drift: Contractions per 1,000 words: draft 8.85, profile 40.08 (range 23.75–51.81)
drift: First person (I/me/my) per 1,000 words: draft 0.0, profile 51.53 (range 33.85–64.39)
...
```

`compare` exits 1 on drift, so you can gate a draft in a script or CI. It's Python 3.9+ with no dependencies. The numbers catch rhythm and register; the skill reads for the rest (openings, closings, signature moves, what you never do).

## Modes

- `calibrate`: samples in, `voice.md` (plus `voice.json`) out. Shows you the profile and asks what's wrong with it.
- `write`: draft new text from the profile.
- `edit`: rewrite existing text into your voice without changing any fact, number, name, or caveat.
- `check`: report drift; no rewriting unless asked.

The profile format is in [templates/voice.md](templates/voice.md). Keep it in your project, or at `~/.config/write-like-me/voice.md` to use it everywhere.

## Where it fits

| Step | Skill | Job |
|---|---|---|
| 1 | [fact-check](https://github.com/conorbronsdon/fact-check?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me) | Are the claims true? |
| 2 | **write-like-me** | Does it sound like you? |
| 3 | [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me) | Does it sound like a model? |

avoid-ai-writing's built-in voice profiles (casual, professional, technical, warm, blunt) are registers anyone can pick. This skill's profile is yours alone. Where they disagree (you love em dashes, avoid-ai-writing flags them), your profile wins, and the change summary says so.

## Limits

- It calibrates only from writing you did yourself. Imitating a named third party is out of scope.
- Under 1,500 words of samples, the profile is marked low confidence. Under about 150 words, a draft's measurements are noisy and the skill says so.
- One register per profile. A newsletter voice and a legal-memo voice need separate profiles.

## More from me

- [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me): audit and rewrite AI writing patterns.
- [What I'm building](https://conorbronsdon.com/builds/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me): agent skills, MCP servers, creator tools.
- [Chain of Thought](https://chainofthought.show/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me): conversations with the people shipping AI systems.

Authored by [Conor Bronsdon](https://conorbronsdon.com/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=write-like-me) · [GitHub](https://github.com/conorbronsdon) · [X](https://x.com/ConorBronsdon) · [LinkedIn](https://www.linkedin.com/in/conorbronsdon/)

---

## Disclaimer

*This is an independent personal project, not affiliated with, sponsored by, or endorsed by any company. All views expressed are my own.*

## License

MIT
