#!/usr/bin/env python3
"""Sample diverse design briefs for synthetic templates.

Diversity is the whole game for synthetic data: if every generated page is
"dark hero + big serif", the student learns one look. So each brief is a
cross-product draw over independent axes, with constraints that stop
clichéd combos and keep every axis value evenly used (least-used first).

    python3 dataset/pipeline/sample_briefs.py -n 60 > dataset/synthetic/_queue.jsonl

Axes: industry/brand · page type · layout archetype · type pairing ·
palette mood · motion signature · signature interaction · light/dark.
"""
import argparse
import json
import random
import re
import unicodedata
from collections import Counter

INDUSTRIES = [
    ("Tidewater", "oyster farm & raw bar"), ("Kettle & Kiln", "community pottery studio"),
    ("Parallax Labs", "AR prototyping agency"), ("Ostrava Rail", "night-train operator"),
    ("Quill", "independent literary magazine"), ("Hollow Pines", "forest cabin rentals"),
    ("Moto Rossa", "vintage motorcycle restorer"), ("Sable", "natural wine bar"),
    ("Lattice", "structural engineering firm"), ("Fieldnote", "birdwatching app"),
    ("Brine", "small-batch hot sauce"), ("Atlas Cartography", "hand-drawn map studio"),
    ("Ferment Co.", "kombucha brewery"), ("North Paddle", "sea-kayak school"),
    ("Cinder Records", "vinyl-only record label"), ("Plume", "ethical down outerwear"),
    ("Orrery", "planetarium & observatory"), ("Verdant", "urban vertical farm"),
    ("Mise", "chef knife maker"), ("Little Fable", "children's picture-book publisher"),
    ("Grain & Grit", "climbing gym"), ("Sundial", "solar installer co-op"),
    ("Opal Dental", "boutique dental clinic"), ("Ledger Lane", "bookkeeping for creatives"),
    ("Woven", "handloom textile cooperative"), ("Static Bloom", "electronic music festival"),
    ("Harbourlight", "maritime history museum"), ("Pocket Sky", "kite & wind-toy shop"),
    ("Tessellate", "tile & terrazzo maker"), ("Bramble", "wild foraging tours"),
    ("Monolith", "brutalist architecture tours"), ("Cartwheel", "kids' bike brand"),
    ("Saltbox", "coastal surf school"), ("Inkwell", "tattoo studio"),
    ("Quiet Hours", "meditation app"), ("Halftone", "risograph print studio"),
    ("Driftwood", "furniture from reclaimed timber"), ("Ampersand", "type design course"),
    ("Pitch & Putt", "retro mini-golf bar"), ("Borealis Air", "regional seaplane airline"),
    ("Foundry Fit", "strength coaching for over-50s"), ("Copperleaf", "tea house & ceremony"),
    ("Signal", "privacy-first email client"), ("Patchwork", "neighbourhood mutual-aid network"),
    ("Basalt", "volcanic skincare"), ("Velodrome", "track cycling club"),
    ("Paper Moon", "stationery subscription"), ("Lumen Optics", "independent eyewear"),
    ("Heirloom Seeds", "seed library & shop"), ("Gridiron Data", "sports analytics API"),
    ("Spoke & Stem", "bicycle-delivered florist"), ("Undertow", "documentary film studio"),
    ("Marginalia", "used & rare bookshop"), ("Cobble", "cobbler & leather repair"),
    ("Aerie", "treetop hotel"), ("Rhythm Rooms", "rehearsal studio rental"),
    ("Petrichor", "perfume house"), ("Stack Overflowers", "hackathon organisers"),
    ("Granary", "flour mill & bakery school"), ("Waypoint", "trail-running race series"),
    # wave 2 (2026-10-13)
    ("Lantern & Loom", "night market collective"), ("Fathom", "freediving school"),
    ("Okra", "West African supper club"), ("Vellum", "bookbinding workshop"),
    ("Hinterland", "rural broadband co-op"), ("Plover", "shorebird conservation trust"),
    ("Pressed", "cold-press juice bar"), ("Tinker", "kids' electronics kits"),
    ("Clay Court", "neighbourhood tennis club"), ("Mortar", "historic masonry restoration"),
    ("Murmur", "ASMR & sleep audio label"), ("Riverside Rowing", "rowing club"),
    ("Proof", "sourdough pizza truck"), ("Quarry", "climbing-shoe resoler"),
    ("Saffron Street", "spice merchant"), ("Night Owl", "24h veterinary clinic"),
    ("Compass Rose", "sailing charter"), ("Folklore", "oral-history archive"),
    ("Alder", "Scandinavian sauna"), ("Gauge", "knitting-yarn dyer"),
    ("Bellwether", "sheep farm & wool mill"), ("Ochre", "aboriginal-owned art gallery"),
    ("Fieldhouse", "indoor sports hall"), ("Overture", "youth orchestra"),
    ("Rivet", "denim repair & alterations"), ("Kinship", "foster-care charity"),
    ("Delta", "river-cruise company"), ("Thimble", "sewing pattern company"),
    ("Mosaic", "multilingual preschool"), ("Arcade 1983", "retro arcade bar"),
    ("Upland", "honey producer"), ("Ballast", "port logistics software"),
    ("Pilot Light", "home-heating engineers"), ("Pinhole", "film-photography lab"),
    ("Stillwater", "hospice & palliative care"), ("Glasshouse", "botanical garden"),
    ("Morrow", "estate-planning app"), ("Tempo", "metronome & practice app"),
    ("Hearth", "wood-stove maker"), ("Crossword Club", "puzzle subscription"),
    ("Orchard Lane", "cider house"), ("Slipway", "wooden boatbuilder"),
    ("Kestrel", "drone survey company"), ("Common Ground", "community allotments"),
    ("Silt", "natural-dye studio"), ("Polar", "ice-cream parlour"),
    ("Contour", "architectural model makers"), ("Echo Chamber", "acoustic panel maker"),
    ("Veranda", "outdoor furniture brand"), ("Lexicon", "translation agency"),
    ("Burrow", "tiny-home builder"), ("Ripple", "swim school for adults"),
    ("Cartograph", "GIS data startup"), ("Paloma", "mezcal distillery"),
    ("Studio Ochre", "interior design practice"), ("Marrowbone", "nose-to-tail butcher"),
    ("Bluebell", "midwifery practice"), ("Grit & Gravel", "gravel-bike tour company"),
    ("Index", "independent design-book publisher"), ("Lighthouse Labs", "coding bootcamp for career changers"),
    # wave 2b (2026-10-14): fresh brands for queue2 lines 89-120 (pool was exhausted)
    ('Thornick', 'letterpress wedding stationer'),
    ('Hollins Gauge', 'model railway shop'),
    ('Quenby', 'audiology & hearing clinic'),
    ('Ashgrove Lido', 'restored outdoor lido'),
    ('Felwick', 'violin maker & repairer'),
    ('Marlpit', 'brick reclamation yard'),
    ('Selvedge Lane', 'upholstery workshop'),
    ('Tidemark', 'flood-risk survey consultancy'),
    ('Corvid Locks', 'locksmith & key cutter'),
    ('Wrenfold', 'paper-engineering studio'),
    ('Halyard Ferries', 'island car ferry'),
    ('Embergate', 'natural burial ground'),
    ('Pebblehatch', 'rescue-hen rehoming charity'),
    ('Lowfold', 'cheese cave & affineur'),
    ('Sixpenny', 'pick-your-own fruit farm'),
    ('Gannet & Gull', 'seabird boat trips'),
    ('Whinstone', 'drystone-walling courses'),
    ('Cobaltine', 'glassblowing studio'),
    ('Kittering', 'cat café & adoption'),
    ('Orbweaver', 'mechanical keyboard maker'),
    ('Tarnside', 'volunteer mountain rescue team'),
    ('Brightwork', 'chandlery & marine hardware'),
    ('Quillon', 'fencing club'),
    ('Dunmere', 'dementia-friendly cinema'),
    ('Pollard', 'tree surgeons'),
    ('Plinth', 'museum-grade picture framer'),
    ('Stepwell', 'public-library makerspace'),
    ('Ravelin', 'escape-room company'),
    ('Nettlebed', 'herbal apothecary'),
    ('Windrow', 'compost collection co-op'),
    ('Paternoster', 'vintage lift restoration'),
    ('Quayside Ice', 'ice-skating rink'),
]
PAGE_TYPES = ["home", "home", "home", "product-detail", "pricing", "about", "event", "portfolio-index",
              "case-study", "menu", "booking", "docs-landing", "shop",
              "blog-post / long-read", "careers", "contact", "launch / waitlist", "404 / error page",
              "changelog", "dashboard", "checkout", "sign-up / onboarding", "team", "faq / help", "comparison",
              # wave 3 (2026-10-14): page types the corpus had none of
              "settings / account", "search results", "status page", "legal / privacy policy", "recipe",
              "listing detail (property / vehicle)", "newsletter archive", "order confirmation / receipt",
              "lookbook / gallery", "press kit", "store / location finder", "course syllabus / lesson"]
LAYOUTS = [
    "editorial magazine spread — multi-column text, drop caps, captions, pull quotes",
    "bento grid — modular tiles of varied size carrying different content types",
    "split screen — sticky left column, scrolling right column",
    "horizontal-scroll gallery section pinned inside a vertical page",
    "brutalist raw grid — visible rules, monospace labels, harsh contrast",
    "type-only poster — giant typography as the main visual, almost no imagery",
    "index / catalogue list — dense numbered rows that expand on hover",
    "single-column long-read — narrow measure, generous whitespace, marginal notes",
    "map-led — an illustrated SVG map or diagram is the central navigation",
    "swiss grid — strict 12-col, flush-left, asymmetric balance, red accent",
    "scrapbook collage — overlapping cut-out images, tape, rotated cards",
    "full-bleed photo essay — image after image with short captions",
    "timeline / chronology — a vertical or horizontal rail drives the page",
    "card stack — sections slide over each other as sticky cards",
    "instrument panel — the page looks like a device / console UI",
    "newspaper broadsheet — 12-col grid, mixed story sizes, hairline rules, datelines",
    "zine / cut-and-paste — rotated type blocks, xerox texture, hand-drawn marks",
    "spec sheet / data table first — the product IS the table, typographic precision",
    "oversized numerals — giant numbers structure the page (steps, stats, prices)",
    "vertical writing-mode accents — rotated labels, side-running titles, Japanese-style margins",
    "sticky media + scrolling captions — one visual frame changes as text steps past",
    "full-screen sections with snap — chapters, each a single composition",
    "asymmetric off-grid — elements deliberately hang off columns, big negative space",
    "catalogue cards with specimen detail — museum/archive object records",
    "desktop-OS metaphor — windows, folders, draggable panels",
]
TYPE_PAIRS = [
    ("Fraunces", "Inter Tight"), ("Instrument Serif", "Geist"), ("Playfair Display", "Karla"),
    ("Space Grotesk", "Space Mono"), ("Syne", "Manrope"), ("DM Serif Display", "DM Sans"),
    ("Bricolage Grotesque", "Atkinson Hyperlegible"), ("Cormorant Garamond", "Jost"),
    ("Archivo Black", "Archivo"), ("Anton", "IBM Plex Sans"), ("Bodoni Moda", "Figtree"),
    ("Unbounded", "Onest"), ("Newsreader", "Public Sans"), ("Big Shoulders Display", "Barlow"),
    ("Libre Caslon Display", "Work Sans"), ("Bebas Neue", "Source Serif 4"), ("Rubik Mono One", "Rubik"),
    ("Young Serif", "Hanken Grotesk"), ("Gloock", "Schibsted Grotesk"), ("Familjen Grotesk", "Literata"),
    ("Chivo Mono", "Chivo"), ("Caprasimo", "Nunito Sans"), ("Italiana", "Montserrat Alternates"),
    ("EB Garamond", "Inter Tight"), ("Fraunces", "Commissioner"), ("Instrument Sans", "Instrument Serif"),
    ("JetBrains Mono", "IBM Plex Sans"), ("Zilla Slab", "Lato"), ("Climate Crisis", "Albert Sans"),
    ("Lexend Zetta", "Lexend"), ("Spectral", "Sora"), ("Pixelify Sans", "Space Mono"),
    ("Abril Fatface", "Poppins"), ("Bagel Fat One", "Outfit"), ("Shrikhand", "Red Hat Text"),
    ("Tenor Sans", "Crimson Pro"), ("Anybody", "Azeret Mono"), ("Gupter", "Mulish"),
    ("Darker Grotesque", "Lora"), ("Bowlby One", "Courier Prime"), ("Kaisei Decol", "Zen Kaku Gothic New"),
]
PALETTES = [
    ("sun-bleached paper + ink + one tomato red", "light"), ("deep forest + moss + bone", "dark"),
    ("cobalt + cream, risograph two-tone", "light"), ("charcoal + sodium-vapour orange", "dark"),
    ("terracotta + sand + olive", "light"), ("midnight navy + brass", "dark"),
    ("mint + plum + off-white", "light"), ("black + acid chartreuse", "dark"),
    ("oat + espresso + rust", "light"), ("glacier blue + slate + white", "light"),
    ("burgundy + blush + gold leaf", "dark"), ("concrete grey + safety yellow", "light"),
    ("seafoam + deep teal + coral", "light"), ("ultraviolet ink + paper (no gradients)", "light"),
    ("pine + pumpkin + cream", "light"), ("graphite + pale lilac", "dark"),
    ("butter yellow + cocoa", "light"), ("oxblood + black + parchment", "dark"),
    ("sky + cloud + sunset pink, airy pastel", "light"), ("printer CMY on newsprint", "light"),
    ("fluorescent pink + blue risograph on newsprint", "light"), ("ink black + bone + one signal red", "light"),
    ("matcha + sumi black + warm white", "light"), ("ultramarine + white, Klein-blue monochrome", "light"),
    ("rust + steel + concrete", "dark"), ("cream + forest + marigold, 70s print", "light"),
    ("aubergine + saffron", "dark"), ("chalk + powder blue + tomato", "light"),
    ("sepia archive: tobacco + paper + faded ink", "light"), ("tar black + hi-vis orange + white", "dark"),
    ("lavender fog + charcoal + lime pop", "light"), ("deep sea teal + phosphor green, CRT", "dark"),
]
MOTIONS = [
    "split-text character stagger on headings", "scroll-scrubbed clip-path reveals",
    "parallax layered sandwich hero (bg / type / foreground)", "marquee ticker + magnetic buttons",
    "SVG line-drawing on scroll", "sticky stacking cards with scale-down", "cursor-follow spotlight / mask",
    "number counters + bar growth on view", "kinetic type that reacts to scroll velocity",
    "slow Ken Burns imagery + fade-rise reveals", "canvas particle or noise field background",
    "view-transition style crossfades between tabs",
    "CSS scroll-driven animations (animation-timeline: view()) — no JS",
    "FLIP layout transitions between states",
    "stepped / sprite-like steps() easing, deliberately mechanical",
    "variable-font axis animation (weight/width responds to scroll or pointer)",
    "image-trail / pointer-follow reveal on a list",
    "horizontal pinned scroll with progress indicator",
    "text mask / clip reveal lines on scroll",
    "almost none — static, motion only on interaction (restraint as style)",
]
INTERACTIONS = [
    "filterable grid with animated re-layout", "live price calculator with sliders",
    "product configurator (colour/size/material) updating the visual", "booking form with date logic & validation",
    "before/after drag comparison slider", "audio player with waveform scrubbing",
    "interactive SVG map with hover cards", "tabbed itinerary / schedule by day",
    "quiz that recommends a product", "accordion FAQ with search", "lightbox gallery with keyboard nav",
    "theme toggle that changes the art direction", "drag-to-reorder or drag-to-explore canvas",
    "type tester (edit text, change size/weight)", "countdown + waitlist form with states",
    "cart drawer with quantity steppers and totals", "timeline scrubber", "copy-to-clipboard code tabs",
    "multi-step form with progress and per-step validation", "seat / slot map selection",
    "searchable command palette (Cmd/Ctrl-K)", "scalable recipe / quantity recomputation",
    "comparison table with column highlight and sticky header", "interactive chart with hover readouts",
    "drag-and-drop sorter / planner", "sound board / step sequencer (Web Audio, user-initiated)",
    "persisting checklist / wishlist (localStorage, try/catch)", "date-range availability calendar",
]
BANNED = [  # combos that collapse into clichés
    (r"midnight navy|black \+ acid|graphite", r"privacy-first email|analytics API"),  # dark SaaS cliché
]


def slugify(s: str) -> str:
    # transliterate accents first (Érablière → erabliere), else they become dashes
    s = s.translate(str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "þ": "th"}))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pick(rng, items, used: Counter, key=lambda x: x):
    """Least-used-first with random tiebreak → even coverage of each axis."""
    m = min(used[key(i)] for i in items)
    choice = rng.choice([i for i in items if used[key(i)] == m])
    used[key(choice)] += 1
    return choice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--start", type=int, default=1, help="first syn-NNN index")
    ap.add_argument("--history", help="previous queue jsonl: its draws count as used (keeps coverage even)")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    used = {k: Counter() for k in ("ind", "page", "lay", "type", "pal", "mot", "int")}
    if args.history:
        for line in open(args.history):
            h = json.loads(line)
            used["ind"][h["brand"]] += 1; used["page"][h["page_type"]] += 1; used["lay"][h["layout"]] += 1
            used["type"][tuple(h["type_pairing"])] += 1; used["pal"][h["palette"]] += 1
            used["mot"][h["motion"]] += 1; used["int"][h["interaction"]] += 1
    i = 0
    while i < args.n:
        brand, industry = pick(rng, INDUSTRIES, used["ind"], key=lambda x: x[0])
        pal, mode = pick(rng, PALETTES, used["pal"], key=lambda x: x[0])
        if any(re.search(a, pal) and re.search(b, industry) for a, b in BANNED):
            continue
        b = {
            "slug": f"syn-{args.start + i:03d}-{slugify(brand)}",
            "brand": brand, "industry": industry,
            "page_type": pick(rng, PAGE_TYPES, used["page"]),
            "layout": pick(rng, LAYOUTS, used["lay"]),
            "type_pairing": list(pick(rng, TYPE_PAIRS, used["type"])),
            "palette": pal, "mode": mode,
            "motion": pick(rng, MOTIONS, used["mot"]),
            "interaction": pick(rng, INTERACTIONS, used["int"]),
        }
        print(json.dumps(b))
        i += 1


if __name__ == "__main__":
    main()
