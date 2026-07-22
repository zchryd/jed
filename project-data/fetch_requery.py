#!/usr/bin/env python3
"""Targeted re-query for species whose plates live under historical synonyms.
Adds a RELEVANCE GATE: a candidate is rejected unless the subject's tokens
appear in its title or categories (kills topic-drift junk). Writes cand2/ and
requery.json."""
import json, os, re, subprocess, time, urllib.parse
from io import BytesIO
from PIL import Image, ImageOps

HERE=os.path.dirname(os.path.abspath(__file__))
C2=os.path.join(HERE,"cand2"); os.makedirs(C2,exist_ok=True)
UA="jed-fieldguide-plates/1.0 (personal project; +https://github.com/zchryd/jed)"
API="https://commons.wikimedia.org/w/api.php"

# slug -> (queries[], relevance-token-set)
JOBS={
 "coast-redwood":(["Sequoia sempervirens Silva","Sequoia sempervirens Sargent","Sequoia sempervirens botanical plate"],{"sequoia"}),
 "sword-fern":(["Polystichum munitum plate","Aspidium munitum","Polystichum munitum illustration"],{"polystichum","aspidium","munitum"}),
 "western-trillium":(["Trillium ovatum plate","Trillium ovatum botanical","Trillium ovatum illustration"],{"trillium"}),
 "pacific-wren":(["Troglodytes hyemalis plate","winter wren Audubon plate","Anorthura troglodytes plate"],{"troglodytes","wren","anorthura"}),
 "sitka-spruce":(["Picea sitchensis Silva","Abies sitchensis plate","Picea sitchensis botanical"],{"picea","sitchensis","abies"}),
 "grand-fir":(["Abies grandis Silva","Abies grandis plate","Picea grandis plate"],{"abies","grandis"}),
 "marbled-murrelet":(["Brachyramphus marmoratus plate","Brachyramphus plate bird","marbled murrelet illustration"],{"brachyramphus","murrelet"}),
 "spotted-owl":(["Syrnium occidentale plate","Strix occidentalis plate","spotted owl Audubon plate"],{"strix","syrnium","occidental","owl"}),
 "black-bear":(["Ursus americanus Audubon quadrupeds","American black bear plate","Ursus americanus plate"],{"ursus","bear"}),
 "american-dipper":(["Cinclus mexicanus plate","water ouzel Audubon plate","Cinclus americanus plate"],{"cinclus","ouzel","dipper"}),
 "roughskin-newt":(["Taricha torosa plate","Triton torosus plate","Diemyctylus newt plate"],{"taricha","triton","diemyctylus","newt","salamand"}),
 "red-alder":(["Alnus oregona plate","Alnus rubra Silva","Alnus rubra plate"],{"alnus"}),
 "harrier":(["Circus hudsonius plate","marsh hawk Audubon plate","Circus cyaneus plate"],{"circus","harrier","hawk"}),
 "green-anemone":(["Anthopleura plate","Actinia Gosse anemone plate","sea anemone Actinologia plate"],{"anthopleura","actinia","anemone"}),
 "chiton":(["Cryptochiton plate","Chiton Sowerby plate","Chiton Amphineura plate mollusca"],{"chiton","cryptochiton"}),
 "banana-slug":(["Ariolimax plate","Ariolimax columbianus illustration","Limax slug plate mollusca"],{"ariolimax","limax","slug"}),
 "wandering-salamander":(["Aneides lugubris plate","Autodax salamander plate","Aneides plate amphibian"],{"aneides","autodax","salamand"}),
}

def curl(url,t=60):
    r=subprocess.run(["curl","-sSL","--max-time",str(t),"-A",UA,url],capture_output=True,timeout=t+10)
    if r.returncode: raise RuntimeError((r.stderr.decode('utf-8','replace')[:200]) or "curl fail")
    return r.stdout
def api(p):
    p={**p,"format":"json"}; return json.loads(curl(API+"?"+urllib.parse.urlencode(p),40).decode("utf-8"))

PD_OK=re.compile(r"public domain|^pd\b|pd-|cc0|no known copyright|no restrictions",re.I)
PD_BAD=re.compile(r"cc[\s\-]?by|share[\s\-]?alike|attribution required|gfdl|fair use",re.I)
DOC_BAD=re.compile(r"\bcover\b|title page|frontispiece|gazette|bulletin|\breport\b|atlas|document|\bpage\b|portrait|\bmap\b|herbarium|specimen sheet|\bseal\b",re.I)
ILLO_OK=re.compile(r"illustration|\bplate\b|drawing|lithograph|engrav|botanical|\bfauna\b|\bflora\b|iconograph|sargent|silva|audubon|gould|curtis|hooker|jordan|baird|figure|planche|tafel",re.I)
CAM={"Make","Model","FNumber","ExposureTime","ISOSpeedRatings","FocalLength","LensModel","ApertureValue","ShutterSpeedValue"}

def is_pd(md):
    blob=" ".join([(md.get(k,{}) or {}).get("value","") for k in("LicenseShortName","License","UsageTerms")])
    cr=(md.get("Copyrighted",{}) or {}).get("value","")
    pd=False
    if cr.strip().lower()=="false": pd=True
    if PD_OK.search(blob): pd=True
    if PD_BAD.search(blob): pd=False
    short=(md.get("LicenseShortName",{}) or {}).get("value","")
    return pd,(short or "unknown").strip()
def cam_exif(meta):
    if not meta: return False
    return len({m.get("name") for m in meta if isinstance(m,dict)} & CAM)>=2
def artist(md):
    raw=(md.get("Artist",{}) or {}).get("value","") or (md.get("Credit",{}) or {}).get("value","")
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",raw)).strip()[:140]

def search(q,tokens):
    try:
        d=api({"action":"query","generator":"search","gsrsearch":q,"gsrnamespace":6,"gsrlimit":15,
               "prop":"imageinfo|categories","cllimit":"max",
               "iiprop":"url|mime|size|extmetadata|metadata",
               "iiextmetadatafilter":"LicenseShortName|License|UsageTerms|Copyrighted|Artist|Credit",
               "iiurlwidth":480})
    except Exception as e:
        print("  ! ",e); return []
    out=[]
    for p in ((d.get("query",{}) or {}).get("pages",{}) or {}).values():
        ii=(p.get("imageinfo") or [None])[0]
        if not ii: continue
        title=p.get("title","")
        cats=[c.get("title","").replace("Category:","") for c in (p.get("categories") or [])]
        pd,lic=is_pd(ii.get("extmetadata",{}) or {})
        if not pd or not ii.get("thumburl"): continue
        hay=(title+" "+" ".join(cats)).lower()
        relevant=any(t in hay for t in tokens)
        s=0
        if ii.get("mime") in ("image/jpeg","image/png"): s+=4
        elif ii.get("mime")=="image/svg+xml": s-=60
        if cam_exif(ii.get("metadata")): s-=55
        if "photograph" in " ".join(cats).lower(): s-=25
        if ILLO_OK.search(title): s+=8
        if DOC_BAD.search(title): s-=55
        if not relevant: s-=200          # RELEVANCE GATE
        w,h=ii.get("width",0),ii.get("height",0)
        if max(w,h)>=500: s+=2
        out.append({"title":title,"sc":s,"lic":lic,"artist":artist(ii.get("extmetadata",{}) or {}),
                    "thumb":ii["thumburl"],"src":ii.get("descriptionurl",""),"cam":cam_exif(ii.get("metadata")),
                    "rel":relevant})
    seen=set(); ded=[]
    for c in sorted(out,key=lambda x:x["sc"],reverse=True):
        if c["title"] in seen: continue
        seen.add(c["title"]); ded.append(c)
    return ded
def save(url,path):
    im=Image.open(BytesIO(curl(url,60))); im=ImageOps.exif_transpose(im)
    if im.mode in("RGBA","LA","P"):
        bg=Image.new("RGB",im.size,(255,255,255)); im=im.convert("RGBA"); bg.paste(im,mask=im.split()[-1]); im=bg
    else: im=im.convert("RGB")
    im.thumbnail((460,460)); im.save(path,"JPEG",quality=84)

def main():
    res={}
    for slug,(queries,tokens) in JOBS.items():
        best=[]
        for q in queries:
            r=search(q,tokens)
            r=[c for c in r if c["sc"]>-100]     # drop gated-out
            if r: best=r
            if r and r[0]["sc"]>=8: break
            time.sleep(0.2)
        keep=best[:3]; cand=[]
        for i,c in enumerate(keep):
            p=f"cand2/{slug}__{i}.jpg"
            try: save(c["thumb"],os.path.join(HERE,p)); c["file"]=p; cand.append(c)
            except Exception as e: print("  ! thumb",slug,i,e)
            time.sleep(0.15)
        res[slug]={"cand":cand}
        print(f"[{slug}] {len(cand)} cand "+" ".join(f"[{i}:{c['sc']}{'C' if c['cam'] else ''}]" for i,c in enumerate(cand)))
        time.sleep(0.2)
    json.dump(res,open(os.path.join(HERE,"requery.json"),"w"),indent=1,ensure_ascii=False)
    print("\nDONE")
if __name__=="__main__": main()
