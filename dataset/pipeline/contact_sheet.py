#!/usr/bin/env python3
"""Tile rendered screenshots into labelled contact sheets for fast human review.

Usage:
    python3 dataset/pipeline/contact_sheet.py dataset/renders/templates --width desktop --cols 4
    → dataset/renders/templates/_sheet_desktop_01.jpg, _02.jpg …
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders")
    ap.add_argument("--width", default="desktop")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--per-sheet", type=int, default=16)
    ap.add_argument("--tile", type=int, default=480, help="tile width px")
    ap.add_argument("--filter", default="", help="substring the id must contain")
    args = ap.parse_args()

    root = Path(args.renders)
    shots = sorted(p for p in root.glob(f"*/{args.width}.jpg") if args.filter in p.parent.name)
    tw = args.tile
    th = int(tw * 900 / 1440) if args.width == "desktop" else int(tw * 1.6)
    font = ImageFont.load_default(size=14)
    for s in range(0, len(shots), args.per_sheet):
        batch = shots[s:s + args.per_sheet]
        rows = (len(batch) + args.cols - 1) // args.cols
        sheet = Image.new("RGB", (args.cols * tw, rows * (th + 22)), "#111")
        d = ImageDraw.Draw(sheet)
        for i, p in enumerate(batch):
            im = Image.open(p).convert("RGB")
            im = im.crop((0, 0, im.width, min(im.height, int(im.width * th / tw))))
            im = im.resize((tw, th))
            x, y = (i % args.cols) * tw, (i // args.cols) * (th + 22)
            sheet.paste(im, (x, y + 22))
            d.text((x + 6, y + 3), p.parent.name.replace("website_templates__", "").replace("__index", "")[:60],
                   fill="#ddd", font=font)
        out = root / f"_sheet_{args.width}_{s // args.per_sheet + 1:02d}.jpg"
        sheet.save(out, quality=80)
        print(out)


if __name__ == "__main__":
    main()
