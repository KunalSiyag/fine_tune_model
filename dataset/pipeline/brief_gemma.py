#!/usr/bin/env python3
"""Gemma 4 (local, Ollama) turns a one-line request into the design spec the fine-tuned model was trained on.

    python3 dataset/pipeline/brief_gemma.py "a site for my bakery in Pune"
    python3 dataset/pipeline/brief_gemma.py --ab dataset/briefs/ab_oneliners.txt --out dataset/runs/ab

The fine-tuned Qwen3-8B saw three prompt styles: terse one-liners, client briefs and art-direction
specs (palette hex, named fonts, sections in order, the interaction, motion, reduced motion). Users
type one-liners; Gemma writes the spec. Its few-shot examples are real terse→spec pairs of the same
page from sft_train.jsonl, so its output lands in the training distribution.

--ab writes raw.jsonl (the one-liner as-is, a terse prompt) and gemma.jsonl (Gemma's spec) with the
same ids, for `train_tinker.py sample --prompts` — the A/B test of whether the rewrite helps.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

from build_dataset import SYSTEM  # the fine-tuned model's system prompt, verbatim

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dataset" / "out"
OLLAMA = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b"
NO_PHOTOS = "No photos are available — use CSS, SVG or canvas for imagery."

GEMMA_SYSTEM = (
    "You are an art director. Turn a client's one-line website request into a design spec for a "
    "developer, in exactly the style of the examples: one dense paragraph of plain prose, no markdown, "
    "no headings, no preamble. Commit to a specific palette with hex values, named Google Fonts with "
    "their roles, the sections in order with real content (names, numbers, prices, dates — invent "
    "plausible, obviously fictional specifics where the client gave none), exactly one interaction "
    "that really works, the motion, and what reduced motion shows. Keep every fact the client gave, "
    "and repeat its place names and business details word for word. "
    "Pick an art direction that fits this particular business instead of a generic tech look. "
    "Fonts must be families that exist on Google Fonts (never system fonts such as Courier New, "
    "Arial, Helvetica, Georgia or ui-monospace). Keep the interaction small enough for a short "
    "script: one filter, tab set, calculator, accordion or validated form, not several. "
    "The page is static HTML/CSS/JS: there are no photos (imagery is CSS, SVG or canvas), no backend "
    "(forms validate and confirm in the page), and no embeds such as maps or videos. "
    "Write in English unless the request is in another language. 160-240 words."
)


def few_shot_pairs(k: int, seed: int | str) -> list[tuple[str, str]]:
    """k (terse, spec) pairs describing the same page, shortest specs only."""
    by = defaultdict(dict)
    for line in (OUT / "sft_train.jsonl").open():
        r = json.loads(line)
        if r["task"] == "page_from_brief":
            src, variant = r["id"].rsplit(":", 1)
            by[src][variant] = r["messages"][1]["content"]
    pairs = []
    for d in by.values():
        if "terse" in d and "spec" in d and d["spec"].endswith(NO_PHOTOS):
            terse = d["terse"].removesuffix(NO_PHOTOS).strip()
            spec = d["spec"].removesuffix(NO_PHOTOS).strip()
            if len(spec) <= 1800:
                pairs.append((terse, spec))
    pairs.sort()
    return random.Random(seed).sample(pairs, k)


GENERIC_FONTS = re.compile(r"\b(monospace|fixed-width|system[- ]ui|ui-\w+|Courier( New)?|Arial|Helvetica|"
                           r"Georgia|Times New Roman|Verdana)\b", re.I)


def problems(request: str, spec: str) -> list[str]:
    """Checks prompt wording didn't reliably enforce: client's proper nouns kept, real Google Fonts only."""
    nouns = {w.strip(",.") for w in request.split()[1:] if w[:1].isupper() and w.lower() != "i"}
    out = [f"keep the client's name '{n}' word for word" for n in sorted(nouns) if n not in spec]
    out += [f"'{m.group(0)}' is not a Google Fonts family; name a real one (e.g. IBM Plex Mono, Space Mono)"
            for m in GENERIC_FONTS.finditer(spec)]
    return out


def chat(messages: list[dict], temperature: float, num_ctx: int = 8192, raw: bool = False) -> str:
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False, "think": False,
                       "options": {"temperature": temperature, "num_ctx": num_ctx}}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1200) as resp:
        text = json.loads(resp.read())["message"]["content"]
    if raw:
        return text
    text = re.sub(r"\*\*|`|^#+\s*", "", text, flags=re.M).strip()  # it occasionally slips into markdown
    return " ".join(text.split())


def write_spec(request: str, shots: list[tuple[str, str]], temperature: float, retries: int = 2) -> str:
    messages = [{"role": "system", "content": GEMMA_SYSTEM}]
    for terse, spec in shots:
        messages += [{"role": "user", "content": terse}, {"role": "assistant", "content": spec}]
    messages.append({"role": "user", "content": request})
    spec = chat(messages, temperature)
    for _ in range(retries):
        issues = problems(request, spec)
        if not issues:
            break
        print(f"   retry: {'; '.join(issues)}", file=sys.stderr)
        messages += [{"role": "assistant", "content": spec},
                     {"role": "user", "content": "Rewrite the whole spec in the same style, fixing: "
                                                 + "; ".join(issues) + "."}]
        spec = chat(messages, temperature)
    return spec


def prompt_record(rid: str, user: str) -> dict:
    return {"id": rid, "messages": [{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": f"{user}\n\n{NO_PHOTOS}"}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?", help="one-line website request")
    ap.add_argument("--ab", help="text file, one request per line → raw.jsonl + gemma.jsonl")
    ap.add_argument("--out", default=str(ROOT / "dataset" / "runs" / "ab"))
    ap.add_argument("--shots", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--temperature", type=float, default=0.7)
    args = ap.parse_args()

    def shots_for(request: str):  # a different trio per request, or every spec copies one mood
        return few_shot_pairs(args.shots, f"{args.seed}:{request}")

    if args.request:
        print(write_spec(args.request, shots_for(args.request), args.temperature))
        return
    if not args.ab:
        sys.exit("give a request or --ab FILE")

    requests = [l.strip() for l in Path(args.ab).read_text().splitlines() if l.strip() and not l.startswith("#")]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "raw.jsonl").open("w") as raw, (out / "gemma.jsonl").open("w") as gem:
        for i, req in enumerate(requests, 1):
            rid = f"ab-{i:02d}"
            t0 = time.time()
            spec = write_spec(req, shots_for(req), args.temperature)
            raw.write(json.dumps(prompt_record(rid, req)) + "\n")
            gem.write(json.dumps({**prompt_record(rid, spec), "request": req}) + "\n")
            print(f"{rid} ({time.time() - t0:.0f}s, {len(spec.split())} words) {req}\n   → {spec[:160]}…")
    print(f"Wrote {out}/raw.jsonl and {out}/gemma.jsonl ({len(requests)} prompts each)")


if __name__ == "__main__":
    main()
