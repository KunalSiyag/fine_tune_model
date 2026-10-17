#!/usr/bin/env python3
"""Best-of-k with render.py as the judge: keep the candidate that passes QA, report pass@1 vs best-of-k.

    python3 dataset/pipeline/pick_best.py dataset/runs/sft-v1/samples-gemma2 dataset/runs/sft-v1/renders-gemma2

Expects <samples>/<id>/k1 … kN (train_tinker.py sample --k N) rendered into <renders>/report.jsonl.
A candidate that never closed index.html wasn't rendered and counts as a fail, and so does one whose
first desktop screen is a single flat colour (render.py passes those). The winner is copied
to <samples>/<id>/best; the scores go to <renders>/best.json.
"""
import argparse
import base64
import io
import json
import shutil
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageStat


def blank_first_screen(shot: Path) -> bool:
    """render.py counts text in the DOM, so a hero that paints nothing still passes; check the pixels."""
    if not shot.exists():
        return False
    im = Image.open(shot).convert("L")
    return ImageStat.Stat(im.crop((0, 0, im.size[0], min(900, im.size[1])))).stddev[0] < 4


JUDGE = ("You are a strict art director reviewing the first screen of a small-business website. "
         "Score it 1-10 for design quality: clear hierarchy, a confident headline, real content visible, "
         "deliberate palette and type. Score 1-3 if the screen is mostly empty, a repeated pattern, broken, "
         "overlapping or unreadable. Reply as JSON: {\"score\": n, \"reason\": \"<12 words\"}.")


def judge(shot: Path) -> dict:
    """Gemma 4 (local, vision) scores the first desktop screen; render.py can't see taste."""
    im = Image.open(shot)
    im = im.crop((0, 0, im.size[0], min(900, im.size[1]))).resize((960, 600))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=85)
    body = json.dumps({"model": "gemma4:e4b", "stream": False, "think": False, "format": "json",
                       "options": {"temperature": 0, "num_ctx": 4096},
                       "messages": [{"role": "system", "content": JUDGE},
                                    {"role": "user", "content": "Score this first screen.",
                                     "images": [base64.b64encode(buf.getvalue()).decode()]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        verdict = json.loads(json.loads(urllib.request.urlopen(req, timeout=600).read())["message"]["content"])
        return {"score": int(verdict["score"]), "reason": str(verdict.get("reason", ""))}
    except (ValueError, KeyError, TypeError):
        return {"score": 0, "reason": "unparseable verdict"}


def score(row: dict | None) -> tuple:
    """Higher is better: pass, then fewest JS errors / failed requests / overflowing widths, then most text."""
    if row is None:
        return (0, -99, -99, -99, 0)
    overflow = sum(bool(v.get("overflow")) for v in row["widths"].values()) if isinstance(row["widths"], dict) else 0
    return (int(row["pass"]), -len(row["errors"]), -len(row["failed"]), -overflow, row.get("textLen", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("samples")
    ap.add_argument("renders")
    ap.add_argument("--judge", action="store_true", help="Gemma 4 vision picks between passing drafts")
    args = ap.parse_args()
    samples, renders = Path(args.samples), Path(args.renders)

    report = {}
    for line in (renders / "report.jsonl").open():
        r = json.loads(line)
        pid, cand, _ = r["id"].split("__")  # ab-01__k2__index
        if r["pass"] and blank_first_screen(renders / r["id"] / "desktop.jpg"):
            r["pass"], r["errors"] = False, r["errors"] + ["blank first screen"]
        report[(pid, cand)] = r

    cands = defaultdict(list)
    for d in sorted(samples.glob("*/k*")):
        cands[d.parent.name].append(d.name)

    results = {}
    for pid, ks in sorted(cands.items()):
        ranked = sorted(ks, key=lambda c: score(report.get((pid, c))), reverse=True)
        passing = [c for c in ks if report.get((pid, c), {}).get("pass")]
        verdicts = {}
        if args.judge and passing:  # taste decides between drafts that all work
            verdicts = {c: judge(renders / report[(pid, c)]["id"] / "desktop.jpg") for c in passing}
            ranked = sorted(passing, key=lambda c: verdicts[c]["score"], reverse=True) + \
                [c for c in ranked if c not in passing]
        best = ranked[0]
        row = report.get((pid, best))
        results[pid] = {"best": best, "pass": bool(row and row["pass"]),
                        "k1_pass": bool(report.get((pid, "k1"), {}).get("pass")),
                        "passing": passing, "judge": verdicts,
                        "errors": (row["errors"] + row["failed"]) if row else ["no index.html"]}
        shutil.rmtree(samples / pid / "best", ignore_errors=True)
        shutil.copytree(samples / pid / best, samples / pid / "best")
        v = verdicts.get(best)
        taste = f"  judge {v['score']}/10{' WEAK' if v['score'] < 6 else ''}: {v['reason']}" if v else ""
        print(f"{pid}: {'PASS' if results[pid]['pass'] else 'FAIL'} via {best}  "
              f"passing={passing or '-'}  {'' if results[pid]['pass'] else results[pid]['errors']}{taste}")

    n = len(results)
    k = max(len(v) for v in cands.values())
    pass1 = sum(v["k1_pass"] for v in results.values())
    passk = sum(v["pass"] for v in results.values())
    any_cand = sum(len(v["passing"]) for v in results.values())
    print(f"\npass@1 (first candidate): {pass1}/{n}   best-of-{k}: {passk}/{n}   "
          f"all candidates: {any_cand}/{n * k}")
    if args.judge:
        good = sum(v["pass"] and v["judge"].get(v["best"], {}).get("score", 0) >= 6 for v in results.values())
        print(f"pass and judged good (≥6/10): {good}/{n}")
    (renders / "best.json").write_text(json.dumps({"pass@1": pass1, f"best_of_{k}": passk, "n": n,
                                                   "candidates_passing": any_cand, "per_prompt": results},
                                                  indent=2))


if __name__ == "__main__":
    main()
