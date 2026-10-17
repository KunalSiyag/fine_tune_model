#!/usr/bin/env python3
"""Programmatic DPO negatives: chosen = a good page, rejected = the same page
with ONE controlled defect. Because everything else is identical, the
preference signal isolates exactly the thing we want the model to learn.

Mutations
  destyled        art direction stripped: every colour remapped to the
                  Tailwind-default slate/indigo palette, every font → Inter,
                  every radius → 12px, grain/cursor/texture removed.
                  (structure + copy unchanged → teaches *taste*, not content)
  reduced-motion  the classic GSAP bug re-introduced: timeline paused while
                  elements sit at opacity:0 → blank page for some users
  anchor-nav      (site pages only) nav links rewritten to #anchors that
                  don't exist on this page → broken multi-page navigation

    python3 dataset/pipeline/make_negatives.py            # → dataset/pairs/auto-*/
Writes pairs/<id>/{pair.json, chosen/, rejected/} (see SPEC §5).
"""
import colorsys
import json
import re
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DS = ROOT / "dataset"
PAIRS = DS / "pairs"

GENERIC_ACCENTS = ["#6366f1", "#8b5cf6", "#ec4899", "#3b82f6"]
HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
INTER = ('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" '
         'rel="stylesheet" />')


def remap_hex(m: re.Match, state: dict) -> str:
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    if ss > .35 and .2 < ll < .85:  # an accent colour → next generic accent (stable per source colour)
        acc = state.setdefault(h.lower(), GENERIC_ACCENTS[len(state) % len(GENERIC_ACCENTS)])
        return acc
    if ll < .12:
        return "#0f172a"
    if ll < .3:
        return "#1e293b"
    if ll > .93:
        return "#ffffff"
    if ll > .8:
        return "#f1f5f9"
    return "#64748b" if ll < .55 else "#94a3b8"


def destyle_css(css: str, state: dict) -> str:
    css = HEX.sub(lambda m: remap_hex(m, state), css)
    css = re.sub(r"font-family\s*:\s*[^;}]+", "font-family:'Inter',system-ui,sans-serif", css)
    css = re.sub(r"(--[\w-]*(?:font|display|serif|sans|mono|hand)[\w-]*\s*:\s*)[^;}]+",
                 r"\1'Inter',system-ui,sans-serif", css)
    css = re.sub(r"border-radius\s*:\s*[^;}]+", "border-radius:12px", css)
    css = re.sub(r"letter-spacing\s*:\s*-?[\d.]+(em|px)", "letter-spacing:normal", css)
    css = re.sub(r"text-transform\s*:\s*uppercase", "text-transform:none", css)
    css = re.sub(r"mix-blend-mode\s*:\s*[^;}]+", "mix-blend-mode:normal", css)
    css += "\n.grain,.noise,.cursor,.cursor-dot,.cursor-ring,[class*=grain],[class*=cursor]{display:none!important}\n"
    return css


def destyle_html(html: str, state: dict) -> str:
    html = re.sub(r'<link[^>]+fonts\.googleapis\.com/css2[^>]*>', INTER, html, count=1)
    html = re.sub(r'<link[^>]+fonts\.googleapis\.com/css2[^>]*>', "", html)
    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + destyle_css(m.group(2), state) + m.group(3),
                  html, flags=re.S)
    html = re.sub(r'style="([^"]*)"', lambda m: 'style="' + HEX.sub(lambda x: remap_hex(x, state), m.group(1)) + '"', html)
    return html


def reduced_motion_bug(js: str) -> str | None:
    if "gsap" not in js:
        return None
    new = re.sub(r"gsap\.globalTimeline\.timeScale\(1000\);?", "gsap.globalTimeline.pause();", js)
    if new == js:
        new = js + "\nif(window.matchMedia('(prefers-reduced-motion: reduce)').matches){ gsap.globalTimeline.pause(); }\n"
    return new


def anchor_nav(html: str) -> str | None:
    nav = re.search(r"<(nav|header)\b.*?</\1>", html, re.S)
    if not nav:
        return None
    block = nav.group(0)
    new = re.sub(r'href="(?:\./)?([\w-]+)\.html"', lambda m: f'href="#{m.group(1)}"', block)
    return None if new == block else html.replace(block, new)


def write_pair(pid: str, prompt: str, chosen: dict, rejected: dict, kind: str, source: str):
    d = PAIRS / pid
    if d.exists():
        shutil.rmtree(d)
    for sub, files in (("chosen", chosen), ("rejected", rejected)):
        for name, text in files.items():
            p = d / sub / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
    (d / "pair.json").write_text(json.dumps({
        "prompt": prompt, "rejected_kind": kind, "source": source,
        "files": list(chosen.keys())}, indent=2))


def linked(d: Path, html: str, ext: str) -> list[str]:
    return [r for r in re.findall(r'(?:href|src)="\.?/?([\w./-]+\.%s)"' % ext, html) if (d / r).exists()]


def main():
    n = Counter()
    # --- single-page templates (corpus + synthetic): destyled + reduced-motion
    srcs = []
    for pf in sorted((DS / "corpus" / "prompts").glob("*.json")):
        meta = json.loads(pf.read_text())
        srcs.append((DS / "corpus" / "templates" / meta["slug"], meta, f"templates/{meta['slug']}"))
    for group in ("synthetic", "external"):
        for pf in sorted((DS / group).glob("*/prompts.json")):
            srcs.append((pf.parent, json.loads(pf.read_text()), f"{group}/{pf.parent.name}"))
    tiers = json.loads((DS / "tiers.json").read_text())
    for d, meta, source in srcs:
        if d.name in tiers["B"]:
            continue  # only A-tier pages may be "chosen"
        html = (d / "index.html").read_text()
        css_files, js_files = linked(d, html, "css"), linked(d, html, "js")
        chosen = {f: (d / f).read_text() for f in css_files + js_files}
        chosen["index.html"] = html
        prompt = meta["prompts"]["brief"]
        state = {}
        rej = {f: destyle_css(t, state) if f.endswith(".css") else t for f, t in chosen.items()}
        rej["index.html"] = destyle_html(html, state)
        write_pair(f"auto-destyled-{d.name}", prompt, chosen, rej, "destyled", source)
        n["destyled"] += 1
        for jf in js_files:
            bug = reduced_motion_bug(chosen[jf])
            if bug:
                write_pair(f"auto-rmbug-{d.name}", prompt, chosen, {**chosen, jf: bug}, "reduced-motion", source)
                n["reduced-motion"] += 1
                break

    # --- site pages: off-system (page-specific CSS ignores the site's tokens and
    # fonts, while the shared chrome stays) + anchor-nav
    for sj in sorted((DS / "sites").glob("*/site.json")):
        d = sj.parent
        site = json.loads(sj.read_text())
        for p in site["pages"]:
            if p["file"] == "index.html":
                continue
            html = (d / p["file"]).read_text()
            bad = anchor_nav(html)
            if bad:
                write_pair(f"auto-anchornav-{site['site']}-{p['file'][:-5]}", p["prompts"]["brief"],
                           {p["file"]: html}, {p["file"]: bad}, "anchor-nav", f"sites/{site['site']}")
                n["anchor-nav"] += 1
            state = {}
            write_pair(f"auto-offsystem-{site['site']}-{p['file'][:-5]}", p["prompts"]["brief"],
                       {p["file"]: html}, {p["file"]: destyle_html(html, state)}, "off-system",
                       f"sites/{site['site']}")
            n["off-system"] += 1
    print(dict(n))


if __name__ == "__main__":
    main()
