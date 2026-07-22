#!/usr/bin/env python3
import json, os, re, subprocess, time, urllib.parse
from io import BytesIO
from PIL import Image, ImageOps
HERE=os.path.dirname(os.path.abspath(__file__)); C3=os.path.join(HERE,"cand3"); os.makedirs(C3,exist_ok=True)
UA="jed-fieldguide-plates/1.0 (personal project; +https://github.com/zchryd/jed)"; API="https://commons.wikimedia.org/w/api.php"
JOBS={
 "coast-redwood":(["Sequoia sempervirens foliage","Sequoia sempervirens Curtis botanical","Sequoia sempervirens plate","Wellingtonia gigantea plate"],{"sequoia","redwood","wellingtonia"}),
 "sword-fern":(["Aspidium munitum","Polystichum munitum Hooker","Polystichum munitum plate","Dryopteris munita fern"],{"polystichum","aspidium","dryopteris","munit"}),
 "sitka-spruce":(["Picea sitchensis Sargent","Abies menziesii plate","Picea sitchensis plate cone","Pinus menziesii plate"],{"picea","sitchensis","abies","menziesii"}),
 "grand-fir":(["Abies grandis plate","Picea grandis plate","Abies grandis Lambert","Abies grandis cone foliage"],{"abies","grandis"}),
 "spotted-owl":(["Syrnium occidentale","Strix occidentalis plate","Ptynx occidentalis","Syrnium occidentale Cassin"],{"strix","syrnium","ptynx","occidental"}),
 "black-bear":(["American Black Bear Audubon","Ursus americanus Bachman","Ursus americanus quadrupeds plate","Ursus americanus lithograph"],{"ursus"}),
 "roughskin-newt":(["Triton torosus","Taricha torosa plate","Diemyctylus torosus","Notophthalmus newt plate"],{"triton","taricha","torosus","diemyctylus","notophthalmus"}),
 "red-alder":(["Alnus oregona","Alnus rubra Sargent","Alnus rubra plate","Alnus oregona Silva"],{"alnus"}),
}
def curl(u,t=60):
    r=subprocess.run(["curl","-sSL","--max-time",str(t),"-A",UA,u],capture_output=True,timeout=t+10)
    if r.returncode: raise RuntimeError((r.stderr.decode('utf-8','replace')[:150]) or "curl")
    return r.stdout
def api(p): p={**p,"format":"json"}; return json.loads(curl(API+"?"+urllib.parse.urlencode(p),40).decode())
PD_OK=re.compile(r"public domain|^pd\b|pd-|cc0|no known copyright|no restrictions",re.I)
PD_BAD=re.compile(r"cc[\s\-]?by|share[\s\-]?alike|attribution required|gfdl|fair use",re.I)
DOC=re.compile(r"\bcover\b|title page|frontispiece|\breport\b|document|\bpage\b|portrait|\bmap\b|\bseal\b|life history of|studies of",re.I)
ILLO=re.compile(r"illustration|\bplate\b|drawing|lithograph|engrav|botanical|silva|sargent|audubon|hooker|curtis|cassin|figure|tafel",re.I)
CAM={"Make","Model","FNumber","ExposureTime","ISOSpeedRatings","FocalLength","LensModel"}
def is_pd(md):
    blob=" ".join([(md.get(k,{}) or {}).get("value","") for k in("LicenseShortName","License","UsageTerms")])
    cr=(md.get("Copyrighted",{}) or {}).get("value",""); pd=False
    if cr.strip().lower()=="false": pd=True
    if PD_OK.search(blob): pd=True
    if PD_BAD.search(blob): pd=False
    return pd,((md.get("LicenseShortName",{}) or {}).get("value","") or "unknown").strip()
def cam(m): return bool(m) and len({x.get("name") for x in m if isinstance(x,dict)} & CAM)>=2
def art(md):
    raw=(md.get("Artist",{}) or {}).get("value","") or (md.get("Credit",{}) or {}).get("value","")
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",raw)).strip()[:140]
def search(q,tok):
    try:
        d=api({"action":"query","generator":"search","gsrsearch":q,"gsrnamespace":6,"gsrlimit":15,
               "prop":"imageinfo|categories","cllimit":"max","iiprop":"url|mime|size|extmetadata|metadata",
               "iiextmetadatafilter":"LicenseShortName|License|UsageTerms|Copyrighted|Artist|Credit","iiurlwidth":480})
    except Exception as e: print("  !",e); return []
    out=[]
    for p in ((d.get("query",{}) or {}).get("pages",{}) or {}).values():
        ii=(p.get("imageinfo") or [None])[0]
        if not ii: continue
        title=p.get("title",""); cats=[c.get("title","").replace("Category:","") for c in (p.get("categories") or [])]
        pd,lic=is_pd(ii.get("extmetadata",{}) or {})
        if not pd or not ii.get("thumburl"): continue
        hay=(title+" "+" ".join(cats)).lower(); rel=any(t in hay for t in tok)
        s=0
        if ii.get("mime") in ("image/jpeg","image/png"): s+=4
        elif ii.get("mime")=="image/svg+xml": s-=60
        if cam(ii.get("metadata")): s-=55
        if ILLO.search(title): s+=8
        if DOC.search(title): s-=55
        if not rel: s-=120
        if max(ii.get("width",0),ii.get("height",0))>=500: s+=2
        out.append({"title":title,"sc":s,"lic":lic,"artist":art(ii.get("extmetadata",{}) or {}),
                    "thumb":ii["thumburl"],"src":ii.get("descriptionurl",""),"cam":cam(ii.get("metadata")),"rel":rel})
    seen=set(); ded=[]
    for c in sorted(out,key=lambda x:x["sc"],reverse=True):
        if c["title"] in seen: continue
        seen.add(c["title"]); ded.append(c)
    return ded
def save(u,p):
    im=Image.open(BytesIO(curl(u,60))); im=ImageOps.exif_transpose(im)
    if im.mode in("RGBA","LA","P"):
        bg=Image.new("RGB",im.size,(255,255,255)); im=im.convert("RGBA"); bg.paste(im,mask=im.split()[-1]); im=bg
    else: im=im.convert("RGB")
    im.thumbnail((460,460)); im.save(p,"JPEG",quality=84)
res={}
for slug,(qs,tok) in JOBS.items():
    best=[]
    for q in qs:
        r=search(q,tok)
        if r: 
            best=r
            if r[0]["sc"]>=8: break
        time.sleep(0.2)
    keep=best[:4]; cand=[]
    for i,c in enumerate(keep):
        p=f"cand3/{slug}__{i}.jpg"
        try: save(c["thumb"],os.path.join(HERE,p)); c["file"]=p; cand.append(c)
        except Exception as e: print("  !thumb",slug,i,e)
        time.sleep(0.15)
    res[slug]={"cand":cand}
    print(f"[{slug}] {len(cand)} "+" ".join(f"[{i}:{c['sc']}{'r' if c['rel'] else ''}]" for i,c in enumerate(cand)))
    time.sleep(0.2)
json.dump(res,open(os.path.join(HERE,"micro.json"),"w"),indent=1,ensure_ascii=False)
print("DONE")
