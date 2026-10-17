#!/usr/bin/env python3
"""Assemble SFT + DPO JSONL from corpus templates, sites and pairs.

    python3 dataset/pipeline/build_dataset.py                 # → dataset/out/
    python3 dataset/pipeline/build_dataset.py --max-tokens 16000 --variants 2

Task types produced (see dataset/SPEC.md §6):

  page_from_brief    prompt → a complete single-page site (index.html + style.css + js)
                     sources: corpus templates, each site's home page
  site_extend_page   site context (design brief, style.css, chrome, page list) + page
                     prompt → ONE new page that fits the existing site
                     sources: every non-home page of every site
  site_from_brief    prompt → every file of a multi-page site (only if it fits --max-tokens)
  upgrade            a generic page + "give this real art direction" → the chosen page
                     sources: pairs with rejected_kind=generic-rewrite
  DPO                prompt → chosen vs rejected (pairs/)

Only sources whose renders PASS (dataset/renders/**/report.jsonl) are used;
pass --no-qa to skip that gate.
"""
import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DS = ROOT / "dataset"
OUT = DS / "out"

SYSTEM = (
    "You are a senior web designer-developer. You build distinctive, production-quality websites "
    "in vanilla HTML, CSS and JavaScript (Google Fonts, GSAP and Lenis from CDN are allowed). "
    "Every page has a clear art direction — a deliberate palette, type pairing, shape language and "
    "motion personality — specific copy written for the brand, motion on load, scroll and hover, and "
    "at least one interaction that really works. Pages are responsive, accessible, and fully visible "
    "with reduced motion. Reply only with files, each wrapped as <file path=\"...\">…</file>."
)

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".svg"}
TEXT_EXT = {".html", ".css", ".js", ".json"}


def est_tokens(s: str) -> int:
    return int(len(s) / 3.3)  # code-heavy text ≈ 3.3 chars/token for BPE tokenizers


def file_block(path: str, content: str) -> str:
    return f'<file path="{path}">\n{content.rstrip()}\n</file>'


HTML_FIRST = False  # --html-first: pages before the css/js that style and script them


def ordered(paths: list[str]) -> list[str]:
    """Shared-files-first made the model write its JS before the elements it selects (null lookups);
    with HTML_FIRST the markup comes first, then css, then js. assets.json stays first: it's the plan."""
    if not HTML_FIRST:
        return paths
    rank = {".json": 0, ".html": 1, ".css": 2, ".js": 3}
    return sorted(paths, key=lambda p: rank.get(Path(p).suffix, 4))  # stable: keeps order within a kind


def join_files(files: list[tuple[str, str]]) -> str:
    content = dict(files)
    return "\n\n".join(file_block(p, content[p]) for p in ordered([p for p, _ in files]))


def stable_bucket(key: str) -> float:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


# ---------------------------------------------------------------- QA gate
def load_qa() -> dict:
    """path (relative to ROOT) → pass bool, from every report.jsonl under renders/."""
    qa = {}
    # full QA passes (renders/final, final_v2, …) win over agents' earlier per-site runs,
    # and a later pass wins over an earlier one
    reps = sorted((DS / "renders").rglob("report.jsonl"),
                  key=lambda p: next((x for x in p.parts if x.startswith("final")), ""))
    for rep in reps:
        for line in rep.read_text().splitlines():
            r = json.loads(line)
            qa[r["path"]] = r["pass"]
    return qa


def qa_ok(qa: dict, path: Path, enabled: bool) -> bool:
    if not enabled:
        return True
    return qa.get(str(path.relative_to(ROOT)), False)


# ---------------------------------------------------------------- helpers
def referenced_local(html: str, kinds: tuple) -> list[str]:
    refs = re.findall(r'(?:href|src)="\.?/?([^"#?:]+?\.(?:%s))"' % "|".join(kinds), html)
    return list(dict.fromkeys(refs))


def image_inventory(d: Path, html_blobs: list[str]) -> list[str]:
    """Images the page uses, as 'path — alt' lines, so the prompt can offer them."""
    lines, seen = [], set()
    for html in html_blobs:
        for m in re.finditer(r'<img[^>]*src="\.?/?([^"]+)"[^>]*>', html):
            src = m.group(1)
            if src in seen or not (d / src).exists():
                continue
            seen.add(src)
            alt = re.search(r'alt="([^"]*)"', m.group(0))
            lines.append(f"- {src} — {alt.group(1) if alt else ''}".rstrip(" —"))
        for src in re.findall(r"url\(['\"]?\.?/?([^'\")]+\.(?:jpg|jpeg|png|webp))", html):
            if src not in seen and (d / src).exists():
                seen.add(src)
                lines.append(f"- {src}")
    return lines


def assets_spec(d: Path) -> str | None:
    p = d / "assets.json"
    if not p.exists():
        return None
    spec = json.loads(p.read_text())
    spec.pop("comment", None)
    return json.dumps(spec, indent=2)


def chrome(html: str) -> str:
    """The shared header/nav + footer markup of a site (what new pages must copy)."""
    parts = []
    for tag in ("header", "nav", "footer"):
        m = re.search(rf"<{tag}\b.*?</{tag}>", html, re.S)
        if m and not any(m.group(0) in p for p in parts):
            parts.append(m.group(0))
    return "\n\n".join(parts)


def js_hooks(js: str) -> list[str]:
    """Selectors the shared script wires up automatically — tells a new page what it gets for free."""
    sels = re.findall(r"querySelector(?:All)?\(\s*['\"]([^'\"]+)['\"]", js)
    sels += re.findall(r"getElementById\(\s*['\"]([^'\"]+)['\"]", js)
    sels += re.findall(r"gsap\.(?:utils\.toArray|from|to|fromTo)\(\s*['\"]([^'\"]+)['\"]", js)
    return sorted(set(s for s in sels if len(s) < 60))[:40]


def prompt_variants(prompts: dict, n: int, rng: random.Random) -> list[tuple[str, str]]:
    keys = [k for k in ("terse", "brief", "spec") if prompts.get(k)]
    rng.shuffle(keys)
    return [(k, prompts[k]) for k in keys[:n]]


def page_files(d: Path, page: str) -> list[tuple[str, str]]:
    """index.html + the local css/js it links, in a stable order (shared files first)."""
    html = (d / page).read_text()
    files = []
    spec = assets_spec(d)
    if spec:
        files.append(("assets.json", spec))
    for rel in referenced_local(html, ("css",)) + referenced_local(html, ("js",)):
        if (d / rel).exists():
            files.append((rel, (d / rel).read_text()))
    files.append((page, html))
    return files


def image_note(d: Path, html_blobs: list[str], has_spec: bool) -> str:
    if has_spec:
        return ("\n\nNo photos exist yet: list every image you use in assets.json "
                "(name, generation prompt, width, height, seed) and reference them as ./assets/<name>.")
    inv = image_inventory(d, html_blobs)
    if inv:
        return "\n\nImages available (use these, don't invent others):\n" + "\n".join(inv)
    return "\n\nNo photos are available — use CSS, SVG or canvas for imagery."


# ---------------------------------------------------------------- record builders
def rec(rid, task, source, tier, user, assistant, weight=1.0):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant}]
    return {"id": rid, "task": task, "source": source, "tier": tier, "weight": weight,
            "messages": msgs, "n_tokens_est": est_tokens(SYSTEM + user + assistant)}


def from_templates(args, qa, tiers, rng):
    out = []
    for pf in sorted((DS / "corpus" / "prompts").glob("*.json")):
        meta = json.loads(pf.read_text())
        slug = meta["slug"]
        d = DS / "corpus" / "templates" / slug
        if not (d / "index.html").exists() or not qa_ok(qa, d / "index.html", not args.no_qa):
            continue
        tier = "A" if slug in tiers["A"] else "B"
        files = page_files(d, "index.html")
        answer = join_files(files)
        note = image_note(d, [c for p, c in files if p.endswith(".html")], any(p == "assets.json" for p, _ in files))
        n = args.variants if tier == "A" else max(1, args.variants - 1)
        for kind, prompt in prompt_variants(meta["prompts"], n, rng):
            out.append(rec(f"tpl:{slug}:{kind}", "page_from_brief", f"templates/{slug}", tier,
                           prompt + note, answer, tiers["weights"][tier]))
    return out


def from_sites(args, qa, rng):
    out = []
    for sj in sorted((DS / "sites").glob("*/site.json")):
        d = sj.parent
        site = json.loads(sj.read_text())
        name = site["site"]
        pages = site["pages"]
        ok = {p["file"] for p in pages if qa_ok(qa, d / p["file"], not args.no_qa)}
        if "index.html" not in ok:
            continue
        home = (d / "index.html").read_text()
        css_name = next((r for r in referenced_local(home, ("css",)) if (d / r).exists()), "style.css")
        js_name = next((r for r in referenced_local(home, ("js",)) if (d / r).exists()), "site.js")
        css = (d / css_name).read_text()
        js = (d / js_name).read_text() if (d / js_name).exists() else ""
        page_list = "\n".join(f"- {p['file']} — {p['type']}: {p.get('purpose', p.get('title', ''))}" for p in pages)
        has_spec = (d / "assets.json").exists()

        # 1. home page as a standalone build
        hp = next(p for p in pages if p["file"] == "index.html")
        files = page_files(d, "index.html")
        answer = join_files(files)
        for kind, prompt in prompt_variants(hp["prompts"], args.variants, rng):
            out.append(rec(f"site:{name}:index.html:{kind}", "page_from_brief", f"sites/{name}", "A",
                           prompt + image_note(d, [home], False), answer))

        # 2. each other page as "extend this existing site"
        hooks = js_hooks(js)
        for p in pages:
            if p["file"] == "index.html" or p["file"] not in ok:
                continue
            html = (d / p["file"]).read_text()
            ctx = (
                f"I'm extending my existing website ({site['brand']['name']} — {site['brand'].get('one_liner', '')}).\n\n"
                f"Design system: {site.get('design_brief', '')}\n\n"
                f"Pages in the site:\n{page_list}\n\n"
                f"Shared stylesheet {css_name} (already linked on every page — don't repeat it):\n"
                f"<file path=\"{css_name}\">\n{css.rstrip()}\n</file>\n\n"
                f"Shared script {js_name} (loaded on every page) auto-wires: {', '.join(hooks) or 'nav only'}.\n\n"
                f"Header and footer every page must reuse verbatim (move aria-current to the new page):\n{chrome(home)}"
                + image_note(d, [home, html], False)
            )
            for kind, prompt in prompt_variants(p["prompts"], args.variants, rng):
                user = ctx + f"\n\nNow write {p['file']}. {prompt}\n\nPut page-specific CSS in one <style> in the head and page-specific JS in one inline <script> after {js_name}."
                out.append(rec(f"site:{name}:{p['file']}:{kind}", "site_extend_page", f"sites/{name}", "A",
                               user, file_block(p["file"], html)))

        # 3. whole site in one answer (only when everything passed and it fits)
        if ok == {p["file"] for p in pages} and site.get("site_prompts"):
            shared = []
            if has_spec:
                shared.append(("assets.json", assets_spec(d)))
            shared += [(css_name, css)] + ([(js_name, js)] if js else [])
            files = shared + [(p["file"], (d / p["file"]).read_text()) for p in pages]
            answer = join_files(files)
            for kind, prompt in prompt_variants(site["site_prompts"], 1, rng):
                user = prompt + "\n\nBuild every page: " + ", ".join(p["file"] for p in pages) + "." + \
                       image_note(d, [c for a, c in files if a.endswith('.html')], has_spec)
                out.append(rec(f"site:{name}:ALL:{kind}", "site_from_brief", f"sites/{name}", "A", user, answer))
    return out


def from_synthetic(args, qa, rng):
    """dataset/{synthetic,external}/<slug>/ — single pages with a prompts.json alongside."""
    out = []
    for pj in sorted(list((DS / "synthetic").glob("*/prompts.json")) + list((DS / "external").glob("*/prompts.json"))):
        d = pj.parent
        if not qa_ok(qa, d / "index.html", not args.no_qa):
            continue
        meta = json.loads(pj.read_text())
        files = page_files(d, "index.html")
        answer = join_files(files)
        note = image_note(d, [c for p, c in files if p.endswith(".html")], any(p == "assets.json" for p, _ in files))
        group = d.parent.name  # synthetic | external
        for kind, prompt in prompt_variants(meta["prompts"], args.variants, rng):
            r = rec(f"{group[:3]}:{d.name}:{kind}", "page_from_brief", f"{group}/{d.name}", "A", prompt + note, answer)
            if meta.get("license"):
                r["license"], r["attribution"] = meta["license"], meta.get("attribution", "")
            out.append(r)
    return out


def pair_answer(d: Path, files: list[str]) -> str:
    return "\n\n".join(file_block(f, (d / f).read_text()) for f in ordered(files))


def from_pairs(args, rng):
    """pairs/<id>/{pair.json, chosen/, rejected/} → DPO rows (+ 'upgrade' SFT rows for generic rewrites)."""
    sft, dpo = [], []
    for pj in sorted((DS / "pairs").glob("*/pair.json")):
        d = pj.parent
        pair = json.loads(pj.read_text())
        files = pair["files"]
        chosen, rejected = pair_answer(d / "chosen", files), pair_answer(d / "rejected", files)
        user = pair["prompt"]
        prompt_msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        dpo.append({"id": f"pair:{d.name}", "source": pair.get("source", ""), "kind": pair["rejected_kind"],
                    "prompt": prompt_msgs,
                    "chosen": [{"role": "assistant", "content": chosen}],
                    "rejected": [{"role": "assistant", "content": rejected}],
                    "n_tokens_est": est_tokens(SYSTEM + user + chosen + rejected)})
        if pair["rejected_kind"] == "generic-rewrite":
            up = ("This works but looks like every other AI-generated site. Keep the content and "
                  "functionality, and give it a real art direction — distinctive type, palette, layout and "
                  f"motion that fit the brand.\n\nBrief: {user}\n\n{rejected}")
            sft.append(rec(f"upgrade:{d.name}", "upgrade", pair.get("source", f"pairs/{d.name}"), "A",
                           up, chosen))
    return sft, dpo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=2, help="prompt variants per output (A tier)")
    ap.add_argument("--max-tokens", type=int, default=24000, help="drop records longer than this")
    ap.add_argument("--eval-frac", type=float, default=0.1)
    ap.add_argument("--no-qa", action="store_true", help="don't require PASS renders")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dpo-cap", default="anchor-nav=40,reduced-motion=40",
                    help="max DPO pairs per rejected_kind (correctness kinds are cheap and would "
                         "otherwise drown the taste signal); '' = no caps")
    ap.add_argument("--html-first", action="store_true", help="order answers html → css → js")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    global HTML_FIRST
    HTML_FIRST = args.html_first
    out = Path(args.out)
    rng = random.Random(args.seed)
    qa = load_qa()
    tiers = json.loads((DS / "tiers.json").read_text())

    sft = from_templates(args, qa, tiers, rng) + from_sites(args, qa, rng) + from_synthetic(args, qa, rng)
    pair_sft, dpo = from_pairs(args, rng)
    caps = dict((k, int(v)) for k, v in (c.split("=") for c in args.dpo_cap.split(",") if c))
    rng.shuffle(dpo)
    seen = Counter()
    kept = []
    for r in dpo:
        seen[r["kind"]] += 1
        if seen[r["kind"]] <= caps.get(r["kind"], 10**9):
            kept.append(r)
    dpo = kept
    sft += pair_sft

    too_long = [r for r in sft if r["n_tokens_est"] > args.max_tokens]
    sft = [r for r in sft if r["n_tokens_est"] <= args.max_tokens]
    dpo = [r for r in dpo if r["n_tokens_est"] <= args.max_tokens * 1.6]

    # split by SOURCE so prompt variants of one page never straddle train/eval
    def is_eval(src):
        return stable_bucket(src) < args.eval_frac
    splits = defaultdict(list)
    for r in sft:
        splits["sft_eval" if is_eval(r["source"]) else "sft_train"].append(r)
    for r in dpo:
        splits["dpo_eval" if is_eval(r["source"]) else "dpo_train"].append(r)

    out.mkdir(parents=True, exist_ok=True)
    for name in ("sft_train", "sft_eval", "dpo_train", "dpo_eval"):
        rows = splits[name]
        rng.shuffle(rows)
        (out / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    stats = {
        "sft_train": len(splits["sft_train"]), "sft_eval": len(splits["sft_eval"]),
        "dpo_train": len(splits["dpo_train"]), "dpo_eval": len(splits["dpo_eval"]),
        "tasks": dict(Counter(r["task"] for r in sft)),
        "tiers": dict(Counter(r["tier"] for r in sft)),
        "dpo_kinds": dict(Counter(r["kind"] for r in dpo)),
        "sources": len({r["source"] for r in sft}),
        "eval_sources": sorted({r["source"] for r in splits["sft_eval"]}),
        "tokens": {"total_sft": sum(r["n_tokens_est"] for r in sft),
                   "max": max((r["n_tokens_est"] for r in sft), default=0),
                   "p50": sorted(r["n_tokens_est"] for r in sft)[len(sft) // 2] if sft else 0},
        "dropped_too_long": [r["id"] for r in too_long],
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps({k: v for k, v in stats.items() if k != "dropped_too_long"}, indent=2))
    print(f"dropped {len(too_long)} records over {args.max_tokens} tokens")


if __name__ == "__main__":
    main()
