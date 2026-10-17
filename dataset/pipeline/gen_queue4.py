"""Wave 4 queue: 60 SHORT briefs (syn-231..290) → records of ~2–5k tokens.

Records cost ≈320 tokens per KiB of page, so a short record needs a 6–14 KiB
page. Rather than squeezing ordinary pages, wave 4 uses formats that are small
by nature:
  - 30 micro pages: 15 naturally tiny page types × 2
  - 30 component pages: one production-complete component on a minimal
    branded page shell
Brands are fresh and global (10 non-English); palette, type, motion are drawn
least-used-first with waves 1–3 as history; half the pages are dark.

    python3 dataset/pipeline/gen_queue4.py   # → dataset/synthetic/_queue4.jsonl
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

DS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DS / "pipeline"))
_argv, sys.argv = sys.argv, ["x"]
import sample_briefs as sb  # noqa: E402
sys.argv = _argv

# (brand, industry, locale, language)
BRANDS = [
    ("Hatchmere Lock Café", "canal-side café", "Stoke-on-Trent, UK", "en-GB"),
    ("Pellow Gin", "small-batch gin distillery", "Penzance, Cornwall, UK", "en-GB"),
    ("Ashby Typewriter Rescue", "typewriter repair", "Leicester, UK", "en-GB"),
    ("Burren Bothy", "walkers' hostel", "County Clare, Ireland", "en-IE"),
    ("Tallyman Darts League", "pub darts league", "Wigan, UK", "en-GB"),
    ("Gorse & Grain", "granola maker", "Aberdeen, UK", "en-GB"),
    ("Selkie Swims", "year-round sea-swimming group", "Portobello, Edinburgh, UK", "en-GB"),
    ("Inkle Loom School", "weaving classes", "Lerwick, Shetland, UK", "en-GB"),
    ("Lanthorn Opticians", "independent optician", "Bath, UK", "en-GB"),
    ("Tidy Tenant", "end-of-tenancy cleaning", "Manchester, UK", "en-GB"),
    ("Fenland Fixers", "volunteer repair café", "Ely, Cambridgeshire, UK", "en-GB"),
    ("Quarto Night", "poetry open-mic night", "Belfast, UK", "en-GB"),
    ("Copse Coffee Cart", "mobile coffee cart", "Cardiff, UK", "en-GB"),
    ("Marlow Motet", "chamber choir", "Marlow, UK", "en-GB"),
    ("Rook & Rye", "whisky bar", "Glasgow, UK", "en-GB"),
    ("Brindle Grooming", "dog groomer", "Sheffield, UK", "en-GB"),
    ("Llechi Tours", "slate-mine tours", "Blaenau Ffestiniog, Wales, UK", "en-GB"),
    ("Cuttle Couriers", "bike courier co-op", "Brighton, UK", "en-GB"),
    ("Wren's Nest Childminding", "home childminder", "Norwich, UK", "en-GB"),
    ("Ferrous Forge School", "blacksmithing courses", "Shropshire, UK", "en-GB"),
    ("Second Line Brass Academy", "brass-band school for kids", "New Orleans, USA", "en-US"),
    ("Canyon Drift Rafting", "river-rafting outfitter", "Moab, Utah, USA", "en-US"),
    ("Lakeshore Lefse", "Norwegian-American bakery", "Duluth, Minnesota, USA", "en-US"),
    ("Trillium Kids OT", "paediatric occupational therapy", "Toronto, Canada", "en-CA"),
    ("Harbor Hound", "dog daycare", "Seattle, USA", "en-US"),
    ("Copper Kettle Fudge", "fudge shop", "Mackinac Island, Michigan, USA", "en-US"),
    ("Grain Silo Lofts", "converted-silo loft rentals", "Omaha, Nebraska, USA", "en-US"),
    ("Tumbleweed Tax", "tax prep for freelancers", "Albuquerque, New Mexico, USA", "en-US"),
    ("Bodega Cat Radio", "community internet radio", "The Bronx, New York, USA", "en-US"),
    ("Pebble & Broom", "curling club", "Winnipeg, Canada", "en-CA"),
    ("Atelier Gouttière", "zinc-roofing craftsmen", "Paris, France", "fr"),
    ("Café Würfel", "board-game café", "Leipzig, Germany", "de"),
    ("Forno Rionale", "neighbourhood bakery", "Bologna, Italy", "it"),
    ("Peixaria Alfama", "fishmonger", "Lisbon, Portugal", "pt"),
    ("Bicicletas Lentas", "slow bike tours", "Valencia, Spain", "es"),
    ("Kissaten Hoshi", "jazz coffee house", "Tokyo, Japan", "ja"),
    ("Yeonnam Clay", "pottery classes", "Seoul, South Korea", "ko"),
    ("Bondi Board Repairs", "surfboard repair", "Sydney, Australia", "en-AU"),
    ("Aro Valley Food Co-op", "food co-op", "Wellington, New Zealand", "en-NZ"),
    ("Matatu Art Collective", "matatu bus painters", "Nairobi, Kenya", "en"),
    ("Bonwire Weave Studio", "kente weaving studio", "Bonwire, Ghana", "en"),
    ("Felucca Sunset Sails", "felucca boat rides", "Aswan, Egypt", "en"),
    ("Dhow Wharf Spice Walks", "spice-souk walking tours", "Dubai, UAE", "en"),
    ("Dhobi Fresh", "laundry pickup service", "Mumbai, India", "en-IN"),
    ("Chandni Inks", "calligraphy studio", "Delhi, India", "en-IN"),
    ("Khlong Kayak", "canal kayak tours", "Bangkok, Thailand", "en"),
    ("Sari-Sari Supply", "corner-shop wholesale app", "Manila, Philippines", "en"),
    ("Hawker Heritage Walks", "hawker-food walking tours", "Singapore", "en-SG"),
    ("Batik Lab KL", "batik workshop", "Kuala Lumpur, Malaysia", "en"),
    ("Xe Máy Clinic", "scooter repair", "Ho Chi Minh City, Vietnam", "en"),
    ("Tram Stop Tailor", "alterations tailor", "Melbourne, Australia", "en-AU"),
    ("Café de Altura Lab", "coffee-cupping school", "Bogotá, Colombia", "es"),
    ("Ceviche Ciclo", "ceviche bike cart", "Lima, Peru", "en"),
    ("Taller de Piñatas Roma", "piñata maker", "Mexico City, Mexico", "es"),
    ("Bloco do Farol", "street-carnival percussion band", "Salvador, Brazil", "pt-BR"),
    ("Fika Fabriken", "cinnamon-bun bakery", "Stockholm, Sweden", "sv"),
    ("Cykelsmed Nørrebro", "bike smith", "Copenhagen, Denmark", "en"),
    ("Lopi Knit Tours", "wool and knitting tours", "Reykjavík, Iceland", "en"),
    ("Qvevri Cellar", "natural-wine cellar door", "Kakheti, Georgia", "en"),
    ("Kasi Kicks Restore", "sneaker restoration", "Soweto, South Africa", "en-ZA"),
]
assert len(BRANDS) == 60 and len({b[0] for b in BRANDS}) == 60

MICRO = [
    "link-in-bio page", "coming soon with countdown", "thank-you / confirmation page",
    "maintenance / we'll be back page", "event invitation with RSVP", "digital business card",
    "single-product drop", "gift card page", "QR table menu", "app download page",
    "email preferences / unsubscribe", "one-page CV / résumé", "password-gated preview",
    "closed-today / opening-hours notice", "one-page donation appeal",
]
COMPONENTS = [
    "date-range booking calendar", "pricing table with monthly/annual toggle", "multi-step form wizard",
    "cart drawer", "command palette", "toast notification system", "sortable, filterable data table",
    "FAQ accordion with search", "tabs with full keyboard support", "mega-menu navigation",
    "before/after comparison slider (SVG art)", "range-slider price calculator", "scroll-snap carousel",
    "interactive SVG map with pins", "audio player with waveform", "theme switcher (light/dark/high-contrast)",
    "file-drop zone with client-side preview", "one-time-code (OTP) input", "password strength meter on sign-up",
    "seat picker", "variant swatch picker with live preview", "timeline scrubber", "kanban board with drag and drop",
    "scripted chat widget", "countdown timer", "order-status progress tracker", "onboarding tour with popovers",
    "list with skeleton loading states", "honest cookie-consent dialog (equal-weight choices)",
    "code block with language tabs and copy",
]
assert len(MICRO) == 15 and len(COMPONENTS) == 30

# layouts that survive being small; the rest need room to read as themselves
SMALL_LAYOUTS = [l for l in sb.LAYOUTS if l.split(" — ")[0] in {
    "type-only poster", "split screen", "swiss grid", "asymmetric off-grid", "brutalist raw grid",
    "zine / cut-and-paste", "instrument panel", "oversized numerals", "single-column long-read",
    "catalogue cards with specimen", "scrapbook collage", "vertical writing-mode accents",
    "desktop-OS metaphor", "newspaper broadsheet"}]
STAGE = ("one component on a quiet branded stage — a minimal page shell (brand mark, one line of "
         "context, the component, a tiny footer); the component carries the design")


def main():
    hist = [json.loads(l) for q in ("_queue.jsonl", "_queue2.jsonl", "_queue3.jsonl")
            for l in open(DS / "synthetic" / q)]
    used = {k: Counter() for k in ("lay", "type", "pal", "mot")}
    for h in hist:
        used["lay"][h["layout"]] += 1; used["type"][tuple(h["type_pairing"])] += 1
        used["pal"][h["palette"]] += 1; used["mot"][h["motion"]] += 1

    rng = random.Random(53)
    kinds = [("micro page", t) for t in MICRO * 2] + [("component", c) for c in COMPONENTS]
    rng.shuffle(kinds)
    brands = BRANDS[:]
    rng.shuffle(brands)
    modes = ["dark", "light"] * 30
    rng.shuffle(modes)
    out = []
    for i, ((fmt, what), (brand, industry, locale, lang), want) in enumerate(zip(kinds, brands, modes)):
        pal, mode = sb.pick(rng, [p for p in sb.PALETTES if p[1] == want], used["pal"], key=lambda x: x[0])
        out.append({
            "slug": f"syn-{231 + i:03d}-{sb.slugify(brand)}",
            "brand": brand, "industry": industry, "locale": locale, "language": lang,
            "format": fmt,
            "page_type": what if fmt == "micro page" else f"component: {what}",
            "layout": sb.pick(rng, SMALL_LAYOUTS, used["lay"]) if fmt == "micro page" else STAGE,
            "type_pairing": list(sb.pick(rng, sb.TYPE_PAIRS, used["type"])),
            "palette": pal, "mode": mode,
            "motion": sb.pick(rng, sb.MOTIONS, used["mot"]),
            "interaction": "the component itself" if fmt == "component" else "one small, finished interaction that suits the page",
            "size_target": "short: 6-14 KiB total",
        })
    (DS / "synthetic" / "_queue4.jsonl").write_text(
        "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in out))
    print(Counter(b["format"] for b in out), Counter(b["mode"] for b in out),
          Counter(b["language"][:2] for b in out))


if __name__ == "__main__":
    main()
