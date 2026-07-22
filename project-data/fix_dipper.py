import json, os, re, subprocess, time, urllib.parse
from io import BytesIO
from PIL import Image, ImageOps
HERE=os.path.dirname(os.path.abspath(__file__)); FX=os.path.join(HERE,"fix"); os.makedirs(FX,exist_ok=True)
UA="jed-fieldguide-plates/1.0 (personal trip guide; contact [redacted])"; API="https://commons.wikimedia.org/w/api.php"
QS=['Cinclus mexicanus plate bird','American Dipper Audubon','water ouzel Audubon plate','Cinclus americanus plate','Cinclus mexicanus illustration']
TOK={"cinclus","ouzel","dipper"}
def curl(u,t=45):
    r=subprocess.run(["curl","-sSL","--max-time",str(t),"-A",UA,u],capture_output=True,timeout=t+8)
    if r.returncode: raise RuntimeError("curl")
    return r.stdout
def api(p): p={**p,"format":"json"}; return json.loads(curl(API+"?"+urllib.parse.urlencode(p),35).decode())
PD_OK=re.compile(r"public domain|^pd\b|pd-|cc0|no known copyright|no restrictions",re.I)
PD_BAD=re.compile(r"cc[\s\-]?by|share[\s\-]?alike|attribution required|gfdl|fair use",re.I)
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
def save(u,p):
    im=Image.open(BytesIO(curl(u,50))); im=ImageOps.exif_transpose(im)
    if im.mode in("RGBA","LA","P"):
        bg=Image.new("RGB",im.size,(255,255,255)); im=im.convert("RGBA"); bg.paste(im,mask=im.split()[-1]); im=bg
    else: im=im.convert("RGB")
    im.thumbnail((520,520)); im.save(p,"JPEG",quality=86)
best=[]
for q in QS:
    try:
        d=api({"action":"query","generator":"search","gsrsearch":q,"gsrnamespace":6,"gsrlimit":12,
               "prop":"imageinfo|categories","cllimit":"max","iiprop":"url|mime|size|extmetadata|metadata",
               "iiextmetadatafilter":"LicenseShortName|License|UsageTerms|Copyrighted|Artist|Credit","iiurlwidth":520})
    except Exception as e: print("!",e); continue
    cur=[]
    for p in ((d.get("query",{}) or {}).get("pages",{}) or {}).values():
        ii=(p.get("imageinfo") or [None])[0]
        if not ii: continue
        title=p.get("title",""); cats=[cc.get("title","").replace("Category:","") for cc in (p.get("categories") or [])]
        pd,lic=is_pd(ii.get("extmetadata",{}) or {})
        if not pd or not ii.get("thumburl"): continue
        hay=(title+" "+" ".join(cats)).lower()
        if not any(t in hay for t in TOK): continue
        if cam(ii.get("metadata")): continue
        if re.search(r"\bcover\b|title page|\.pdf|\bmap\b|distribution",title,re.I): continue
        w,h=ii.get("width",0),ii.get("height",0)
        s=8 if re.search(r"plate|audubon|illustration|lithograph|drawing|birds",title,re.I) else 2
        if w and h and 0.55<=w/h<=1.7: s+=2   # prefer full-frame not tiny inset pages
        cur.append({"title":title,"sc":s,"lic":lic,"artist":art(ii.get("extmetadata",{}) or {}),
                    "thumb":ii["thumburl"],"src":ii.get("descriptionurl","")})
    if cur:
        seen=set(); cur=[x for x in sorted(cur,key=lambda z:z["sc"],reverse=True) if not (x["title"] in seen or seen.add(x["title"]))]
        best=cur
        if cur[0]["sc"]>=10 and len(cur)>=3: break
    time.sleep(0.2)
dp=[]
for i,cc in enumerate(best[:5]):
    p=f"fix/american-dipper__{i}.jpg"
    try: save(cc["thumb"],os.path.join(HERE,p)); cc["file"]=p; dp.append(cc)
    except Exception as e: print("!",i,e)
    time.sleep(0.12)
fx=json.load(open(os.path.join(HERE,"fix.json"))); fx["american-dipper"]=dp
json.dump(fx,open(os.path.join(HERE,"fix.json"),"w"),indent=1,ensure_ascii=False)
print("dipper:", " | ".join(f"#{i} {x['title'][:44]}" for i,x in enumerate(dp)))
print("DONE")
