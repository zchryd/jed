#!/usr/bin/env python3
"""Source public-domain scientific illustrations from Wikimedia Commons for the
Field Guide species cards. STRICT license filter: only genuinely public-domain
or CC0 files are accepted (nothing CC-BY / CC-BY-SA / GFDL / copyrighted).

Outputs:
  project-data/plates/<slug>.jpg        grayscale, ~860px wide
  project-data/plates_manifest.json     per-species: license, artist, source URL
"""
import json, os, re, sys, time, subprocess, urllib.parse
from io import BytesIO
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_IMG = os.path.join(HERE, "plates")
OUT_MANIFEST = os.path.join(HERE, "plates_manifest.json")
os.makedirs(OUT_IMG, exist_ok=True)

UA = "jed-fieldguide-plates/1.0 (personal trip guide; contact [redacted])"
API = "https://commons.wikimedia.org/w/api.php"

# (slug, anchor h4 text in Field Guide, scientific/subject to search, extra hint words)
# For grouped cards we pick the single most iconic/important subject.
SPECIES = [
    # ZONE 1
    ("coast-redwood",       "Coast redwood",            "Sequoia sempervirens",       "foliage cone"),
    ("redwood-sorrel",      "Redwood sorrel",           "Oxalis oregana",             "botanical"),
    ("sword-fern",          "Sword fern",               "Polystichum munitum",        "frond"),
    ("western-trillium",    "Western trillium",         "Trillium ovatum",            "botanical"),
    ("bead-lily",           "Clintonia (bead lily)",    "Clintonia andrewsiana",      "botanical"),
    ("banana-slug",         "Banana slug",              "Ariolimax columbianus",      "slug"),
    ("varied-thrush",       "Varied thrush",            "Ixoreus naevius",            "bird"),
    ("pacific-wren",        "Pacific wren",             "Troglodytes",                "wren bird"),
    ("wandering-salamander","Wandering salamander",     "Aneides",                    "salamander"),
    # ZONE 2
    ("douglas-fir",         "Douglas-fir",              "Pseudotsuga menziesii",      "cone foliage"),
    ("western-hemlock",     "Western hemlock",          "Tsuga heterophylla",         "cone foliage"),
    ("sitka-spruce",        "Sitka spruce",             "Picea sitchensis",           "cone foliage"),
    ("grand-fir",           "Grand fir",                "Abies grandis",              "cone foliage"),
    ("port-orford-cedar",   "Port Orford cedar",        "Chamaecyparis lawsoniana",   "foliage"),
    ("madrone",             "Tanoak · madrone · California bay", "Arbutus menziesii", "botanical"),
    ("rhododendron",        "Pacific rhododendron",     "Rhododendron macrophyllum",  "flower botanical"),
    ("huckleberry",         "Huckleberries, two ways",  "Vaccinium ovatum",           "botanical berry"),
    ("marbled-murrelet",    "Marbled murrelet",         "Brachyramphus marmoratus",   "bird"),
    ("spotted-owl",         "Northern spotted owl",     "Strix occidentalis",         "owl bird"),
    ("black-bear",          "Black bear &amp; black-tailed deer", "Ursus americanus",  "bear"),
    ("marten",              "Humboldt marten &amp; fisher", "Martes",                 "marten"),
    # ZONE 3
    ("chinook-salmon",      "Chinook salmon",           "Oncorhynchus tshawytscha",   "fish"),
    ("coho-salmon",         "Coho salmon &amp; steelhead", "Oncorhynchus kisutch",    "fish salmon"),
    ("pacific-lamprey",     "Pacific lamprey",          "Entosphenus tridentatus",    "lamprey"),
    ("american-dipper",     "American dipper",          "Cinclus mexicanus",          "bird"),
    ("river-otter",         "River otter · osprey · kingfisher · merganser", "Lontra canadensis", "otter"),
    ("giant-salamander",    "Pacific giant salamander", "Dicamptodon",                "salamander"),
    ("roughskin-newt",      "Rough-skinned newt",       "Taricha granulosa",          "newt"),
    # ZONE 4
    ("red-alder",           "Red alder",                "Alnus rubra",                "botanical leaf catkin"),
    ("salmonberry",         "Salmonberry &amp; thimbleberry", "Rubus spectabilis",    "botanical"),
    ("red-elderberry",      "Red elderberry",           "Sambucus racemosa",          "botanical berry"),
    ("poison-oak",          "Poison oak &amp; stinging nettle", "Toxicodendron diversilobum", "botanical leaf"),
    # ZONE 5
    ("pitcher-plant",       "California pitcher plant",  "Darlingtonia californica",   "botanical"),
    # ZONE 6
    ("aleutian-goose",      "Aleutian cackling goose",  "Branta canadensis",          "goose bird"),
    ("harrier",             "Waterfowl &amp; raptors",  "Circus cyaneus",             "harrier hawk bird"),
    ("sand-verbena",        "Dune plants",              "Abronia latifolia",          "botanical"),
    # ZONE 7
    ("ochre-star",          "Ochre sea star",           "Pisaster ochraceus",         "starfish"),
    ("green-anemone",       "Giant green anemone",      "Anthopleura xanthogrammica", "anemone"),
    ("chiton",              "Chitons, hermit crabs, sculpins", "Cryptochiton stelleri", "chiton"),
    ("gray-whale",          "Gray whales",              "Eschrichtius robustus",      "whale"),
    # ZONE 9
    ("chanterelle",         "Pacific golden chanterelle","Cantharellus",              "mushroom fungus"),
    ("king-bolete",         "King bolete · matsutake · candy cap", "Boletus edulis",  "mushroom fungus"),
    ("turkey-tail",         "Turkey tail &amp; artist's conk", "Trametes versicolor", "fungus"),
    ("fly-agaric",          "Fly agaric",               "Amanita muscaria",           "mushroom fungus"),
    ("death-cap",           "Death cap &amp; destroying angel", "Amanita phalloides", "mushroom fungus"),
    ("coralroot",           "The flowers that pretend to be fungi", "Corallorhiza maculata", "orchid botanical"),
]

def curl(url, timeout=60):
    r = subprocess.run(
        ["curl", "-sSL", "--max-time", str(timeout), "-A", UA, url],
        capture_output=True, timeout=timeout + 10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[:200] or "curl failed")
    return r.stdout

def api_get(params):
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    return json.loads(curl(url, timeout=40).decode("utf-8"))

PD_OK = re.compile(r"public domain|^pd\b|pd-|cc0|no known copyright|no restrictions", re.I)
PD_BAD = re.compile(r"cc[\s\-]?by|share[\s\-]?alike|attribution|gfdl|fair use|copyright(?!ed:\s*false)", re.I)
BAD_TITLE = re.compile(r"range|distribution|\bmap\b|locator|phylog|cladogram|skeleton|skull|logo|icon|stamp|coin", re.I)
GOOD_TITLE = re.compile(r"illustration|plate|drawing|botanical|flora|fauna|lithograph|engrav|sturm|britton|sargent|audubon|gould|figure|iconograph|kunstformen|nordens|bilder|zeichnung|planche", re.I)

def license_of(md):
    short = (md.get("LicenseShortName", {}) or {}).get("value", "")
    lic   = (md.get("License", {}) or {}).get("value", "")
    terms = (md.get("UsageTerms", {}) or {}).get("value", "")
    copyrighted = (md.get("Copyrighted", {}) or {}).get("value", "")
    blob = " ".join([short, lic, terms])
    is_pd = False
    if copyrighted.strip().lower() == "false":
        is_pd = True
    if PD_OK.search(blob):
        is_pd = True
    if PD_BAD.search(blob):
        is_pd = False   # any attribution/share-alike requirement disqualifies
    return is_pd, (short or lic or terms or "unknown").strip()

def artist_of(md):
    raw = (md.get("Artist", {}) or {}).get("value", "") or (md.get("Credit", {}) or {}).get("value", "")
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:120] if txt else ""

def search_candidates(query, limit=12):
    try:
        d = api_get({
            "action": "query", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": 900,
        })
    except Exception as e:
        print("   ! search error:", e); return []
    pages = (d.get("query", {}) or {}).get("pages", {}) or {}
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        out.append((p.get("title", ""), ii))
    return out

def score(title, ii):
    mime = ii.get("mime", "")
    w, h = ii.get("width", 0), ii.get("height", 0)
    s = 0
    if mime in ("image/jpeg", "image/png"):
        s += 5
    if mime == "image/svg+xml":
        s -= 50  # cannot rasterize reliably here
    if GOOD_TITLE.search(title):
        s += 6
    if BAD_TITLE.search(title):
        s -= 40
    if max(w, h) >= 600:
        s += 2
    if max(w, h) >= 1200:
        s += 1
    if w and h:
        ar = w / h
        if 0.5 <= ar <= 2.0:
            s += 1
    return s

def fetch_image(thumburl):
    return curl(thumburl, timeout=60)

def process_and_save(data, slug):
    im = Image.open(BytesIO(data))
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    # grayscale + gentle autocontrast so old scans read cleanly under the duotone CSS
    g = ImageOps.grayscale(im)
    g = ImageOps.autocontrast(g, cutoff=1)
    w, h = g.size
    target = 860
    if w > target:
        g = g.resize((target, round(h * target / w)), Image.LANCZOS)
    path = os.path.join(OUT_IMG, slug + ".jpg")
    g.convert("RGB").save(path, "JPEG", quality=82, optimize=True)
    return path, g.size

def main():
    manifest = {}
    only = set(sys.argv[1:])
    for slug, anchor, subject, hint in SPECIES:
        if only and slug not in only:
            continue
        print(f"[{slug}] {subject!r}")
        cands = []
        for q in (f'"{subject}" {hint}', f'"{subject}" illustration', subject):
            cands = search_candidates(q)
            # keep only PD candidates
            pd = []
            for title, ii in cands:
                is_pd, licname = license_of(ii.get("extmetadata", {}) or {})
                if not is_pd:
                    continue
                if not ii.get("thumburl"):
                    continue
                pd.append((score(title, ii), title, ii, licname))
            pd.sort(key=lambda x: x[0], reverse=True)
            if pd and pd[0][0] > -20:
                cands = pd
                break
            time.sleep(0.3)
        if not cands or isinstance(cands[0], tuple) and len(cands[0]) == 2:
            print("   -> NO PD CANDIDATE"); manifest[slug] = {"status": "MISSING", "anchor": anchor, "subject": subject}
            continue
        sc, title, ii, licname = cands[0]
        try:
            data = fetch_image(ii["thumburl"])
            path, size = process_and_save(data, slug)
        except Exception as e:
            print("   ! download/process error:", e)
            manifest[slug] = {"status": "MISSING", "anchor": anchor, "subject": subject, "error": str(e)}
            continue
        artist = artist_of(ii.get("extmetadata", {}) or {})
        descurl = ii.get("descriptionurl", "")
        print(f"   -> {title}  [{licname}]  score={sc}  {size}")
        manifest[slug] = {
            "status": "ok", "anchor": anchor, "subject": subject,
            "file": f"plates/{slug}.jpg", "title": title,
            "license": licname, "artist": artist,
            "source": descurl, "score": sc,
        }
        time.sleep(0.4)
    with open(OUT_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    ok = sum(1 for v in manifest.values() if v.get("status") == "ok")
    print(f"\nDONE: {ok}/{len(manifest)} sourced. Manifest -> {OUT_MANIFEST}")

if __name__ == "__main__":
    main()
