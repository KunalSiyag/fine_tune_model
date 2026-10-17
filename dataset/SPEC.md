# Dataset spec

The contract every generator (human, agent, script) follows. The builder
(`pipeline/build_dataset.py`) reads only what is described here.

## 1. Folder layout

```
dataset/
├── corpus/templates/<slug>/   normalised copy of website_templates/ (bug-fixed; never hand-edit — rebuild)
├── design_systems/<slug>.json extracted design DNA per template (pipeline/extract_design.py)
├── sites/<site>/              multi-page sites (the core new data) — see §2
├── synthetic/<slug>/          new single-page templates generated from design systems × briefs
├── pairs/<id>/                DPO material: chosen.html / rejected.html / pair.json — see §5
├── raw/                       external sources (untrusted; licenses in raw/SOURCES.md)
├── renders/                   screenshots + QA reports (regenerable, gitignored)
└── out/                       final JSONL files for training
```

## 2. A site

```
sites/<site>/
├── site.json      metadata + prompts (schema below)
├── style.css      SHARED: tokens, type, nav, footer, buttons, shared components
├── site.js        SHARED: nav, reveals, cursor… every selector null-guarded
├── index.html     home
├── <page>.html    one file per page, flat (about.html, pricing.html, journal-post.html…)
├── assets.json    image prompts for any newly generated images (pipeline/gen_assets.py)
└── assets/        images (copied from the base template or generated)
```

Rules that make the site *trainable*:

1. **Shared files are frozen once the home page exists.** New pages link
   `style.css` + `site.js` and put everything page-specific in ONE
   `<style>` block in `<head>` and (optionally) ONE inline `<script>` at the
   end of `<body>`. This is what lets us train "write page X for this
   existing site" with a single-file answer.
2. **Identical chrome.** `<header>`/nav and `<footer>` markup is
   byte-identical across pages except the `aria-current="page"` marker.
   Nav links point at real files (`about.html`, not `#about`).
3. **Every page meets the quality bar** (§4) on its own — no filler pages.
4. Relative paths only (`./assets/x.jpg`). No hotlinked images. CDNs
   allowed: Google Fonts, cdnjs (gsap, ScrollTrigger), unpkg (lenis).

### `site.json`

```json
{
  "site": "ember",
  "base_template": "12-ember-restaurant",
  "brand": {"name": "Ember", "industry": "restaurant",
            "one_liner": "Wood-fire tasting room in a converted foundry",
            "voice": "warm, terse, sensory"},
  "design_brief": "2–4 sentences: palette, type pairing, shape language, motion personality",
  "pages": [
    {"file": "index.html", "type": "home", "title": "Home",
     "purpose": "what this page must achieve",
     "sections": ["hero", "menu-teaser", "..."],
     "interactions": ["menu filter", "reservation form"],
     "prompts": {
        "terse": "how a casual user would ask (1 sentence, no design words)",
        "brief": "a client brief: brand, audience, sections, vibe (3–6 sentences)",
        "spec":  "a designer spec: palette hexes, fonts, layout, motion, interactions"
     }}
  ],
  "site_prompts": {"terse": "...", "brief": "...", "spec": "..."}
}
```

Page `type` vocabulary (use these when they fit, invent when they don't):
`home about pricing features product-detail product-listing cart checkout
blog-index blog-post case-study docs changelog careers contact menu
reservations events schedule gallery team faq legal login signup dashboard
settings 404`.

## 3. Model output format

Every assistant turn is one or more file blocks and nothing else:

```
<file path="pricing.html">
<!DOCTYPE html>
...
</file>
```

Multiple files = multiple blocks, shared files first
(`style.css`, `site.js`, then pages in nav order). No prose before or after.
This format is trivially parseable at inference time and unambiguous
inside code (no nested ``` fences).

## 4. Quality bar (inherited from website_templates/TEMPLATE_SPEC.md)

Hard gates (automated, `pipeline/render.py`):
no console errors, no failed requests, no horizontal scroll at 390/820/1440,
no broken images, content visible under `prefers-reduced-motion`.

Taste gates (`pipeline/slop_check.py` + human review):
- a real art direction: named palette, deliberate type pairing (display +
  text, rarely Inter-only), a shape language, a motion personality;
- at least one real interaction (filter, configurator, toggle, form with
  states, playground) — not a static brochure;
- copy written for the brand, specific and concrete — never "Unlock the
  power of", "Seamless", "Elevate your", "Revolutionize", lorem ipsum;
- no default-AI layout: centered hero → 3 icon cards → testimonial
  carousel → gradient CTA, purple/indigo gradients, emoji as icons.

## 5. Preference pairs

```
pairs/<id>/
├── pair.json      {"prompt": "...", "rejected_kind": "...", "source": "sites/ember",
│                   "files": ["style.css", "index.html"]}   ← answer = these files, in order
├── chosen/<files>
└── rejected/<files>
```

`rejected_kind` — each changes ONE thing so the preference signal is clean:
- `destyled` *(auto, make_negatives.py)* — same structure and copy, art
  direction stripped: Tailwind-default slate/indigo palette, Inter, 12px
  radius everywhere, no grain/cursor/uppercase tracking. Teaches taste.
- `off-system` *(auto)* — a site page whose page-specific CSS ignores the
  site's fonts/palette. Teaches consistency.
- `reduced-motion` *(auto)* — GSAP timeline paused with content at opacity 0.
- `anchor-nav` *(auto)* — multi-page nav rewritten to dead `#anchors`.
- `generic-rewrite` *(agent)* — same brief rebuilt the "default AI" way
  (centered hero, 3 icon cards, buzzword copy, gradient CTA). Must still
  work. Also emitted as an SFT `upgrade` task (generic → good).
- `on-policy` — produced by the student model itself (fill in during training).

## 6. Training records (`out/*.jsonl`)

SFT (`sft_train.jsonl`, `sft_eval.jsonl`), chat format:

```json
{"id": "site:ember:menu.html:extend:brief",
 "task": "page_from_brief | site_extend_page | site_from_brief | restyle | upgrade",
 "source": "sites/ember", "tier": "A",
 "messages": [{"role": "system", "content": "..."},
              {"role": "user", "content": "..."},
              {"role": "assistant", "content": "<file path=...>...</file>"}],
 "n_tokens_est": 7200}
```

DPO (`dpo_train.jsonl`): `{"id", "prompt": [messages w/o assistant], "chosen": [assistant msg], "rejected": [assistant msg]}`
— the conversational format TRL's `DPOTrainer` accepts directly.

Eval split is by **source** (whole sites/templates held out), never by
record — otherwise prompt variants of the same page leak across splits.
