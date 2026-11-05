---
name: write-like-me
description: Build a voice profile from someone's own writing samples, then draft, edit, or check text against it so the agent writes like that person instead of like a model. Use when asked to "write like me," "match my voice," "learn my writing style," "make this sound like me," "build a voice profile," or "does this sound like me." Measures the samples (sentence rhythm, punctuation, openers) and backs every rule with a quoted excerpt. Pairs with avoid-ai-writing, which removes AI patterns; this skill adds the writer's own.
version: 0.1.0
license: MIT
compatibility: Any AI coding assistant that supports agentskills.io SKILL.md format (Claude Code, Cursor, Codex, OpenClaw, Hermes Agent, etc.). The optional measurement script needs Python 3.9+ and no packages; without it the skill estimates the same features by reading.
metadata:
  author: Conor Bronsdon
  repository: https://github.com/conorbronsdon/write-like-me
  tags: writing voice style editing personalization
  agentskills_spec: "1.0"
---

# Write Like Me

Removing AI patterns makes text sound less like a model. It does not make it sound like you. This skill does the second half: it builds a voice profile from your own writing, then uses that profile to draft, edit, and check.

Every rule in the profile has to be backed by evidence: a measurement, a quoted excerpt from the samples, an edit the writer made to an AI draft, or something the writer said. "Conversational but authoritative" with nothing under it is the kind of rule a model ignores, because it already believes it writes that way.

Installing this skill does nothing on its own. It reads samples, and writes a profile, only when the person asks it to calibrate, and only from files or text they point at.

## Modes

- `calibrate`: read samples, measure them, write `voice.md` (and `voice.json` if the script ran). Run this once, and again when your writing changes.
- `write` (default once a profile exists): draft new text in the profile's voice.
- `edit`: rewrite existing text into the voice. Keep every fact, claim, and caveat.
- `check`: compare a draft to the profile and report where it drifts. Do not rewrite unless asked.
- `refine`: fix one thing the profile gets wrong, test the fix on one paragraph, and log it. Use it after a draft misses, instead of recalibrating.

Look for an existing profile first: `voice.md` or `voice.<register>.md` in the current project, then the same names in `~/.config/write-like-me/`. If there are several, pick the one whose register matches the task (a LinkedIn post uses `voice.linkedin.md`), or ask. If none exists and the user asks to write or edit, offer to calibrate first. Without a profile, say that the output is a generic edit, not their voice.

## Calibrate

### 1. Collect samples

Ask for 3 to 10 pieces the person wrote themselves, 1,500 words or more in total. Good samples:

- Were written without AI help. Older work is fine; anything from before 2023 is safest.
- Cover one register: a newsletter voice and a legal memo voice are different profiles. If the samples span registers (essays and LinkedIn posts, tech and politics), sort them by register first and calibrate each group with `--register <name>` into its own `voice.<name>.md`. Pooling registers makes every range wide enough that nothing drifts, which means `check` stops catching anything.
- Include at least one piece they are proud of. Ask which one; it becomes the reference sample.

Also ask whether they have **edit pairs**: an AI draft and the version they actually sent. They are the best evidence there is, because they show which way the writer pushes text. Three or more pairs are enough to start. Collect them as files; they are not samples (the sent version can be, if they wrote most of it).

Refuse to calibrate from text the person did not write. Calibrating from someone else's work to imitate them is out of scope.

If the samples total under 1,500 words, calibrate anyway but mark the profile `low confidence` and say why.

### 2. Measure

If the script is available, run it on the samples:

```bash
python3 scripts/voice_stats.py profile samples/*.md --out voice.json --register newsletter
python3 scripts/voice_stats.py diff ai-draft-1.md sent-1.md ai-draft-2.md sent-2.md   # if there are edit pairs
```

It reports sentence and paragraph length (mean and spread), punctuation rates per 1,000 words (em dashes, semicolons, colons, parentheses, questions, exclamations), contraction rate, first- and second-person rates, and the most common sentence openers. Without the script, estimate the same features from a careful read and label them estimates.

The spread of sentence length matters more than the mean. Human writing mixes short and long sentences. Model writing tends to keep them even.

`profile` holds each sample out in turn and compares it to a profile built from the rest. A sample that drifts on three or more features gets a warning: it is probably a different register (an About page among essays, a rant among tutorials). Ask the writer whether it belongs before keeping it. The check finds one odd sample. It does not detect a corpus that is half one register and half another, so sorting by register in step 1 is still your job.

`diff` reports which measured features the writer's edits moved, and in how many pairs, plus the words they cut and added. `diff` counts a pair as moving a feature only when the change is bigger than noise (1.5 per 1,000 words for rates, 10% for lengths), so deleting one word doesn't register as "shorter sentences." A feature that moved the same way in at least three pairs, and in every pair, is a rule sourced `writer edited`. With fewer pairs it is provisional. A word they cut in two or more pairs belongs under Probably never until the writer confirms it.

### 3. Read for what numbers can't show

Read every sample in full. Record, each with at least one verbatim quote from the samples:

- **Openings**: how pieces and paragraphs start. A question, a number, a scene, a blunt claim.
- **Closings**: how pieces end. A summary, a question, an implication, a joke, a call to action.
- **Signature moves**: recurring habits (asides in parentheses, one-line paragraphs, self-deprecation, naming specific people and numbers, analogies from a particular field).
- **Vocabulary**: words and phrases they use often, and plain words they choose where others reach for fancier ones.
- **Stance**: how they handle certainty. Do they hedge, or state positions flatly? Do they argue, explain, or tell stories?
- **Absences**: things a model would do that they never do. Absences are the strongest rules, because they are the ones the model will break. But an absence in a few samples might be chance. Record each one as **provisional**, with its count ("0 of 6 samples"), until the writer confirms it in step 4 or the edit pairs show them removing it. Only confirmed absences are hard rules.

Do not invent a habit to fill a section. If the samples don't show it, leave the section out.

### 4. Ask only what the samples can't answer

Ask at most five short questions, and only where the samples are silent or contradict each other. Spend them first on the provisional absences most likely to matter. Typical ones: "Your posts never use emoji; is that a rule?" "You swear in two of the eight samples; keep or avoid?" "Who are you usually writing for?" Record each answer as a rule with the source `writer said`.

Ask after measuring and reading, never before. What people say about their own style is less reliable than what their writing shows, so the questions settle what the samples leave open. They do not replace the samples.

### 5. Write the profile

Write `voice.md` using [templates/voice.md](templates/voice.md). Rules:

- Lead with a five-line summary the agent can hold in mind while drafting.
- Every rule cites its evidence: a measurement from `voice.json`, a quoted excerpt, or `writer said`.
- Include two or three reference excerpts of 50 to 150 words each, quoted exactly, with what each one shows.
- Keep the whole profile under 200 lines. A profile too long to read before every draft will not be used.
- Show the person the profile and ask what is wrong with it. Fix what they flag. They are the judge of their own voice.

### 6. Blind test (optional, needs 5+ samples)

A profile can pass every measurement and still produce text the writer's readers would not mistake for theirs. To test that:

1. Before step 2, set aside one sample of 300+ words that is not the reference sample. Calibrate from the rest.
2. Write a passage of about the same length on the held-out sample's topic, from the profile alone. Give yourself its subject and main points, never its sentences.
3. Give a judge with fresh context (a subagent, or a person who knows the writer) two other real samples as reference, then the held-out sample and your passage in random order. Ask which one the writer wrote and why.
4. Record the result and the judge's reason in the profile's header. A judge who picks your passage, or can't tell, is a pass. One trial is weak evidence; say so, or run three on different held-out samples.
5. Add the held-out sample back and recalibrate.

The judge's reason is the useful part. "The second one hedges, and the reference samples never do" is a rule you missed. Two lessons from running it:

- **Discard tells about errors.** Judges often pick the human because of typos, a split word, or a tense slip. That is real, but the profile must never add errors to imitate it. Keep the tells about openings, structure, analogies, and rhythm.
- **Don't use `compare` as the tiebreak.** The profile's ranges come from whole pieces, and a held-out excerpt (an opening section, say) can drift from them while being the writer's own words. In one trial the real excerpt drifted on two features and the imitation drifted on one. The judge, not the numbers, decides this test.

## Write and edit

1. Read `voice.md` in full, including the reference excerpts.
2. Draft (or edit). Match the measured rhythm: if their sentence lengths vary widely, vary yours; if they never use semicolons, don't.
3. Apply the confirmed absences as hard rules. Avoid the provisional ones too, unless the task clearly calls for one; if you use one, say so.
4. In `edit` mode, keep every fact, number, name, link, quote, and caveat. Change how it is said, not what is said. If a sentence can't move into the voice without changing its meaning, leave it and say so.
5. Run `check` on your own output before returning it. Fix what drifts, at most twice. If something still drifts after two revisions, return the draft anyway and list what is still off and why; a third pass usually trades one drift for another.

Don't overdo it. Using every signature move in one paragraph is a parody of the writer. Use their habits at the rate the samples show.

Don't overcorrect, either. Sounding human is not the same as sounding sloppy. Do not add typos, fake anecdotes, or experiences the writer did not have. If the voice calls for a personal story, ask the writer for one.

## Check

Compare the draft to the profile:

```bash
python3 scripts/voice_stats.py compare draft.md --profile voice.json
```

The script flags each measured feature that falls outside the profile's range and exits 1 if any did. Then read the draft against the qualitative rules and the absences. Report:

> **Mostly on voice. Two drifts: sentences are too even (spread 4.1 vs. the profile's 9.8), and the opening is a rhetorical question, which none of the 8 samples use.**

followed by a short list of the specific sentences that drift and why. Lead with the verdict. Don't list features that passed.

Short drafts (under about 150 words) give noisy measurements. Say so and weight the read over the numbers.

A broken hard rule (a confirmed absence) is a drift. A broken provisional absence is a note: mention it, and offer to ask the writer whether it is a rule.

## Refine

Use this when a draft missed and the writer can say how ("too formal," "I'd never open with a question," "that's not how I end things").

1. Find the cause in the profile: a rule that is missing, wrong, or too loose. Name it.
2. Propose one change, with its evidence: `writer said`, an edit pair, or a quote from the samples.
3. Rewrite one paragraph of the missed draft under the changed rule, and show the before and after.
4. If the writer approves, update `voice.md` and add a dated line to its change log. If not, ask what is still off and try again, at most twice.

Change one rule per refine. If the profile needs more than three changes at once, recalibrate instead. Keep the profile under 200 lines: when a new rule pushes it over, merge or cut an older one, and say which.

## Pairing

- [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) removes AI patterns. Its built-in voice profiles (casual, professional, and so on) are generic registers; this profile is the writer's own. Run it after `write` or `edit`. Where the profile and avoid-ai-writing disagree (for example, the writer loves em dashes), the profile wins for that writer, and say so in the change summary.
- [fact-check](https://github.com/conorbronsdon/fact-check) verifies claims. Run it before polishing anything you will publish.
