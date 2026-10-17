#!/usr/bin/env python3
"""Check that a site's header/nav and footer are identical on every page
(SPEC §2 rule 2) and that nav links resolve to real files.

    python3 dataset/pipeline/check_chrome.py dataset/sites/ember
    python3 dataset/pipeline/check_chrome.py dataset/sites/ember --sync   # copy index.html's chrome to every page

Normalisation before comparing: aria-current attributes are removed
(they're expected to move), whitespace is collapsed.
--sync rewrites each page's chrome with index.html's, then re-applies
aria-current="page" on the link to that page (if present in the nav).
"""
import argparse
import re
import sys
from pathlib import Path

BLOCKS = ("header", "footer")


def block(html: str, tag: str):
    m = re.search(rf"<{tag}\b.*?</{tag}>", html, re.S)
    return m.group(0) if m else None


def norm(s: str) -> str:
    s = re.sub(r'\s+aria-current="[^"]*"', "", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--sync", action="store_true")
    args = ap.parse_args()
    d = Path(args.site)
    home = (d / "index.html").read_text()
    ref = {t: block(home, t) for t in BLOCKS}
    ref = {t: b for t, b in ref.items() if b}
    if not ref:
        sys.exit("index.html has no <header> or <footer>")
    bad = 0
    for page in sorted(d.glob("*.html")):
        html = page.read_text()
        for tag, rb in ref.items():
            pb = block(html, tag)
            if pb is None or norm(pb) != norm(rb):
                if args.sync and pb is not None:
                    new = re.sub(r'\s+aria-current="[^"]*"', "", rb)
                    new = re.sub(rf'(<a\b[^>]*href="(?:\./)?{re.escape(page.name)}")', r'\1 aria-current="page"', new, count=1)
                    html = html.replace(pb, new)
                    page.write_text(html)
                    print(f"synced  {page.name} <{tag}>")
                else:
                    bad += 1
                    print(f"DIFFERS {page.name} <{tag}>" + (" (missing)" if pb is None else ""))
        # nav links must resolve
        for href in re.findall(r'href="(?:\./)?([\w-]+\.html)(?:#[\w-]*)?"', html):
            if not (d / href).exists():
                bad += 1
                print(f"DEAD    {page.name} → {href}")
    print("chrome OK" if not bad else f"{bad} problem(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
