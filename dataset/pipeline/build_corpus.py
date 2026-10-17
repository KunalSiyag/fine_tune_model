#!/usr/bin/env python3
"""Copy website_templates/ into the training corpus, normalised and fixed.

The originals stay untouched; dataset/corpus/templates/<slug>/ is what the
dataset builder reads. Fixes applied here are bugs we never want the model
to learn:

  - reduced-motion: `gsap.globalTimeline.pause()` freezes reveal tweens at
    opacity:0 → blank page. Replaced with "jump every tween to its end".

Then files from dataset/overrides/templates/<slug>/ are copied on top
(agent/hand fixes such as a mobile nav — see briefs/MOBILENAV_AGENT.md).

Skipped: stubs (no real content) and near-duplicates listed in SKIP.

Usage: python3 dataset/pipeline/build_corpus.py
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "website_templates"
DST = ROOT / "dataset" / "corpus" / "templates"
# hand/agent-fixed files that replace the copied originals (e.g. adding a
# mobile nav). Same relative layout as the template folder.
OVERRIDES = ROOT / "dataset" / "overrides" / "templates"

SKIP = {
    "website-06-meridian-watch",  # scaffold stub, not built yet
    "01-norish-poster",           # duplicate of norish-interactive-poster
}
KEEP_EXT = {".html", ".css", ".js", ".json", ".md", ".jpg", ".jpeg", ".png", ".webp", ".svg", ".avif"}

# timeScale on the global timeline also applies to tweens created later, so
# every reveal still happens — instantly — and nothing is left at opacity:0.
REDUCED_FIX = ("if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){ "
               "gsap.globalTimeline.timeScale(1000); }")
# CSS safety net for class-toggled reveals (.reveal → .in via IntersectionObserver)
REDUCED_CSS = ("\n@media (prefers-reduced-motion: reduce){"
               ".reveal,.reveal-up,[data-reveal],h2 .ch{opacity:1!important;transform:none!important}"
               "*,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important;"
               "animation-iteration-count:1!important}}\n")
PAUSE_RE = re.compile(r"if\s*\(\s*window\.matchMedia\('\(prefers-reduced-motion: reduce\)'\)\.matches\s*\)\s*\{"
                      r"([^{}]*?)gsap\.globalTimeline(?:\.progress\(1\))?\.pause\(\);\s*\}")


def fix_js(text: str) -> tuple[str, int]:
    def repl(m):
        extra = m.group(1).strip()  # e.g. "hero.auto = stage.auto = 0;"
        return REDUCED_FIX if not extra else REDUCED_FIX.replace("{ ", "{ " + extra + " ", 1)
    return PAUSE_RE.subn(repl, text)


def main():
    final, tmp = DST, DST.with_name("templates.tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    build(tmp)
    # swap atomically-ish so readers (running agents) never see a half-built corpus
    old = DST.with_name("templates.old")
    if final.exists():
        final.rename(old)
    tmp.rename(final)
    if old.exists():
        shutil.rmtree(old)


def build(DST: Path):
    n_fix = n_ov = 0
    kept = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir() or not (d / "index.html").exists() or d.name in SKIP:
            continue
        out = DST / d.name
        for f in d.rglob("*"):
            if f.is_file() and f.suffix.lower() in KEEP_EXT and f.name not in {"preview.jpg", "preview.png"}:
                t = out / f.relative_to(d)
                t.parent.mkdir(parents=True, exist_ok=True)
                if f.suffix == ".js":
                    text, k = fix_js(f.read_text())
                    n_fix += k
                    t.write_text(text)
                elif f.suffix == ".css" and f.name == "style.css":
                    text = f.read_text()
                    if "prefers-reduced-motion" not in text:
                        text += REDUCED_CSS
                    t.write_text(text)
                else:
                    shutil.copy2(f, t)
        ov = OVERRIDES / d.name
        if ov.exists():
            for f in ov.rglob("*"):
                if f.is_file():
                    t = out / f.relative_to(ov)
                    t.parent.mkdir(parents=True, exist_ok=True)
                    text_or_bytes = f.read_bytes()
                    if f.suffix == ".js":
                        text, k = fix_js(text_or_bytes.decode())
                        n_fix += k
                        t.write_text(text)
                    else:
                        t.write_bytes(text_or_bytes)
            n_ov += 1
        kept.append(d.name)
    print(f"{len(kept)} templates → {DST}  ({n_fix} reduced-motion fixes, {n_ov} with overrides)")


if __name__ == "__main__":
    main()
