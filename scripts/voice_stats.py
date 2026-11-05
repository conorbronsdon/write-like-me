#!/usr/bin/env python3
"""Measure writing style features and compare a draft to a voice profile.

Usage:
  python3 scripts/voice_stats.py profile samples/*.md --out voice.json [--register NAME]
  python3 scripts/voice_stats.py compare draft.md --profile voice.json [--json]
  python3 scripts/voice_stats.py diff ai-draft.md sent.md [ai2.md sent2.md ...] [--json]

profile stores per-sample measurements, the pooled value, and a range for
each feature. It also holds each sample out in turn and compares it to a
profile built from the others: a sample that drifts on several features is
probably a different register and is reported as a warning.

compare exits 1 when any feature falls outside its range, 0 when all are
inside, and 2 on bad usage or unreadable input.

diff takes pairs of (AI draft, version the writer actually sent) and reports
which features and words the writer's edits moved, and in how many pairs.
It always exits 0 (2 on bad input); it reports evidence, it does not judge.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter

FEATURES = {
    "sentence_mean": "Sentence length, mean (words)",
    "sentence_spread": "Sentence length, spread (std dev)",
    "paragraph_mean": "Paragraph length, mean (sentences)",
    "em_dash_per_1k": "Em dashes per 1,000 words",
    "semicolon_per_1k": "Semicolons per 1,000 words",
    "colon_per_1k": "Colons per 1,000 words",
    "paren_per_1k": "Parentheticals per 1,000 words",
    "question_per_1k": "Questions per 1,000 words",
    "exclaim_per_1k": "Exclamations per 1,000 words",
    "contraction_per_1k": "Contractions per 1,000 words",
    "first_person_per_1k": "First person (I/me/my) per 1,000 words",
    "second_person_per_1k": "Second person (you/your) per 1,000 words",
}
# Rate features get an absolute slack (per 1,000 words) so a feature at zero
# in the samples still tolerates a stray use, and length features a relative one.
ABS_SLACK = 1.5
REL_SLACK = 0.25
MIN_WORDS = 150
# A held-out sample drifting on this many features is likely another register.
# Samples shorter than REGISTER_MIN_WORDS are too noisy to warn about.
REGISTER_DRIFTS = 3
REGISTER_MIN_WORDS = 2 * MIN_WORDS

# Function words say little about voice in a word-level edit diff.
STOPWORDS = set("""a an and are as at be but by for from has have he her his i if in into is it
its me my of on or our she so than that the their them then there these they this to
us was we were what when which who will with you your""".split())

WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")
CONTRACTION = re.compile(r"\b[A-Za-z]+['’](?:s|t|re|ve|ll|d|m)\b", re.I)
FIRST = re.compile(r"\b(?:I|me|my|mine|myself)\b")
SECOND = re.compile(r"\b(?:you|your|yours|yourself)\b", re.I)
SENT_END = re.compile(r"(?<=[.!?])[\"”’')\]]*\s+")
FENCE = re.compile(r"^\s*(```|~~~)")
STRIP = [re.compile(r"`[^`]*`"), re.compile(r"\]\([^)]*\)"), re.compile(r"https?://\S+"),
         re.compile(r"^\s{0,3}#{1,6}\s.*$"), re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")]


def paragraphs(text: str) -> list[str]:
    lines, out, buf, in_code = text.splitlines(), [], [], False
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break
    for raw in lines:
        if FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = raw
        for pat in STRIP:
            line = pat.sub("", line)
        line = line.strip().lstrip(">").strip()
        if line:
            buf.append(line)
        elif buf:
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def measure(text: str) -> dict:
    paras = paragraphs(text)
    sents = [s for p in paras for s in SENT_END.split(p) if WORD.search(s)]
    body = " ".join(paras)
    words = WORD.findall(body)
    n = len(words)
    lengths = [len(WORD.findall(s)) for s in sents]
    per_k = (lambda c: round(1000 * c / n, 2)) if n else (lambda c: 0.0)
    openers = Counter(WORD.findall(s)[0].lower() for s in sents if WORD.findall(s))
    return {
        "words": n,
        "sentences": len(sents),
        "sentence_mean": round(statistics.mean(lengths), 2) if lengths else 0.0,
        "sentence_spread": round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0.0,
        "paragraph_mean": round(len(sents) / len(paras), 2) if paras else 0.0,
        "em_dash_per_1k": per_k(body.count("—") + body.count(" -- ")),
        "semicolon_per_1k": per_k(body.count(";")),
        "colon_per_1k": per_k(len(re.findall(r":(?!//)", body))),
        "paren_per_1k": per_k(len(re.findall(r"\([^)]{3,}\)", body))),
        "question_per_1k": per_k(sum(1 for s in sents if s.rstrip("\"”’') ").endswith("?"))),
        "exclaim_per_1k": per_k(sum(1 for s in sents if s.rstrip("\"”’') ").endswith("!"))),
        "contraction_per_1k": per_k(len(CONTRACTION.findall(body))),
        "first_person_per_1k": per_k(len(FIRST.findall(body))),
        "second_person_per_1k": per_k(len(SECOND.findall(body))),
        "top_openers": [w for w, _ in openers.most_common(8)],
    }


def feature_ranges(per: dict[str, dict], pooled: dict) -> dict[str, list[float]]:
    ranges = {}
    for key in FEATURES:
        vals = [m[key] for m in per.values() if m["words"]]
        lo, hi = (min(vals), max(vals)) if vals else (pooled[key], pooled[key])
        if key.endswith("_per_1k"):
            lo, hi = max(0.0, lo - ABS_SLACK), hi + ABS_SLACK
        else:
            lo, hi = lo * (1 - REL_SLACK), hi * (1 + REL_SLACK)
        ranges[key] = [round(lo, 2), round(hi, 2)]
    return ranges


def holdout(samples: dict[str, str], per: dict[str, dict]) -> dict[str, list[str]]:
    """Compare each sample to a profile built from the others."""
    if len(samples) < 3:
        return {}
    out = {}
    for name, text in samples.items():
        rest = {k: v for k, v in samples.items() if k != name}
        rest_per = {k: per[k] for k in rest}
        rest_pooled = measure("\n\n".join(rest.values()))
        prof = {"pooled": rest_pooled, "ranges": feature_ranges(rest_per, rest_pooled)}
        out[name] = [d["feature"] for d in compare(text, prof)["drifts"]]
    return out


def build_profile(samples: dict[str, str], register: str | None = None) -> dict:
    per = {name: measure(text) for name, text in samples.items()}
    pooled = measure("\n\n".join(samples.values()))
    held = holdout(samples, per)
    warnings = [f"{name} drifts from the other samples on {len(feats)} features "
                f"({', '.join(feats)}); it may be a different register. Profile it "
                f"separately, or drop it from this profile."
                for name, feats in held.items()
                if len(feats) >= REGISTER_DRIFTS and per[name]["words"] >= REGISTER_MIN_WORDS]
    words = pooled["words"]
    return {
        "version": 2,
        "register": register,
        "confidence": "low" if words < 1500 or len(samples) < 3 else "normal",
        "samples": {k: {"words": v["words"], "holdout_drifts": held.get(k, [])}
                    for k, v in per.items()},
        "warnings": warnings,
        "pooled": pooled,
        "ranges": feature_ranges(per, pooled),
    }


def compare(draft: str, profile: dict) -> dict:
    m = measure(draft)
    # One occurrence in a short draft is noise, never a drift on its own.
    one_use = 1000 / m["words"] if m["words"] else 0.0
    drifts = []
    for key, label in FEATURES.items():
        lo, hi = profile["ranges"][key]
        if key.endswith("_per_1k"):
            hi = max(hi, profile["pooled"][key] + one_use)
        val = m[key]
        if val < lo or val > hi:
            drifts.append({"feature": key, "label": label, "draft": val,
                           "profile": profile["pooled"][key], "range": [lo, hi]})
    return {"words": m["words"], "short": m["words"] < MIN_WORDS, "drifts": drifts, "draft": m}


def edit_diff(pairs: list[tuple[str, str]]) -> dict:
    """Report what a writer's own edits changed across (AI draft, sent) pairs."""
    moves = {}
    for key, label in FEATURES.items():
        deltas = [measure(after)[key] - measure(before)[key] for before, after in pairs]
        down = sum(1 for d in deltas if d < 0)
        up = sum(1 for d in deltas if d > 0)
        if down or up:
            moves[key] = {"label": label, "mean_change": round(statistics.mean(deltas), 2),
                          "pairs_down": down, "pairs_up": up}
    cut, added = Counter(), Counter()
    for before, after in pairs:
        b = Counter(w.lower() for w in WORD.findall(" ".join(paragraphs(before))))
        a = Counter(w.lower() for w in WORD.findall(" ".join(paragraphs(after))))
        keep = (lambda w: not w.isdigit() and w not in STOPWORDS)
        cut.update(w for w in b if w not in a and keep(w))
        added.update(w for w in a if w not in b and keep(w))
    return {"pairs": len(pairs), "features": moves,
            "words_cut": cut.most_common(15), "words_added": added.most_common(15)}


def read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("profile", help="measure samples and write a profile")
    p.add_argument("samples", nargs="+")
    p.add_argument("--out", help="write JSON here instead of stdout")
    p.add_argument("--register", help="label for this profile, e.g. newsletter or linkedin")
    c = sub.add_parser("compare", help="compare a draft to a profile")
    c.add_argument("draft")
    c.add_argument("--profile", required=True)
    c.add_argument("--json", action="store_true")
    d = sub.add_parser("diff", help="what the writer's edits changed: AI draft, sent version, ...")
    d.add_argument("files", nargs="+", help="pairs: draft1 sent1 [draft2 sent2 ...]")
    d.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "diff" and len(args.files) % 2:
        print("error: diff needs pairs of files (AI draft, then the version you sent)",
              file=sys.stderr)
        return 2
    try:
        if args.cmd == "profile":
            prof = build_profile({s: read(s) for s in args.samples}, args.register)
            for w in prof["warnings"]:
                print(f"warning: {w}", file=sys.stderr)
            out = json.dumps(prof, indent=2, ensure_ascii=False)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    fh.write(out + "\n")
                print(f"wrote {args.out}: {prof['pooled']['words']} words from "
                      f"{len(prof['samples'])} samples, confidence {prof['confidence']}")
            else:
                print(out)
            return 0
        if args.cmd == "diff":
            files = [read(f) for f in args.files]
            res = edit_diff(list(zip(files[::2], files[1::2])))
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
                return 0
            print(f"{res['pairs']} pair(s). Positive change = the writer added more of it.")
            for v in res["features"].values():
                print(f"{v['label']}: mean change {v['mean_change']:+} "
                      f"(down in {v['pairs_down']}, up in {v['pairs_up']} of {res['pairs']})")
            if res["words_cut"]:
                print("words cut: " + ", ".join(f"{w} ({n})" for w, n in res["words_cut"]))
            if res["words_added"]:
                print("words added: " + ", ".join(f"{w} ({n})" for w, n in res["words_added"]))
            return 0
        profile = json.loads(read(args.profile))
        result = compare(read(args.draft), profile)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["short"]:
            print(f"note: draft is {result['words']} words; measurements are noisy under {MIN_WORDS}.")
        if not result["drifts"]:
            print("On voice: every measured feature is inside the profile's range.")
        for d in result["drifts"]:
            print(f"drift: {d['label']}: draft {d['draft']}, profile {d['profile']} "
                  f"(range {d['range'][0]}–{d['range'][1]})")
    return 1 if result["drifts"] else 0


if __name__ == "__main__":
    sys.exit(main())
