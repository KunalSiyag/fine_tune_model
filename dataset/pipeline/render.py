#!/usr/bin/env python3
"""Render HTML pages headlessly and run objective QA checks.

For every page: screenshot at desktop / tablet / mobile widths and record
hard failures that no amount of "taste" can excuse:

  - console errors / uncaught exceptions
  - failed network requests (missing local assets, dead CDNs)
  - horizontal overflow at any width (the #1 small-model bug)
  - broken <img> elements
  - near-empty pages (body text < 200 chars)

Usage:
    python3 dataset/pipeline/render.py website_templates/04-flux-saas/index.html ...
    python3 dataset/pipeline/render.py --glob "website_templates/*/index.html" --out dataset/renders
    python3 dataset/pipeline/render.py --glob "dataset/sites/*/*.html" --widths desktop

Desktop shots are full-page; the desktop pass also runs a monkey test
(clicks every button/tab/summary, submits every form empty then filled,
presses Esc) — JS errors during it FAIL the page.

Writes <out>/<id>/<width>.jpg and <out>/report.jsonl (one row per page).
"""
import argparse
import fcntl
import functools
import glob
import http.server
import json
import sys
import threading
from multiprocessing import Pool
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WIDTHS = {"desktop": (1440, 900), "tablet": (820, 1180), "mobile": (390, 844)}

OVERFLOW_JS = """() => {
  const de = document.documentElement;
  const vw = de.clientWidth;
  // offenders: visible elements whose right edge escapes the viewport
  const bad = [], cut = [];
  // content cut off at the right edge by a clipping (not scrolling) ancestor:
  // invisible to the scroll test, so report it separately (warning only)
  const CONTENT = 'input,select,textarea,button,a,label,p,li,h1,h2,h3,h4,h5,h6';
  // any element carrying its own text (a <div> band, a <span> label) counts as content
  const ownText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
  // tickers, marquees and carousels run off the edge on purpose
  const TRACK = /ticker|marquee|track|rail|strip|carousel|slider|reel/i;
  const isTrack = (el, clipper) => {
    for (let n = el; n && n !== clipper.parentElement; n = n.parentElement) {
      if (TRACK.test((n.className && n.className.baseVal !== undefined ? n.className.baseVal : n.className) + ' ' + n.id)) return true;
      const s = getComputedStyle(n);
      // animated marquees, and horizontal tracks moved by a transform (pinned galleries)
      if (s.animationName !== 'none' || (n !== el && s.transform !== 'none')) return true;
    }
    return false;
  };
  for (const el of document.body.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed' || cs.visibility === 'hidden') continue;
    if (r.right > vw + 2 && r.left < vw) {
      // ignore if an ancestor clips it
      let p = el.parentElement, clipped = false;
      while (p && p !== document.body) {
        const o = getComputedStyle(p);
        if (/(hidden|clip|auto|scroll)/.test(o.overflowX)) { clipped = true; break; }
        p = p.parentElement;
      }
      const name = (el.tagName + '.' + [...el.classList].join('.')).slice(0, 60);
      if (!clipped) bad.push(name);
      else if ((el.matches(CONTENT) || ownText(el)) && !el.closest('[aria-hidden="true"],[inert]')
               && /(hidden|clip)/.test(getComputedStyle(p).overflowX)
               && p.getBoundingClientRect().right <= vw + 2 && !isTrack(el, p)) cut.push(name);
    }
  }
  const y = scrollY; scrollTo(99999, y); const sx = scrollX; scrollTo(0, y);
  // overflow:hidden still allows programmatic scrolling; if the root clips,
  // users can't pan sideways — report it as clipped instead of a failure
  const clips = [de, document.body].some(e => /hidden|clip/.test(getComputedStyle(e).overflowX));
  return {scrollX: sx, clipped: clips, scrollW: de.scrollWidth, vw, offenders: [...new Set(bad)].slice(0, 5), cutoff: [...new Set(cut)].slice(0, 5)};
}"""

# characters of text actually visible in the first viewport (opacity chain > .1)
VISIBLE_TEXT_JS = """(whole) => {
  let n = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode, el = t.parentElement;
    if (!el || !t.textContent.trim()) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || (!whole && (r.bottom < 0 || r.top > innerHeight))) continue;
    let op = 1, p = el;
    while (p) { const cs = getComputedStyle(p); op *= parseFloat(cs.opacity);
      if (cs.visibility === 'hidden' || cs.display === 'none') op = 0; p = p.parentElement; }
    if (op > 0.1) n += t.textContent.trim().length;
  }
  return n;
}"""

STATS_JS = """() => ({
  text: document.body.innerText.length,
  imgsBroken: [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src).map(i => i.src).slice(0,5),
  height: document.documentElement.scrollHeight,
  title: document.title,
})"""


# Text that becomes visible at ANY point while scrolling down the page
# (reveals that reverse when scrolled back up still count as visible).
SCROLL_COLLECT_JS = """async (stepMs) => {
  document.documentElement.style.setProperty('scroll-behavior', 'auto', 'important');
  const seen = new Set();
  const grab = () => {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const t = w.currentNode, el = t.parentElement;
      if (!el || seen.has(t) || !t.textContent.trim()) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.bottom < 0 || r.top > innerHeight) continue;
      let op = 1, p = el;
      while (p) { const cs = getComputedStyle(p); op *= parseFloat(cs.opacity);
        if (cs.visibility === 'hidden' || cs.display === 'none') op = 0; p = p.parentElement; }
      if (op > 0.1) seen.add(t);
    }
  };
  const step = Math.max(300, innerHeight * 0.8);
  for (let y = 0; y <= document.body.scrollHeight; y += step) {
    scrollTo(0, y); await new Promise(r => setTimeout(r, stepMs)); grab();
  }
  scrollTo(0, 0);
  let n = 0; seen.forEach(t => n += t.textContent.trim().length); return n;
}"""

# smooth scroll-behavior would swallow programmatic scrollTo steps → reveals never fire
SCROLL_THROUGH = """async () => { document.documentElement.style.setProperty('scroll-behavior', 'auto', 'important');
  for (let y = 0; y < document.body.scrollHeight; y += 700) { scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); } scrollTo(0, 0); }"""

# Monkey test: click every visible button-like control, submit every form empty
# and then filled, press Escape. Any JS error during this is a FAIL; a submit
# nobody handled (page would reload/navigate) is a warning.
GUARD_SUBMIT_JS = """() => { document.addEventListener('submit', e => { if (!e.defaultPrevented) { e.preventDefault();
  window.__unhandledSubmit = (window.__unhandledSubmit || 0) + 1; } }); }"""
FILL_JS = """(form) => { const d = new Date(Date.now() + 30*864e5).toISOString().slice(0,10);
  for (const el of form.querySelectorAll('input, select, textarea')) {
    if (el.disabled || el.type === 'hidden') continue;
    if (el.tagName === 'SELECT') { if (el.options.length > 1) el.selectedIndex = 1; }
    else if (el.type === 'checkbox' || el.type === 'radio') el.checked = true;
    else if (el.type === 'email') el.value = 'ada@example.com';
    else if (el.type === 'number' || el.type === 'range') el.value = el.min && +el.min > 0 ? el.min : '2';
    else if (el.type === 'date') el.value = d;
    else if (el.type === 'tel') el.value = '+44 20 7946 0000';
    else if (el.type === 'time') el.value = '19:30';
    else el.value = el.pattern ? '' : 'Ada Lovelace';
    el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true}));
  } }"""


def interact(page, row):
    errs_before = len(row["errors"])
    page.evaluate(GUARD_SUBMIT_JS)
    sel = "button:not([disabled]), [role=button], [role=tab], summary, input[type=checkbox], input[type=radio]"
    clicked = 0
    for el in page.query_selector_all(sel)[:40]:
        try:
            if el.is_visible():
                el.scroll_into_view_if_needed(timeout=1000)
                el.click(timeout=1200, no_wait_after=True)
                clicked += 1
                page.wait_for_timeout(120)
                page.keyboard.press("Escape")
        except Exception:
            pass  # covered / detached / animating — not a page bug
    for form in page.query_selector_all("form")[:6]:
        try:
            page.evaluate("f => f.requestSubmit ? f.requestSubmit() : f.submit()", form)  # empty → validation path
            page.wait_for_timeout(150)
            page.evaluate(FILL_JS, form)
            page.evaluate("f => { f.noValidate = true; f.requestSubmit ? f.requestSubmit() : f.submit(); }", form)
            page.wait_for_timeout(250)
        except Exception:
            pass
    row["interact"] = {"clicked": clicked, "forms": len(page.query_selector_all("form")),
                       "errors": row["errors"][errs_before:],
                       "unhandledSubmit": page.evaluate("window.__unhandledSubmit || 0")}


def page_id(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT)
    return "__".join(rel.with_suffix("").parts[-3:])


def serve(port: int):
    """Serve the repo root over HTTP — file:// blocks module scripts / fetch()."""
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)  # port 0 → any free port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def check(browser, path: Path, out: Path, widths, full_page: bool, base: str, do_interact: bool = True):
    pid = page_id(path)
    dest = out / pid
    dest.mkdir(parents=True, exist_ok=True)
    row = {"id": pid, "path": str(path.resolve().relative_to(ROOT)), "errors": [], "failed": [], "widths": {}}
    for name in widths:
        w, h = WIDTHS[name]
        ctx = browser.new_context(viewport={"width": w, "height": h})
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and "favicon" not in (m.location or {}).get("url", "")
                and row["errors"].append(m.text[:200]))
        page.on("pageerror", lambda e: row["errors"].append(("pageerror: " + str(e))[:200]))
        page.on("requestfailed", lambda r: r.url.startswith("http")  # a clicked mailto:/tel: isn't a load
                and row["failed"].append(r.url[:200]))
        try:
            page.goto(base + str(path.resolve().relative_to(ROOT)), wait_until="domcontentloaded", timeout=20000)
            page.wait_for_load_state("load", timeout=12000)
        except Exception as e:  # page never reached DOMContentLoaded / load
            row["errors"].append(f"goto: {str(e).splitlines()[0]}"[:200])
        page.wait_for_timeout(600)
        # scroll through once so IntersectionObserver reveals fire before the shot
        page.evaluate(SCROLL_THROUGH)
        page.wait_for_timeout(900)  # let reveal transitions finish
        ov = page.evaluate(OVERFLOW_JS)
        st = page.evaluate(STATS_JS)
        try:
            page.screenshot(path=str(dest / f"{name}.jpg"), type="jpeg", quality=70,
                            full_page=full_page and name == "desktop", timeout=15000)
        except Exception:  # very tall full-page shots can exceed GPU texture limits
            page.screenshot(path=str(dest / f"{name}.jpg"), type="jpeg", quality=70, timeout=15000)
        row["widths"][name] = {"overflow": ov["scrollX"] > 2 and not ov["clipped"],
                               "clippedOverflow": ov["scrollX"] > 2 and ov["clipped"], "offenders": ov["offenders"],
                               "cutoff": ov["cutoff"],
                               "height": st["height"], "imgsBroken": st["imgsBroken"]}
        row["textLen"] = st["text"]
        if name == "desktop":
            row["visibleText"] = page.evaluate(VISIBLE_TEXT_JS, False)
            row["visibleTextDoc"] = page.evaluate(SCROLL_COLLECT_JS, 180)
            if do_interact:
                interact(page, row)
        row["title"] = st["title"]
        ctx.close()
    # reduced-motion users must still see the content (common GSAP bug:
    # elements start at opacity:0 and the timeline is paused, never revealed)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    try:
        page.goto(base + str(path.resolve().relative_to(ROOT)), wait_until="load", timeout=20000)
        page.wait_for_timeout(1200)
        row["visibleTextReduced"] = page.evaluate(VISIBLE_TEXT_JS, False)
        row["visibleTextReducedDoc"] = page.evaluate(SCROLL_COLLECT_JS, 180)
    except Exception:
        row["visibleTextReduced"] = row["visibleTextReducedDoc"] = 0
    ctx.close()
    # first screen AND whole document must stay readable under reduced motion
    row["reducedBlank"] = ((row.get("visibleText", 0) > 40 and row["visibleTextReduced"] < 0.4 * row["visibleText"])
                           or (row.get("visibleTextDoc", 0) > 200
                               and row["visibleTextReducedDoc"] < 0.6 * row["visibleTextDoc"]))
    row["errors"] = sorted(set(row["errors"]))
    row["failed"] = sorted(set(row["failed"]))
    row["pass"] = (not row["errors"] and not row["failed"] and row.get("textLen", 0) > 200 and not row["reducedBlank"]
                   and not any(v["overflow"] or v["imgsBroken"] for v in row["widths"].values()))
    return row


def worker(job):
    """One browser per process; handles a chunk of pages."""
    chunk, out, widths, full_page, base, do_interact = job
    rows = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:  # bundled browser missing → use system Chrome
            browser = p.chromium.launch(channel="chrome")
        for path in chunk:
            try:
                row = check(browser, Path(path), Path(out), widths, full_page, base, do_interact)
            except Exception as e:
                row = {"id": page_id(Path(path)), "path": path, "pass": False, "errors": [f"crash: {e}"[:200]],
                       "failed": [], "widths": {}}
            rows.append(row)
            flag = "PASS" if row["pass"] else "FAIL"
            why = []
            if row["errors"]: why.append(f"{len(row['errors'])} console err")
            if row["failed"]: why.append(f"{len(row['failed'])} failed req")
            if row.get("reducedBlank"): why.append("blank under reduced-motion")
            if row.get("interact", {}).get("errors"): why.append(f"{len(row['interact']['errors'])} err on interaction")
            if row.get("interact", {}).get("unhandledSubmit"): why.append("warn: form submit not handled")
            for n, v in row["widths"].items():
                if v["overflow"]: why.append(f"overflow@{n} {v['offenders'][:2]}")
                if v.get("cutoff"): why.append(f"warn: cut off@{n} {v['cutoff'][:2]}")
            print(f"{flag}  {row['id']:<56} {'; '.join(why)}", flush=True)
        browser.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--glob", action="append", default=[])
    ap.add_argument("--out", default=str(ROOT / "dataset" / "renders"))
    ap.add_argument("--widths", default="desktop,tablet,mobile")
    ap.add_argument("--no-full-page", action="store_true", help="desktop shot = first screen only")
    ap.add_argument("--no-interact", action="store_true", help="skip the click/form monkey test")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--port", type=int, default=0, help="0 = pick a free port (safe for parallel runs)")
    args = ap.parse_args()

    paths = [Path(p) for p in args.paths]
    for g in args.glob:
        paths += [Path(p) for p in sorted(glob.glob(str(ROOT / g) if not Path(g).is_absolute() else g))]
    if not paths:
        sys.exit("no pages given")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    widths = args.widths.split(",")
    srv = serve(args.port)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"

    n = max(1, min(args.jobs, len(paths)))
    chunks = [[str(p) for p in paths[i::n]] for i in range(n)]
    with Pool(n) as pool:
        rows = [r for part in pool.map(worker, [(c, str(out), widths, not args.no_full_page, base, not args.no_interact)
                                                    for c in chunks]) for r in part]

    # report.jsonl is keyed by id: re-rendering a page replaces its old row
    report = out / "report.jsonl"
    with open(out / ".report.lock", "w") as lk:  # parallel agents share report files
        fcntl.flock(lk, fcntl.LOCK_EX)
        old = {}
        if report.exists():
            for line in report.read_text().splitlines():
                r = json.loads(line)
                old[r["id"]] = r
        for r in rows:
            old[r["id"]] = r
        report.write_text("".join(json.dumps(r) + "\n" for r in old.values()))
    ok = sum(r["pass"] for r in rows)
    print(f"\n{ok}/{len(rows)} passed  →  {report}")


if __name__ == "__main__":
    main()
