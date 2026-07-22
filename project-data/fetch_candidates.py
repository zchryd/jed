#!/usr/bin/env python3
"""v2: fetch up to N public-domain CANDIDATE images per species so a human can
visually pick the real engraving/plate. Adds an EXIF-camera filter (rejects
photographs) and document/portrait/cover rejection. Downloads all kept
candidates as cand/<slug>__<i>.jpg and writes candidates.json.
"""
import json, os, re, subprocess, time, urllib.parse
from io import BytesIO
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.join(HERE, "cand"); os.makedirs(CAND, exist_ok=True)
UA = "jed-fieldguide-plates/1.0 (personal trip guide; contact [redacted])"
API = "https://commons.wikimedia.org/w/api.php"

# import the species list from v1 to stay in sync
import importlib.util
spec = importlib.util.spec_from_file_location("fp", os.path.join(HERE, "fetch_plates.py"))
fp = importlib.util.module_from_spec(spec); spec.loader.exec_module(fp)
SPECIES = fp.SPECIES

# per-species query overrides to steer toward illustration-rich collections
OVERRIDE = {
    "coast-redwood":   ['"Sequoia sempervirens" (Sargent OR Silva OR plate OR botanical)'],
    "sword-fern":      ['"Polystichum munitum" (plate OR botanical OR fern)'],
    "western-trillium":['"Trillium ovatum" (plate OR botanical OR flora)'],
    "bead-lily":       ['"Clintonia" (plate OR botanical OR Curtis)'],
    "banana-slug":     ['Ariolimax (plate OR mollusca OR illustration)', 'Arion (plate OR illustration)'],
    "pacific-wren":    ['Troglodytes (plate OR Audubon OR Gould)'],
    "wandering-salamander":['Aneides (plate OR illustration)', 'Plethodontidae plate'],
    "douglas-fir":     ['"Pseudotsuga" (Sargent OR Silva OR plate)'],
    "western-hemlock": ['"Tsuga" (Sargent OR Silva OR plate)'],
    "sitka-spruce":    ['"Picea sitchensis" (Sargent OR Silva OR plate)', 'Picea (plate OR Silva)'],
    "grand-fir":       ['"Abies grandis" (Sargent OR Silva OR plate)', 'Abies (plate OR Silva)'],
    "port-orford-cedar":['"Chamaecyparis lawsoniana" (Sargent OR Silva OR plate)'],
    "madrone":         ['"Arbutus menziesii" (plate OR botanical OR Silva)'],
    "rhododendron":    ['"Rhododendron macrophyllum" (plate OR Curtis OR botanical)', 'Rhododendron californicum plate'],
    "huckleberry":     ['"Vaccinium ovatum" (plate OR botanical)', 'Vaccinium (plate OR botanical illustration)'],
    "marbled-murrelet":['Brachyramphus (plate OR Gould OR Baird)', 'murrelet plate'],
    "spotted-owl":     ['"Strix occidentalis" (plate OR Audubon)', 'Syrnium occidentale plate'],
    "black-bear":      ['"Ursus americanus" (Audubon OR quadrupeds OR plate)'],
    "marten":          ['Martes (Audubon OR quadrupeds OR plate)', 'Mustela martes plate'],
    "chinook-salmon":  ['Oncorhynchus (plate OR Jordan OR fishes)', 'salmon plate fishes'],
    "coho-salmon":     ['"Oncorhynchus kisutch" (plate OR fishes)', 'salmon plate Jordan Evermann'],
    "pacific-lamprey": ['Petromyzon (plate OR fishes)', 'lamprey plate illustration'],
    "american-dipper": ['Cinclus (plate OR Audubon OR Baird)', 'water ouzel plate'],
    "river-otter":     ['Lutra (Audubon OR quadrupeds OR plate)', 'otter plate illustration'],
    "giant-salamander":['Dicamptodon (plate OR illustration)', 'Amblystoma plate'],
    "roughskin-newt":  ['Taricha (plate OR illustration)', 'Triton newt plate'],
    "red-alder":       ['"Alnus rubra" (plate OR Sargent OR Silva OR botanical)', 'Alnus oregona plate'],
    "salmonberry":     ['"Rubus spectabilis" (plate OR botanical OR Curtis)'],
    "red-elderberry":  ['"Sambucus racemosa" (plate OR botanical)', 'Sambucus plate botanical'],
    "poison-oak":      ['"Rhus diversiloba" (plate OR botanical)', 'Toxicodendron plate botanical'],
    "pitcher-plant":   ['"Darlingtonia californica" (plate OR Curtis OR botanical magazine OR Hooker)'],
    "aleutian-goose":  ['Branta (plate OR Audubon)', 'Bernicla plate goose'],
    "harrier":         ['Circus (plate OR Audubon OR Gould)', 'marsh hawk plate'],
    "sand-verbena":    ['Abronia (plate OR botanical)'],
    "ochre-star":      ['Pisaster (plate OR illustration)', 'Asterias plate starfish'],
    "green-anemone":   ['Anthopleura (plate OR illustration)', 'Actinia anemone plate Gosse'],
    "chiton":          ['Cryptochiton (plate OR illustration)', 'Chiton plate mollusca'],
    "gray-whale":      ['"Eschrichtius" (plate OR illustration)', 'Rhachianectes gray whale plate'],
    "chanterelle":     ['Cantharellus (plate OR fungi OR illustration)', 'Cantharellus cibarius plate'],
    "king-bolete":     ['Boletus edulis (plate OR fungi OR illustration)'],
    "turkey-tail":     ['Polyporus versicolor plate', 'Trametes versicolor plate fungi'],
    "fly-agaric":      ['Amanita muscaria (plate OR fungi OR illustration)'],
    "death-cap":       ['Amanita phalloides (plate OR fungi OR illustration)'],
    "coralroot":       ['Corallorhiza (plate OR botanical OR orchid)'],
}

def curl(url, timeout=60):
    r = subprocess.run(["curl","-sSL","--max-time",str(timeout),"-A",UA,url],
                       capture_output=True, timeout=timeout+10)
    if r.returncode != 0:
        raise RuntimeError((r.stderr.decode('utf-8','replace')[:200]) or "curl failed")
    return r.stdout

def api(params):
    params={**params,"format":"json"}
    return json.loads(curl(API+"?"+urllib.parse.urlencode(params),40).decode("utf-8"))

PD_OK  = re.compile(r"public domain|^pd\b|pd-|cc0|no known copyright|no restrictions", re.I)
PD_BAD = re.compile(r"cc[\s\-]?by|share[\s\-]?alike|attribution required|gfdl|fair use", re.I)
DOC_BAD= re.compile(r"\bcover\b|title page|frontispiece|gazette|bulletin|\breport\b|atlas|reconnaissance|document|\bpage\b|portrait|\bmap\b|distribution|range map|herbarium|specimen sheet|stamp|logo|\bseal\b|photograph of|scan of page", re.I)
ILLO_OK= re.compile(r"illustration|\bplate\b|\bpl\.\b|\btab\.\b|drawing|lithograph|engrav|botanical|\bfauna\b|\bflora\b|iconograph|sargent|silva|audubon|gould|curtis|hooker|jordan|evermann|baird|figure|planche|tafel", re.I)
CAM_TAGS = {"Make","Model","FNumber","ExposureTime","ISOSpeedRatings","FocalLength","LensModel","ApertureValue","ShutterSpeedValue","ExposureProgram"}

def is_pd(md):
    short=(md.get("LicenseShortName",{}) or {}).get("value","")
    lic=(md.get("License",{}) or {}).get("value","")
    terms=(md.get("UsageTerms",{}) or {}).get("value","")
    cr=(md.get("Copyrighted",{}) or {}).get("value","")
    blob=" ".join([short,lic,terms])
    pd=False
    if cr.strip().lower()=="false": pd=True
    if PD_OK.search(blob): pd=True
    if PD_BAD.search(blob): pd=False
    return pd,(short or lic or terms or "unknown").strip()

def has_camera_exif(meta):
    if not meta: return False
    names={m.get("name") for m in meta if isinstance(m,dict)}
    return len(names & CAM_TAGS) >= 2

def artist(md):
    raw=(md.get("Artist",{}) or {}).get("value","") or (md.get("Credit",{}) or {}).get("value","")
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",raw)).strip()[:140]

def score(title, cats, ii, subject):
    mime=ii.get("mime",""); w,h=ii.get("width",0),ii.get("height",0)
    s=0
    if mime in ("image/jpeg","image/png"): s+=4
    if mime=="image/svg+xml": s-=60
    if mime=="application/pdf" or mime=="image/tiff": s-=40
    if has_camera_exif(ii.get("metadata")): s-=55            # it's a photograph
    catblob=" ".join(cats).lower()
    if "photograph" in catblob: s-=25
    if re.search(r"illustration|lithograph|botanical illustration|biodiversity heritage|plates from|zoological illustration|mycological", catblob): s+=12
    if ILLO_OK.search(title): s+=8
    if DOC_BAD.search(title): s-=55
    # subject name present in title
    for tok in subject.lower().split():
        if len(tok)>3 and tok in title.lower(): s+=2
    if max(w,h)>=500: s+=2
    if w and h and 0.45<=w/h<=2.2: s+=1
    return s

def search(query, subject, limit=15):
    try:
        d=api({"action":"query","generator":"search","gsrsearch":query,
               "gsrnamespace":6,"gsrlimit":limit,"prop":"imageinfo|categories",
               "cllimit":"max",
               "iiprop":"url|mime|size|extmetadata|metadata",
               "iiextmetadatafilter":"LicenseShortName|License|UsageTerms|Copyrighted|Artist|Credit",
               "iiurlwidth":480})
    except Exception as e:
        print("   ! search err",e); return []
    pages=(d.get("query",{}) or {}).get("pages",{}) or {}
    out=[]
    for p in pages.values():
        ii=(p.get("imageinfo") or [None])[0]
        if not ii: continue
        cats=[c.get("title","").replace("Category:","") for c in (p.get("categories") or [])]
        pd,lic=is_pd(ii.get("extmetadata",{}) or {})
        if not pd or not ii.get("thumburl"): continue
        out.append({"title":p.get("title",""),"sc":score(p.get("title",""),cats,ii,subject),
                    "lic":lic,"artist":artist(ii.get("extmetadata",{}) or {}),
                    "thumb":ii["thumburl"],"src":ii.get("descriptionurl",""),
                    "mime":ii.get("mime",""),"cam":has_camera_exif(ii.get("metadata"))})
    # dedup by title, sort by score
    seen=set(); ded=[]
    for c in sorted(out,key=lambda x:x["sc"],reverse=True):
        if c["title"] in seen: continue
        seen.add(c["title"]); ded.append(c)
    return ded

def save_thumb(url, path):
    data=curl(url,60)
    im=Image.open(BytesIO(data))
    im=ImageOps.exif_transpose(im)
    if im.mode in ("RGBA","LA","P"):
        bg=Image.new("RGB",im.size,(255,255,255)); im=im.convert("RGBA"); bg.paste(im,mask=im.split()[-1]); im=bg
    else: im=im.convert("RGB")
    im.thumbnail((460,460))
    im.save(path,"JPEG",quality=84)

def main():
    catalog={}
    for slug,anchor,subject,hint in SPECIES:
        queries = OVERRIDE.get(slug, []) + [f'"{subject}" {hint}', subject]
        best=[]
        for q in queries:
            best = search(q, subject)
            if best and best[0]["sc"]>=6:  # decent illustration found
                break
            time.sleep(0.2)
        keep=best[:4]
        cand=[]
        for i,c in enumerate(keep):
            p=f"cand/{slug}__{i}.jpg"
            try:
                save_thumb(c["thumb"], os.path.join(HERE,p)); c["file"]=p; cand.append(c)
            except Exception as e:
                print("   ! thumb err",slug,i,e)
            time.sleep(0.15)
        catalog[slug]={"anchor":anchor,"subject":subject,"cand":cand}
        tags=" ".join(f"[{i}:{c['sc']}{'C' if c['cam'] else ''}]" for i,c in enumerate(cand))
        print(f"[{slug}] {len(cand)} cand {tags}")
        time.sleep(0.2)
    json.dump(catalog, open(os.path.join(HERE,"candidates.json"),"w"), indent=1, ensure_ascii=False)
    print("\nDONE ->", os.path.join(HERE,"candidates.json"))

if __name__=="__main__":
    main()
