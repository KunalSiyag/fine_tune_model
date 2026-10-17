#!/usr/bin/env python3
"""Screenshot one section of a page *in a real viewport*, after scrolling to it
step by step so scroll-triggered reveals fire. Full-page captures can show
scroll-linked sections as blank; use this to check them.

    python3 dataset/pipeline/peek.py dataset/sites/ember/menu.html ".pairings" out.jpg [--width 390]
"""
import argparse
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("selector")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    args = ap.parse_args()

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rel = Path(args.page).resolve().relative_to(ROOT)
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": args.width, "height": args.height})
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/{rel}")
        pg.wait_for_timeout(800)
        pg.evaluate("document.documentElement.style.setProperty('scroll-behavior','auto','important')")
        y = pg.evaluate("s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top + scrollY - 80 : -1 }",
                        args.selector)
        if y < 0:
            raise SystemExit(f"selector not found: {args.selector}")
        for k in range(0, int(y), 300):
            pg.evaluate(f"scrollTo(0,{k})")
            pg.wait_for_timeout(30)
        pg.evaluate(f"scrollTo(0,{y})")
        pg.wait_for_timeout(1500)
        pg.screenshot(path=args.out, type="jpeg", quality=70)
        b.close()
    print(args.out)


if __name__ == "__main__":
    main()
