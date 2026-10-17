#!/usr/bin/env python3
"""One-liner in, QA-passed website out: the whole product in one command.

    .venv/bin/python dataset/pipeline/make_site.py "a site for my bakery in Pune" --name bakery
    .venv/bin/python dataset/pipeline/make_site.py --batch dataset/briefs/test_oneliners.txt --name test1

Per request:
  1. Gemma 4 (local) writes the art-direction spec (brief_gemma.py, with its checker and retries)
  2. the fine-tuned Qwen3-8B on Tinker writes k drafts in one call (temperature 0.7, 12K cap)
  3. fix_fonts.py repairs Google Fonts URLs; render.py QAs every draft; pick_best.py keeps the best
  4. if no draft passes and the best one only has JS errors, Gemma gets app.js + index.html + the
     browser's errors and returns a fixed app.js, saved as an extra candidate and QA'd like the rest
     (up to --repair-rounds times, each round from the previous repair)

Output: dataset/runs/sites/<name>/<id>/{spec.txt, k1…kN, k*r (repairs), best/} and _renders/.
"""
import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import tinker
from tinker_cookbook import checkpoint_utils
from tinker_cookbook.renderers import get_renderer
from tinker_cookbook.tokenizer_utils import get_tokenizer

import brief_gemma
from train_tinker import MODEL, PRICE, RENDERER, ROOT, load_env_key, sample_all

PIPE = ROOT / "dataset" / "pipeline"
SITES = ROOT / "dataset" / "runs" / "sites"
DEFAULT_RUN = ROOT / "dataset" / "runs" / "sft-v1"

REPAIR_SYSTEM = (
    "You fix JavaScript bugs in a static website. You get index.html, app.js and the errors the "
    "browser reported. Return the corrected app.js in full, wrapped as <file path=\"app.js\">…</file>, "
    "and nothing else. Change only what the errors require: guard lookups of elements that may be "
    "missing, fix syntax, declare each name once. \"Identifier 'top' (or 'name', 'parent', 'self', "
    "'location', 'status', 'length') has already been declared\" means a top-level variable clashes "
    "with a browser global: rename that variable everywhere in app.js. Keep every feature and all behaviour."
)


def slug(text: str, n: int) -> str:
    return f"{n:02d}-" + "-".join(re.findall(r"[a-z0-9]+", text.lower())[:5])


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout


def qa(out: Path, dirs: list[Path] | None = None, judge: bool = False):
    """Render candidates (all, or just the new `dirs`; render.py keys rows by page id) and pick."""
    pages = [str((d / "index.html").relative_to(ROOT)) for d in dirs if (d / "index.html").exists()] if dirs else []
    if dirs is None:
        run(["python3", str(PIPE / "render.py"), "--glob", f"{out.relative_to(ROOT)}/*/k*/index.html",
             "--out", str((out / "_renders").relative_to(ROOT))])
    elif pages:
        run(["python3", str(PIPE / "render.py"), *pages, "--out", str((out / "_renders").relative_to(ROOT))])
    print(run(["python3", str(PIPE / "pick_best.py"), str(out), str(out / "_renders"), *(["--judge"] if judge else [])]))
    return json.loads((out / "_renders" / "best.json").read_text())


def drafts(out: Path, rid: str) -> list[Path]:
    return [d for d in (out / rid).glob("k*") if d.name[1:].isdigit()]


def report_errors(out: Path, rid: str, cand: str) -> list[str]:
    for line in (out / "_renders" / "report.jsonl").open():
        r = json.loads(line)
        if r["id"] == f"{rid}__{cand}__index":
            return r["errors"]
    return []


def repair(cand: Path, errors: list[str], dest: Path) -> bool:
    js, html = cand / "app.js", cand / "index.html"
    if not js.exists():
        return False
    msgs = [{"role": "system", "content": REPAIR_SYSTEM},
            {"role": "user", "content": f'<file path="index.html">\n{html.read_text()}\n</file>\n\n'
                                        f'<file path="app.js">\n{js.read_text()}\n</file>\n\n'
                                        "Browser errors:\n" + "\n".join(f"- {e}" for e in errors)}]
    reply = brief_gemma.chat(msgs, temperature=0.2, num_ctx=32768, raw=True)
    m = re.search(r'<file path="app\.js">\n?(.*?)</file>', reply, re.S)
    if not m:
        return False
    shutil.copytree(cand, dest, dirs_exist_ok=True)
    (dest / "app.js").write_text(m.group(1))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?")
    ap.add_argument("--batch", help="text file, one request per line")
    ap.add_argument("--name", required=True, help="output folder under dataset/runs/sites/")
    ap.add_argument("--run", default=str(DEFAULT_RUN), help="training run whose last sampler checkpoint to use")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=12000)
    ap.add_argument("--repair-rounds", type=int, default=2, help="Gemma JS-repair rounds (0 = off)")
    ap.add_argument("--judge", action="store_true", help="Gemma 4 vision picks between passing drafts")
    ap.add_argument("--spec-seed", type=int, default=7, help="which few-shot examples Gemma sees")
    ap.add_argument("--top-up", type=int, default=3, help="extra drafts for a weak or failing request")
    ap.add_argument("--top-up-rounds", type=int, default=1)
    ap.add_argument("--html-first", action="store_true",
                    help="start the reply with index.html so the JS is written after the elements it selects")
    args = ap.parse_args()
    requests = ([args.request] if args.request else
                [l.strip() for l in Path(args.batch).read_text().splitlines() if l.strip() and not l.startswith("#")])
    out = SITES / args.name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # 1. specs (local, sequential: one GPU)
    rows = []
    for i, req in enumerate(requests, 1):
        rid = slug(req, i)
        spec_file = out / rid / "spec.txt"
        if spec_file.exists():  # re-runs reuse specs, so a crash later doesn't cost Gemma time again
            spec = spec_file.read_text()
        else:
            spec = brief_gemma.write_spec(req, brief_gemma.few_shot_pairs(3, f"{args.spec_seed}:{req}"), 0.7)
            spec_file.parent.mkdir(parents=True, exist_ok=True)
            spec_file.write_text(spec)
            (out / rid / "request.txt").write_text(req)
        rows.append(brief_gemma.prompt_record(rid, spec))
        print(f"[spec] {rid} ({time.time() - t0:.0f}s)")

    # 2. drafts (Tinker, all requests concurrently)
    load_env_key()
    ckpt = checkpoint_utils.get_last_checkpoint(str(Path(args.run).resolve()), required_key="sampler_path")
    client = tinker.ServiceClient().create_sampling_client(model_path=ckpt.sampler_path)
    renderer = get_renderer(RENDERER, get_tokenizer(MODEL))
    prefix = '<file path="index.html">\n' if args.html_first else ""
    have = {r["id"]: len(drafts(out, r["id"])) for r in rows}
    by_have = {}  # top up to k drafts each; rows with the same count share one batch
    for r in rows:
        if have[r["id"]] < args.k:
            by_have.setdefault(have[r["id"]], []).append(r)
    tokens = []
    for n, todo in by_have.items():
        tokens += asyncio.run(sample_all(client, renderer, todo, args.max_tokens, 0.7, out,
                                         args.k - n, prefix, start=n))
        print(f"[drafts] {len(todo)} requests × {args.k - n} new (k{n + 1}…k{args.k})")
    print(f"[drafts] {sum(tokens)} tokens ≈ ${sum(tokens) * PRICE['sample'] / 1e6:.2f}")

    # 3. fonts + QA (only candidates without a report row, so a re-run doesn't re-render everything)
    report = out / "_renders" / "report.jsonl"
    done = {json.loads(l)["id"] for l in report.open()} if report.exists() else set()
    fresh = [d for d in out.glob("*/k*") if f"{d.parent.name}__{d.name}__index" not in done]
    print(run(["python3", str(PIPE / "fix_fonts.py"), *map(str, fresh)]))
    best = qa(out, fresh)

    # 4. Gemma repairs the JS of requests with no passing draft; a fix often exposes the next error,
    #    so each round starts from the previous round's best (k2 → k2r → k2rr)
    for _ in range(args.repair_rounds):
        repaired, new = 0, []
        for rid, v in best["per_prompt"].items():
            js_errors = [e for e in v["errors"] if e.startswith("pageerror")]
            if v["pass"] or not js_errors or len(js_errors) != len(v["errors"]):
                continue  # only pure-JS failures; layout or network problems aren't Gemma's to fix
            src = v["best"]
            while (out / rid / f"{src}r").exists():  # a failed repair ties with its source; extend the chain
                src += "r"
            if src != v["best"]:
                js_errors = [e for e in report_errors(out, rid, src) if e.startswith("pageerror")] or js_errors
            dest = out / rid / f"{src}r"
            if repair(out / rid / src, js_errors, dest):
                repaired += 1
                new.append(dest)
                print(f"[repair] {rid}: {src} → {dest.name}  ({js_errors[0][:80]})")
        if not repaired:
            break
        best = qa(out, new)

    # 5. Gemma judges taste between passing drafts; a request whose pick fails or looks weak
    #    (< 6/10) gets --top-up more drafts, up to --top-up-rounds times
    if args.judge:
        best = qa(out, [], judge=True)
        for _ in range(args.top_up_rounds):
            weak = [r for r in rows if not best["per_prompt"][r["id"]]["pass"]
                    or best["per_prompt"][r["id"]]["judge"].get(best["per_prompt"][r["id"]]["best"], {}).get("score", 0) < 6]
            if not weak:
                break
            n = {r["id"]: len(drafts(out, r["id"])) for r in weak}
            for start in sorted(set(n.values())):
                group = [r for r in weak if n[r["id"]] == start]
                tokens += asyncio.run(sample_all(client, renderer, group, args.max_tokens, 0.7, out,
                                                 args.top_up, prefix, start=start))
            new = [out / r["id"] / f"k{n[r['id']] + j}" for r in weak for j in range(1, args.top_up + 1)]
            print(f"[top-up] {len(weak)} weak or failing requests × {args.top_up} drafts")
            print(run(["python3", str(PIPE / "fix_fonts.py"), *map(str, new)]))
            best = qa(out, new, judge=True)

    passed = sum(v["pass"] for v in best["per_prompt"].values())
    good = sum(v["pass"] and v.get("judge", {}).get(v["best"], {}).get("score", 0) >= 6
               for v in best["per_prompt"].values())
    print(f"\n{passed}/{len(rows)} requests have a passing site"
          f"{f', {good} judged good (≥6/10)' if args.judge else ''} ({time.time() - t0:.0f}s, "
          f"Tinker ≈ ${sum(tokens) * PRICE['sample'] / 1e6:.2f}). Pages: {out.relative_to(ROOT)}/<id>/best/index.html")


if __name__ == "__main__":
    sys.exit(main())
