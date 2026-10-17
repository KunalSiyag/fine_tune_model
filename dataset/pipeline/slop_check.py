#!/usr/bin/env python3
"""Heuristic "AI slop" detector for HTML/CSS/JS pages.

Not a replacement for human taste — a cheap filter that catches the
tell-tale signatures of default LLM / template-kit output, so the expensive
review time goes to borderline pages.

Each signal adds to `slop` (bad) or `craft` (good). Final verdict:
    reject  if slop >= 4            (or any hard signal, e.g. lorem ipsum)
    review  if slop >= 2 or craft < 3
    keep    otherwise

Usage:
    python3 dataset/pipeline/slop_check.py dataset/sites/*/*.html
    python3 dataset/pipeline/slop_check.py --jsonl dataset/raw/public/websight_sample.jsonl --field text
    python3 dataset/pipeline/slop_check.py --dir dataset/corpus/templates   # index.html + linked css/js
"""
import argparse
import colorsys
import json
import re
import sys
from pathlib import Path

GENERIC_FONTS = {"inter", "roboto", "open sans", "poppins", "montserrat", "lato", "arial", "helvetica",
                 "system-ui", "-apple-system", "segoe ui", "sans-serif", "nunito", "source sans pro"}
BUZZ = ["unlock the power", "seamless", "elevate your", "revolutioniz", "supercharge", "game-chang",
        "cutting-edge", "next-level", "empower", "unleash", "transform your", "take your .* to the next",
        "all-in-one", "harness the", "streamline your", "in today's fast-paced", "lorem ipsum",
        "your journey", "boost your productivity", "effortless"]
TAILWIND_DEFAULTS = {"#6366f1", "#4f46e5", "#8b5cf6", "#7c3aed", "#a855f7", "#3b82f6", "#2563eb",
                     "#ec4899", "#667eea", "#764ba2", "#4338ca", "#818cf8"}
EMOJI = re.compile("[\U0001F300-\U0001FAFF]")  # pictographs only — ✦ ★ → ✓ are typography
HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def hue_sat(hexv: str):
    h = hexv.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, ss, ll


def score(html: str, css: str = "", js: str = "") -> dict:
    allcss = css + "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I))
    alljs = js + "\n".join(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", html, re.S | re.I))
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    low = text.lower()
    slop, craft, flags = 0.0, 0.0, []

    # --- typography -------------------------------------------------------
    fams = {f.replace("+", " ").split(":")[0].lower()
            for f in re.findall(r"family=([^&\"']+)", html)}
    fams |= {f.strip().strip("'\"").lower()
             for decl in re.findall(r"font-family\s*:\s*([^;}{]+)", allcss) for f in decl.split(",")[:1]}
    fams = {f for f in fams if f and not f.startswith("var(")}
    distinctive = fams - GENERIC_FONTS
    if not distinctive:
        slop += 1.5; flags.append("generic-fonts-only")
    else:
        craft += min(2, len(distinctive))

    # --- colour -----------------------------------------------------------
    hexes = {("#" + h.lower()) if len(h) == 6 else "#" + "".join(c * 2 for c in h.lower())
             for h in HEX.findall(allcss + html)}
    tw = hexes & TAILWIND_DEFAULTS
    if len(tw) >= 2:
        slop += 1; flags.append(f"tailwind-default-palette({len(tw)})")
    grads = re.findall(r"linear-gradient\(([^;]+)", allcss + html)
    purple = 0
    for g in grads:
        hs = [hue_sat("#" + h) for h in HEX.findall(g)]
        if sum(1 for hh, ss, ll in hs if 230 <= hh <= 300 and ss > .45 and .25 < ll < .8) >= 1 and len(hs) >= 2:
            purple += 1
    if purple:
        slop += min(1.5, .75 * purple); flags.append(f"purple-gradient x{purple}")
    if re.search(r"--[\w-]+\s*:", allcss):
        craft += 1  # tokenised palette

    # --- copy -------------------------------------------------------------
    hits = [b for b in BUZZ if re.search(b, low)]
    if "lorem ipsum" in hits:
        slop += 4; flags.append("LOREM")
    if len(hits) >= 2:
        slop += min(2, .5 * len(hits)); flags.append("buzzwords:" + ",".join(hits[:4]))

    # --- layout -----------------------------------------------------------
    emoji_icons = len(EMOJI.findall(text))
    if emoji_icons >= 3:
        slop += 1; flags.append(f"emoji-icons({emoji_icons})")
    three_up = len(re.findall(r"repeat\(\s*3\s*,\s*(?:1fr|minmax)|grid-cols-3|md:grid-cols-3|lg:grid-cols-3", allcss + html))
    centered_hero = bool(re.search(r"(hero|header)[^{]*\{[^}]*text-align\s*:\s*center", allcss)) or \
        bool(re.search(r"<(section|header|div)[^>]*class=\"[^\"]*text-center[^\"]*\"", html))
    if three_up >= 2 and centered_hero:
        slop += 1; flags.append("centered-hero+3-up-cards")
    if re.search(r"bg-gradient-to-|from-(indigo|purple|violet|blue)-\d00", html):
        slop += .5; flags.append("tailwind-gradient-utilities")

    # --- anti-patterns from briefs/INSPIRATION_VISUAL.md §8 (A-NN) ---------
    gradtext = len(re.findall(r"(?:-webkit-)?background-clip\s*:\s*text", allcss + html))
    if gradtext and re.search(r"(?:linear|radial|conic)-gradient", allcss + html):
        slop += min(1, .5 * gradtext); flags.append(f"gradient-text x{gradtext}")          # A-01
    glass = len(re.findall(r"backdrop-filter\s*:\s*blur", allcss + html))
    if glass >= 3:
        slop += .75; flags.append(f"glass-cards x{glass}")                                 # A-02
    glow = len(re.findall(r"box-shadow\s*:\s*0\s+0\s+\d{2,}px\s+(?:#|rgba?\()", allcss + html))
    if glow >= 3:
        slop += .5; flags.append(f"neon-glow x{glow}")                                      # A-09
    if re.search(r"★★★★★|⭐", text) or len(re.findall(r"class=\"[^\"]*\bstars?\b", html)) >= 3:
        slop += .75; flags.append("star-rating-testimonials")                               # A-08
    if re.search(r"ready to (transform|get started|take|elevate|supercharge)", low):
        slop += .75; flags.append("generic-cta-band")                                       # A-21
    if re.search(r"trusted by (thousands|leading|the world|teams|over)", low):
        slop += .5; flags.append("trusted-by")                                              # A-19
    lm = len(re.findall(r">\s*learn more\s*<", html, re.I))
    if lm >= 3:
        slop += .5; flags.append(f"learn-more x{lm}")                                       # A-23
    if re.search(r"✨", text):
        slop += .5; flags.append("sparkle-badge")                                           # A-15

    # --- craft signals ----------------------------------------------------
    motion = sum(bool(re.search(p, allcss + alljs + html, re.I)) for p in
                 [r"@keyframes", r"IntersectionObserver|ScrollTrigger", r"gsap\.", r"requestAnimationFrame",
                  r"clip-path", r"mix-blend-mode", r"feTurbulence|<canvas|<svg"])
    craft += min(3, motion * .6)
    interactions = len(set(re.findall(r"addEventListener\(\s*['\"](\w+)", alljs)))
    if interactions == 0:
        slop += 1; flags.append("no-interaction")
    craft += min(2, interactions * .4)
    if re.search(r"clamp\(", allcss):
        craft += .5
    if len(text.split()) < 80:
        slop += 1; flags.append("thin-content")

    hard = "LOREM" in flags
    verdict = "reject" if hard or slop >= 4 else "review" if slop >= 2 or craft < 3 else "keep"
    return {"slop": round(slop, 2), "craft": round(craft, 2), "verdict": verdict, "flags": flags,
            "fonts": sorted(distinctive)[:5]}


def load_dir(d: Path, page: str = "index.html"):
    html = (d / page).read_text(errors="ignore")
    css = "".join((d / h).read_text(errors="ignore") for h in re.findall(r'href="\.?/?([\w./-]+\.css)"', html)
                  if (d / h).exists())
    js = "".join((d / s).read_text(errors="ignore") for s in re.findall(r'src="\.?/?([\w./-]+\.js)"', html)
                 if (d / s).exists())
    return html, css, js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="html files (linked local css/js are included)")
    ap.add_argument("--dir", help="score <dir>/*/index.html")
    ap.add_argument("--jsonl")
    ap.add_argument("--field", default="text")
    ap.add_argument("--out", help="write per-item results as jsonl")
    args = ap.parse_args()

    rows = []
    if args.jsonl:
        for i, line in enumerate(open(args.jsonl)):
            r = json.loads(line)
            rows.append({"id": r.get("id", i), **score(r[args.field])})
    for p in args.paths:
        p = Path(p)
        rows.append({"id": str(p), **score(*load_dir(p.parent, p.name))})
    if args.dir:
        for d in sorted(Path(args.dir).iterdir()):
            if (d / "index.html").exists():
                rows.append({"id": d.name, **score(*load_dir(d))})
    if not rows:
        sys.exit("nothing to score")
    for r in rows:
        print(f"{r['verdict']:<7} slop={r['slop']:<4} craft={r['craft']:<4} {str(r['id'])[:44]:<44} {' '.join(r['flags'])}")
    from collections import Counter
    print("\n", dict(Counter(r["verdict"] for r in rows)))
    if args.out:
        Path(args.out).write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    main()
