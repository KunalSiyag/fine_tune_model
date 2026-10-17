#!/usr/bin/env python3
"""Turn a make_site.py run into a shareable gallery: request → Gemma spec → the site it became.

    python3 dataset/pipeline/build_gallery.py dataset/runs/sites/ship-v1 --out dataset/runs/gallery

Writes <out>/index.html (one self-contained page), <out>/shots/*.jpg (first-screen crops) and
<out>/sites/<id>/ (each request's chosen site, live). Every request is shown, failures included.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image

PAGE = Path(__file__).with_name("gallery_template.html")
REDACTIONS = Path(__file__).resolve().parents[1] / "briefs" / "gallery_redactions.json"
# An invented international number may still ring someone; UK 01632 96xxxx is reserved for drama.
PHONE = re.compile(r"(\+\d{1,3})((?:[ \-]?\d{2,5}){2,4})")
TEL = re.compile(r"tel:\+?\d+")


def sanitize(text: str, fixes: list[list[str]]) -> tuple[str, int]:
    n = 0
    for old, new in fixes:
        if old in text:
            text, n = text.replace(old, new), n + 1
    text, k = PHONE.subn(lambda m: m.group(1) + re.sub(r"\d", "0", m.group(2)), text)
    text, t = TEL.subn("tel:+000000000", text)
    return text, n + k + t


def crop(src: Path, dst: Path, width: int, height: int, out_w: int):
    im = Image.open(src).convert("RGB")
    im = im.crop((0, 0, im.size[0], min(height, im.size[1])))
    im.resize((out_w, round(im.size[1] * out_w / im.size[0]))).save(dst, "JPEG", quality=82, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stats", default="{}", help="JSON of headline numbers to show")
    args = ap.parse_args()
    run, out = Path(args.run), Path(args.out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "shots").mkdir(parents=True)
    best = json.loads((run / "_renders" / "best.json").read_text())["per_prompt"]
    redactions = json.loads(REDACTIONS.read_text()) if REDACTIONS.exists() else {}

    items = []
    for pid, v in sorted(best.items()):
        shot_dir = run / "_renders" / f"{pid}__{v['best']}__index"
        verdict = v.get("judge", {}).get(v["best"])
        item = {"id": pid, "n": pid[:2], "request": (run / pid / "request.txt").read_text().strip(),
                "spec": (run / pid / "spec.txt").read_text().strip(), "draft": v["best"],
                "repaired": v["best"].endswith("r"), "pass": v["pass"],
                "score": verdict["score"] if verdict else None, "reason": verdict["reason"] if verdict else "",
                "errors": [e.split("\n")[0][:140] for e in v["errors"]][:2],
                "drafts": len([d for d in (run / pid).glob("k*") if d.name[1:].isdigit()])}
        if (shot_dir / "desktop.jpg").exists():
            crop(shot_dir / "desktop.jpg", out / "shots" / f"{pid}-d.jpg", 1440, 900, 1200)
            item["desktop"] = f"shots/{pid}-d.jpg"
        if (shot_dir / "mobile.jpg").exists():
            crop(shot_dir / "mobile.jpg", out / "shots" / f"{pid}-m.jpg", 390, 844, 260)
            item["mobile"] = f"shots/{pid}-m.jpg"
        if v["pass"]:  # only sites that pass QA go live; a failing one would just show its bug
            dst = out / "sites" / pid
            dst.mkdir(parents=True)
            edits = 0
            for f in (run / pid / "best").iterdir():
                if f.suffix in (".html", ".css", ".js"):
                    text, n = sanitize(f.read_text(), redactions.get(pid, []))
                    (dst / f.name).write_text(text)
                    edits += n
            item["live"] = f"sites/{pid}/index.html"
            item["edited"] = edits
            if edits:
                print(f"  {pid}: {edits} edit(s) in the published copy")
        items.append(item)

    data = json.dumps({"items": items, "stats": json.loads(args.stats)}, ensure_ascii=False)
    page = PAGE.read_text().replace("/*__DATA__*/null", data.replace("</", "<\\/"))
    (out / "index.html").write_text(page)
    print(f"{len(items)} requests, {sum('live' in i for i in items)} live sites → {out}/index.html")


if __name__ == "__main__":
    main()
