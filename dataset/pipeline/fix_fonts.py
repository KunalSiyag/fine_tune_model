#!/usr/bin/env python3
"""Repair Google Fonts css2 URLs the model got wrong, in place, before render.py runs.

    python3 dataset/pipeline/fix_fonts.py dataset/runs/sft-v1/samples-gemma3/*/k*

The fine-tuned model often asks for axes a family doesn't have (Montserrat:wdth, Poppins:opsz) or
glues two families together without '&family='; Google answers 400 and the page loses its type.
Each family spec is checked against fonts.googleapis.com; a rejected one is replaced by the first
accepted fallback that keeps its weight range and italics, and a family Google doesn't have is
dropped. Prints every change so the fix is visible, never silent.
"""
import argparse
import re
import sys
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

CSS2 = "https://fonts.googleapis.com/css2?"
URL_RE = re.compile(r"https://fonts\.googleapis\.com/css2\?[^\"')\s>]+")


@lru_cache(maxsize=None)
def accepted(family_spec: str) -> bool:
    req = urllib.request.Request(f"{CSS2}family={family_spec}&display=swap",
                                 headers={"User-Agent": "Mozilla/5.0"})  # UA picks woff2 CSS, like a browser
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False


def requested_weights(axes: str) -> list[int]:
    """'ital,opsz,wght@0,9..144,300..600;1,9..144,400' → [300, 600, 400]: only the wght column."""
    tags, _, values = axes.partition("@")
    tags = tags.split(",")
    if "wght" not in tags:
        return []
    col = tags.index("wght")
    weights = []
    for tup in values.split(";"):
        parts = tup.split(",")
        if len(parts) == len(tags):
            weights += [int(n) for n in re.findall(r"\d+", parts[col]) if 100 <= int(n) <= 1000]
    return weights


def fallbacks(spec: str) -> list[str]:
    name, _, axes = spec.partition(":")
    weights = requested_weights(axes) or [400, 700]
    lo, hi = min(weights), max(weights)
    rng = f"{lo}..{hi}" if lo != hi else str(lo)
    ital = "ital" in axes.split("@")[0]
    out = []
    if ital:
        out += [f"{name}:ital,wght@0,{rng};1,{rng}",
                f"{name}:ital,wght@" + ";".join([f"0,{w}" for w in sorted(set(weights))] + [f"1,{lo}"])]
    out += [f"{name}:wght@{rng}", f"{name}:wght@" + ";".join(map(str, sorted(set(weights)))), name]
    return out


def split_families(query: str) -> list[str]:
    fams = [p[len("family="):] for p in query.split("&") if p.startswith("family=")]
    out = []
    for f in fams:  # 'Bodoni+Moda:opsz@6..96;Fraunces:ital,wght@…' — a missing &family=
        out += re.split(r";(?=[A-Z][A-Za-z0-9+]*:)", f)
    return out


def fix_url(url: str) -> tuple[str, list[str]]:
    query = url[len(CSS2):].replace("&amp;", "&")
    fixed, notes = [], []
    for spec in split_families(query):
        if accepted(spec):
            fixed.append(spec)
            continue
        good = next((c for c in fallbacks(spec) if accepted(c)), None)
        notes.append(f"{spec} → {good or 'dropped (not on Google Fonts)'}")
        if good:
            fixed.append(good)
    if not notes:
        return url, []
    amp = "&amp;" if "&amp;" in url else "&"
    return CSS2 + amp.join([f"family={f}" for f in fixed] + ["display=swap"]), notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="page folders (their .html and .css files are edited)")
    args = ap.parse_args()
    changed = 0
    for d in map(Path, args.dirs):
        for f in [*d.glob("*.html"), *d.glob("*.css")]:
            text = f.read_text()
            new = text
            for url in set(URL_RE.findall(text)):
                fixed, notes = fix_url(url)
                if notes:
                    new = new.replace(url, fixed)
                    print(f"{f}:\n   " + "\n   ".join(notes))
            if new != text:
                f.write_text(new)
                changed += 1
    print(f"{changed} file(s) changed", file=sys.stderr)


if __name__ == "__main__":
    main()
