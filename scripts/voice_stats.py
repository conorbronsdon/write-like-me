#!/usr/bin/env python3
"""Measure writing style features and compare a draft to a voice profile.

Usage:
  python3 scripts/voice_stats.py profile samples/*.md --out voice.json
  python3 scripts/voice_stats.py compare draft.md --profile voice.json [--json]

The profile stores per-sample measurements, the pooled value, and a range
for each feature. compare exits 1 when any feature falls outside its range,
0 when all are inside, and 2 on bad usage or unreadable input.
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


def build_profile(samples: dict[str, str]) -> dict:
    per = {name: measure(text) for name, text in samples.items()}
    pooled = measure("\n\n".join(samples.values()))
    ranges = {}
    for key in FEATURES:
        vals = [m[key] for m in per.values() if m["words"]]
        lo, hi = (min(vals), max(vals)) if vals else (pooled[key], pooled[key])
        if key.endswith("_per_1k"):
            lo, hi = max(0.0, lo - ABS_SLACK), hi + ABS_SLACK
        else:
            lo, hi = lo * (1 - REL_SLACK), hi * (1 + REL_SLACK)
        ranges[key] = [round(lo, 2), round(hi, 2)]
    words = pooled["words"]
    return {
        "version": 1,
        "confidence": "low" if words < 1500 or len(samples) < 3 else "normal",
        "samples": {k: {"words": v["words"]} for k, v in per.items()},
        "pooled": pooled,
        "ranges": ranges,
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
    c = sub.add_parser("compare", help="compare a draft to a profile")
    c.add_argument("draft")
    c.add_argument("--profile", required=True)
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "profile":
            prof = build_profile({s: read(s) for s in args.samples})
            out = json.dumps(prof, indent=2, ensure_ascii=False)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    fh.write(out + "\n")
                print(f"wrote {args.out}: {prof['pooled']['words']} words from "
                      f"{len(prof['samples'])} samples, confidence {prof['confidence']}")
            else:
                print(out)
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
