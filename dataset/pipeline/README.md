# One sentence in, a website out

A small business owner types one line. Gemma 4 (running locally) turns it into an art-direction
spec, a Qwen3-8B LoRA fine-tuned on Tinker writes the site, headless Chrome checks it, and Gemma
repairs the JavaScript and judges the result.

Gallery of 16 held-out requests: https://kunalsiyag.github.io/fine_tune_model/

```
one-liner ─▶ brief_gemma.py   Gemma 4 E4B (Ollama) writes the spec; a checker re-asks on missing names / fake fonts
          ─▶ train_tinker.py  the fine-tuned Qwen3-8B on Tinker writes k drafts (index.html, style.css, app.js)
          ─▶ fix_fonts.py     repairs Google Fonts URLs the model gets wrong
          ─▶ render.py        headless Chrome at 390/820/1440: JS errors, overflow, reduced motion, click test
          ─▶ pick_best.py     keeps a passing draft; --judge lets Gemma's vision pick between passing drafts
          └─ make_site.py     runs all of the above, plus Gemma JS repair and a fresh spec for weak results
```

## Run it

Needs: `.venv` with `tinker` and `tinker-cookbook`, `TINKER_API_KEY` in `.env`, Ollama with `gemma4:e4b`,
and Playwright with Chrome for `render.py`.

```bash
.venv/bin/python dataset/pipeline/make_site.py "a page for my sewing shop in Kochi, hemming and school uniforms" \
    --name tailor --k 5 --judge
# → dataset/runs/sites/tailor/<id>/best/index.html
```

`--batch FILE` runs one request per line. `--good 7` raises the bar a pick must clear before the
pipeline asks Gemma for a fresh spec. `--same-spec` tops up from the original spec instead.

## Train it

```bash
.venv/bin/python dataset/pipeline/train_tinker.py dry-run --max-length 16384 --epochs 1   # exact tokens and $, free
.venv/bin/python dataset/pipeline/train_tinker.py smoke                                     # ~1 cent end-to-end check
.venv/bin/python dataset/pipeline/train_tinker.py sft --name sft-v1 --epochs 1 --max-length 16384 --eval-limit 8
```

The training data comes from `build_dataset.py` (see `../README.md` and `../SPEC.md`).

## Measured on 16 requests nothing was tuned on

| | requests with a working site |
|---|---|
| first draft only | 7 / 16 |
| best of 5 drafts | 12 / 16 |
| + Gemma JS repair | 14 / 16 |
| … judged good by Gemma (≥ 6/10) | 9 / 16 |

About $0.03 of Tinker sampling per site. Training cost $4.05.
