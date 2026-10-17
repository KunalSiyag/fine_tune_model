#!/usr/bin/env python3
"""Extract a machine-readable design system ("design DNA") from each template.

Reads index.html + style.css (+ inline <style>) and writes
dataset/design_systems/<slug>.json with:

  tokens      CSS custom properties from :root (colors, fonts, radii…)
  fonts       Google Fonts families + the role each font var plays
  palette     most-used colours (hex-normalised), with counts
  radii       distinct border-radius values (shape language)
  type_scale  clamp()/px font sizes used for headings
  libs        CDN libraries (gsap, lenis, three…)
  sections    ordered page outline: tag#id.class → first heading text
  motion      motion/interaction techniques detected in JS + CSS

This JSON is used two ways:
  1. as conditioning context when generating new pages of the same site
     (so the teacher — and later the student — stays on-system)
  2. as a compact "design brief" inside training prompts
"""
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "dataset" / "corpus" / "templates"
DST = ROOT / "dataset" / "design_systems"

HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]+)")
ROOT_BLOCK = re.compile(r":root\s*\{([^}]*)\}", re.S)

MOTION = {
    "gsap": r"\bgsap\.", "scrolltrigger": r"ScrollTrigger", "lenis-smooth-scroll": r"\bLenis\b",
    "three.js": r"\bTHREE\.", "canvas-2d": r"getContext\(['\"]2d", "webgl": r"getContext\(['\"]webgl",
    "intersection-reveal": r"IntersectionObserver", "parallax": r"parallax", "marquee": r"marquee",
    "split-text": r"split|\.ch\b|chars", "typewriter": r"typewriter|typed", "magnetic-buttons": r"magnetic",
    "tilt-cards": r"tilt", "custom-cursor": r"cursor", "counters": r"counter|countUp|count-up",
    "filters": r"filter", "tabs/toggle": r"toggle|tab", "theme-toggle": r"data-theme|theme",
    "drag": r"pointerdown|mousedown|drag", "audio": r"AudioContext", "svg-anim": r"stroke-dash",
    "view-transitions": r"startViewTransition", "keyframes": r"@keyframes",
}


def norm_hex(h: str) -> str:
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h[:7]


class Outline(HTMLParser):
    """Collect top-level landmark sections and their first heading."""
    LANDMARKS = {"header", "nav", "section", "footer", "main", "aside", "article"}

    def __init__(self):
        super().__init__()
        self.items, self.stack, self.cur, self.in_h = [], [], None, False
        self.fonts, self.libs, self.title = [], [], ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "fonts.googleapis.com/css" in (a.get("href") or ""):
            self.fonts += [f.split(":")[0].replace("+", " ")
                           for f in re.findall(r"family=([^&]+)", a["href"])]
        if tag == "script" and a.get("src", "").startswith("http"):
            self.libs.append(re.sub(r"^https?://", "", a["src"]))
        if tag == "title":
            self._in_title = True
        if tag in self.LANDMARKS and tag != "main":
            depth = sum(1 for t in self.stack if t in self.LANDMARKS - {"main"})
            if depth == 0:
                cls = ".".join((a.get("class") or "").split()[:2])
                self.cur = {"el": tag + (f"#{a['id']}" if a.get("id") else "") + (f".{cls}" if cls else ""),
                            "heading": ""}
                self.items.append(self.cur)
        if tag in {"h1", "h2", "h3"} and self.cur is not None and not self.cur["heading"]:
            self.in_h = True
        if tag not in {"br", "img", "input", "meta", "link", "hr", "source", "path", "circle", "rect", "line", "use"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in {"h1", "h2", "h3"}:
            self.in_h = False
        if tag == "title":
            self._in_title = False
        while self.stack:
            t = self.stack.pop()
            if t == tag:
                break

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()
        if self.in_h and self.cur is not None:
            self.cur["heading"] = (self.cur["heading"] + " " + data.strip()).strip()[:80]


def extract(d: Path) -> dict:
    html = (d / "index.html").read_text(errors="ignore")
    css = "\n".join(p.read_text(errors="ignore") for p in d.glob("*.css"))
    css += "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    js = "\n".join(p.read_text(errors="ignore") for p in d.glob("*.js"))
    js += "\n".join(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", html, re.S))

    tokens = {}
    for block in ROOT_BLOCK.findall(css):
        for k, v in VAR.findall(block):
            tokens.setdefault(k, " ".join(v.split()))

    colors = Counter(norm_hex(h) for h in HEX.findall(css + html))
    colors.update("#%02x%02x%02x" % tuple(int(x) for x in m) for m in RGB.findall(css))
    radii = Counter(v.strip() for v in re.findall(r"border-radius\s*:\s*([^;}]+)", css))
    sizes = re.findall(r"font-size\s*:\s*(clamp\([^;}]+\)|\d+(?:\.\d+)?(?:px|rem|vw))", css)
    big = sorted({s for s in sizes if s.startswith("clamp")}, key=len)[:8]

    o = Outline()
    o.feed(html)
    font_roles = {k: v for k, v in tokens.items() if re.search(r"font|display|serif|sans|mono|hand", k)}
    corpus = css + js
    motion = sorted(k for k, pat in MOTION.items() if re.search(pat, corpus, re.I))

    meta = {}
    if (d / "template.json").exists():
        meta = json.loads((d / "template.json").read_text())

    return {
        "slug": d.name,
        "title": meta.get("title") or o.title,
        "description": meta.get("description", ""),
        "tokens": tokens,
        "fonts": sorted(set(o.fonts)),
        "font_roles": font_roles,
        "palette": [{"hex": h, "count": n} for h, n in colors.most_common(10)],
        "radii": [r for r, _ in radii.most_common(6)],
        "type_scale": big,
        "libs": o.libs,
        "sections": [i for i in o.items if i["el"]],
        "motion": motion,
        "size": {"html": len(html), "css": len(css), "js": len(js)},
    }


def main():
    DST.mkdir(parents=True, exist_ok=True)
    n = 0
    for d in sorted(SRC.iterdir()):
        if (d / "index.html").exists():
            ds = extract(d)
            (DST / f"{d.name}.json").write_text(json.dumps(ds, indent=2))
            n += 1
    print(f"{n} design systems → {DST}")


if __name__ == "__main__":
    main()
