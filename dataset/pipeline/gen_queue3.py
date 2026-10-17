"""Wave 3 queue: 50 compact, global briefs (syn-181..230).

Gaps it targets (measured 2026-10-14 over 180 synthetic pages):
88% UK-set, 100% English, none under 20 KiB, 1/3 dark, 12 page types absent.
Other axes are drawn least-used-first with wave 1+2 as history.
"""
import json, random, sys
from collections import Counter
from pathlib import Path

DS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DS / "pipeline"))
sys.argv = ["x"]
import sample_briefs as sb

# (brand, industry, locale, language)
BRANDS = [
    ("Tamarind Row", "South Indian tiffin delivery", "Bengaluru, India", "en-IN"),
    ("Kogei Lab", "urushi lacquer repair studio", "Kyoto, Japan", "en"),
    ("Alma Barro", "hand-made ceramic tile workshop", "Oaxaca, Mexico", "es"),
    ("Savanna Signal", "community solar mini-grid", "Kisumu, Kenya", "en"),
    ("Ilha Verde", "rooftop farm co-op", "São Paulo, Brazil", "pt-BR"),
    ("Northbound Diner", "24-hour highway diner", "Nebraska, USA", "en-US"),
    ("Kelp & Kin", "seaweed snack brand", "Hobart, Tasmania, Australia", "en-AU"),
    ("Fjellstue", "mountain hut booking network", "Jotunheimen, Norway", "en"),
    ("Maison Ourlet", "tailoring & alterations atelier", "Lyon, France", "fr"),
    ("Seochon Hanok Stay", "traditional guesthouse", "Seoul, South Korea", "en"),
    ("Lagos Line Studio", "recording studio", "Lagos, Nigeria", "en"),
    ("Pāua Paddle", "outrigger canoe club", "Wellington, New Zealand", "en-NZ"),
    ("Copper Canyon Assay", "mineral testing lab", "Tucson, Arizona, USA", "en-US"),
    ("Tramvay Baklava", "baklava & pastry shop", "Istanbul, Türkiye", "en"),
    ("Riverbend Mutual", "community credit union", "Dayton, Ohio, USA", "en-US"),
    ("Zellij Atelier", "zellige tile restoration", "Fez, Morocco", "en"),
    ("Prairie Lantern", "rural bookmobile library", "Saskatchewan, Canada", "en-CA"),
    ("Kampung Kode", "coding school for kids", "Yogyakarta, Indonesia", "en"),
    ("Vinho Velho", "port-wine lodge tours", "Porto, Portugal", "pt"),
    ("Sauerteig Süd", "sourdough bakery", "Munich, Germany", "de"),
    ("Cape Kelpie", "dog-walking co-op", "Cape Town, South Africa", "en-ZA"),
    ("Monsoon Ledger", "rainfall data API", "Mumbai, India", "en-IN"),
    ("Andes Altitude Lab", "high-altitude training camp", "Cusco, Peru", "en"),
    ("Mesquite Telehealth", "telehealth clinic for rural ranchers", "West Texas, USA", "en-US"),
    ("Saunasaari", "floating public sauna", "Helsinki, Finland", "en"),
    ("Bamboo Bridge Builders", "bamboo architecture firm", "Ubud, Bali, Indonesia", "en"),
    ("Phở Mai", "pho noodle bar", "Hanoi, Vietnam", "en"),
    ("Copperplate Notary", "mobile notary service", "Brooklyn, New York, USA", "en-US"),
    ("Ghats Estate", "single-estate coffee grower", "Kodagu, India", "en-IN"),
    ("Jacaranda Junction", "weekend craft market", "Pretoria, South Africa", "en-ZA"),
    ("Tango Nocturno", "milonga dance hall", "Buenos Aires, Argentina", "es"),
    ("Glacier Line Heli", "heli-ski operator", "British Columbia, Canada", "en-CA"),
    ("Tatami Works", "tatami mat maker", "Kanazawa, Japan", "ja"),
    ("Saltpan Locations", "film location scouting", "Swakopmund, Namibia", "en"),
    ("Red Gum Brigade", "volunteer bushfire brigade", "Blue Mountains, NSW, Australia", "en-AU"),
    ("Chai Adda Co-op", "tea-stall co-operative", "Kolkata, India", "en-IN"),
    ("Bakfiets Buurt", "cargo-bike rental", "Amsterdam, Netherlands", "nl"),
    ("Quarter Note Piano", "piano restoration", "New Orleans, USA", "en-US"),
    ("Humo Norteño", "barbecue smokehouse", "Monterrey, Mexico", "en"),
    ("Tizi Trails", "village-to-village trekking", "High Atlas, Morocco", "en"),
    ("Kaimukī Shave Ice", "shave-ice stand", "Honolulu, Hawaiʻi, USA", "en-US"),
    ("Polder Data", "flood-sensor startup", "Rotterdam, Netherlands", "en"),
    ("Kesar Mehndi", "bridal henna artist", "Jaipur, India", "en-IN"),
    ("Stadtgarten Kino", "open-air cinema", "Vienna, Austria", "de"),
    ("Yuzu Pantry", "Japanese pantry goods e-shop", "Osaka, Japan", "en"),
    ("Érablière Côté", "maple sugar shack", "Quebec, Canada", "fr-CA"),
    ("Coral Census", "reef citizen-science app", "Cairns, Queensland, Australia", "en-AU"),
    ("Chitenge Collective", "textile co-operative", "Lusaka, Zambia", "en"),
    ("Funicular Valparaíso", "heritage funicular trust", "Valparaíso, Chile", "es"),
    ("Midnight Suds", "24-hour laundromat & café", "Taipei, Taiwan", "en"),
]
assert len(BRANDS) == 50

NEW_TYPES = sb.PAGE_TYPES[sb.PAGE_TYPES.index("settings / account"):]
assert len(NEW_TYPES) == 12

hist = [json.loads(l) for f in ("_queue.jsonl", "_queue2.jsonl") for l in open(DS / "synthetic" / f)]
used = {k: Counter() for k in ("page", "lay", "type", "pal", "mot", "int")}
for h in hist:
    used["page"][h["page_type"]] += 1; used["lay"][h["layout"]] += 1
    used["type"][tuple(h["type_pairing"])] += 1; used["pal"][h["palette"]] += 1
    used["mot"][h["motion"]] += 1; used["int"][h["interaction"]] += 1

rng = random.Random(41)
pages = NEW_TYPES * 2 + [None] * 26          # 24 new-type pages, 26 least-used old types
rng.shuffle(pages)
order = list(range(50)); rng.shuffle(order)
modes = ["dark", "light"] * 25
out = []
for i in range(50):
    brand, industry, locale, lang = BRANDS[order[i]]
    want = modes[i]
    pal_pool = [p for p in sb.PALETTES if p[1] == want]
    pal, mode = sb.pick(rng, pal_pool, used["pal"], key=lambda x: x[0])
    old_types = [t for t in sb.PAGE_TYPES if t not in NEW_TYPES]
    page = pages[i] or sb.pick(rng, old_types, used["page"])
    if pages[i]:
        used["page"][page] += 1
    out.append({
        "slug": f"syn-{181 + i:03d}-{sb.slugify(brand)}",
        "brand": brand, "industry": industry, "locale": locale, "language": lang,
        "page_type": page,
        "layout": sb.pick(rng, sb.LAYOUTS, used["lay"]),
        "type_pairing": list(sb.pick(rng, sb.TYPE_PAIRS, used["type"])),
        "palette": pal, "mode": mode,
        "motion": sb.pick(rng, sb.MOTIONS, used["mot"]),
        "interaction": sb.pick(rng, sb.INTERACTIONS, used["int"]),
        "size_target": "compact: 12-25 KiB total",
    })
(DS / "synthetic" / "_queue3.jsonl").write_text("".join(json.dumps(b, ensure_ascii=False) + "\n" for b in out))
print(Counter(b["mode"] for b in out), Counter(b["language"][:2] for b in out))
print(Counter(b["page_type"] for b in out).most_common(8))
