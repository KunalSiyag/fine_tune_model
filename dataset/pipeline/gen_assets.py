#!/usr/bin/env python3
"""Generate images for any folder that has an assets.json (dataset sites,
synthetic templates…) — the same free Pollinations API that
scripts/generate-assets.py uses, without needing the website_templates/ layout.

assets.json format (identical to the templates'):
    {"style": "...", "assets": [{"name": "about-team.jpg", "prompt": "...",
      "width": 1600, "height": 900, "seed": 301, "model": "flux"}]}

Usage:
    python3 dataset/pipeline/gen_assets.py dataset/sites/12-ember-restaurant
    python3 dataset/pipeline/gen_assets.py <dir> --only about-team.jpg --force

Writes <dir>/assets/<name>. Existing files are skipped unless --force.

The free tier allows ~1 image per 30-60 s per IP and answers 402 otherwise,
so every process takes a global lock (one request in flight machine-wide)
and backs off on 402. Many agents can call this at once; they just queue.
"""
import argparse
import fcntl
import importlib.util
import time
import urllib.error
import urllib.request
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ga", ROOT / "scripts" / "generate-assets.py")
ga = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ga)


LOCK = ROOT / "dataset" / ".pollinations.lock"


def fetch(url: str, tries: int = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "asset-pipeline/1.0"})
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        delay = 20
        for _ in range(tries):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = r.read()
                if len(data) > 5000:
                    return data
            except urllib.error.HTTPError as e:
                if e.code not in (402, 429, 500, 502, 503):
                    raise
            except Exception:
                pass
            time.sleep(delay)
            delay = min(delay + 15, 90)
    raise RuntimeError(f"gave up after {tries} tries: {url[:100]}")


def one(a: dict, out: Path) -> str:
    import urllib.parse
    params = urllib.parse.urlencode({"width": a["width"], "height": a["height"], "seed": a.get("seed", 1),
                                     "model": a.get("model", "flux"), "nologo": "true"})
    url = f"{ga.POLLINATIONS}/prompt/{urllib.parse.quote(a['prompt'])}?{params}"
    raw = fetch(url)
    kb = ga.save_jpeg(raw, out / a["name"], a["width"], a["height"])
    return f"{a['name']} {kb}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=1)  # free tier: 1 concurrent request
    args = ap.parse_args()

    d = Path(args.dir)
    spec = json.loads((d / "assets.json").read_text())
    out = d / "assets"
    out.mkdir(exist_ok=True)
    todo = [a for a in spec["assets"]
            if (not args.only or a["name"] in args.only) and (args.force or not (out / a["name"]).exists())]
    if not todo:
        print("all assets present")
        return 0
    failed = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, a, out): a for a in todo}
        for f, a in futs.items():
            try:
                print("ok  ", f.result(), flush=True)
            except Exception as e:
                failed += 1
                print("FAIL", a["name"], str(e)[:120], flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
