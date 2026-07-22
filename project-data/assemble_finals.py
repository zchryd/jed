import json, os, importlib.util
from PIL import Image, ImageOps
HERE=os.path.dirname(os.path.abspath(__file__))
FF=os.path.join(HERE,"flora_fauna"); os.makedirs(FF,exist_ok=True)
spec=importlib.util.spec_from_file_location("fp",os.path.join(HERE,"fetch_plates.py"))
fp=importlib.util.module_from_spec(spec); spec.loader.exec_module(fp)
ANCHOR={s[0]:(s[1],s[2]) for s in fp.SPECIES}   # slug -> (anchor, subject)

CAND=json.load(open(os.path.join(HERE,"candidates.json")))
REQ =json.load(open(os.path.join(HERE,"requery.json")))
MIC =json.load(open(os.path.join(HERE,"micro.json")))
V1  =json.load(open(os.path.join(HERE,"plates_manifest.json")))

PICKS={
 "redwood-sorrel":("V1",None),"western-trillium":("REQ",2),
 "varied-thrush":("CAND",3),"pacific-wren":("REQ",0),"western-hemlock":("CAND",0),
 "grand-fir":("MIC",0),"port-orford-cedar":("V1",None),"madrone":("CAND",0),
 "rhododendron":("CAND",0),"marbled-murrelet":("REQ",0),
 "black-bear":("MIC",1),"marten":("CAND",0),"chinook-salmon":("CAND",0),
 # NOTE: bead-lily and huckleberry dropped — their only PD candidates were
 # wrong species (epiphytic fern; Cucubalus baccifer). coho uses a labelled
 # coho plate, not the chum (O. keta) that scored highest.
 "coho-salmon":("CAND",2),"pacific-lamprey":("CAND",0),"american-dipper":("REQ",0),
 "river-otter":("CAND",0),"giant-salamander":("V1",None),"salmonberry":("V1",None),
 "red-elderberry":("CAND",1),"poison-oak":("CAND",1),"pitcher-plant":("CAND",1),
 "aleutian-goose":("V1",None),"harrier":("REQ",0),"sand-verbena":("V1",None),
 "ochre-star":("V1",None),"green-anemone":("REQ",0),"chiton":("REQ",0),
 "gray-whale":("CAND",1),"chanterelle":("CAND",0),"king-bolete":("CAND",0),
 "turkey-tail":("CAND",0),"fly-agaric":("CAND",0),"death-cap":("CAND",1),"coralroot":("CAND",0),
}
# human-readable source names for plates whose Commons filename is a bare scan id
CREDIT={
 "death-cap":"Cooke, Illustrations of British Fungi (Amanita phalloides)",
 "coho-salmon":"Coho salmon — fisheries plate (Evermann & Goldsborough)",
 "pacific-wren":"Winter Wren & Rock Wren — bird plate",
 "poison-oak":"Poison-oak — The New Student's Reference Work",
 "huckleberry":None,
}
def resolve(slug,src,idx):
    if src=="V1":
        m=V1[slug]; return os.path.join(HERE,m["file"]), m["title"], m["license"], m.get("artist",""), m.get("source","")
    j={"CAND":CAND,"REQ":REQ,"MIC":MIC}[src]
    c=j[slug]["cand"][idx]
    return os.path.join(HERE,c["file"]), c["title"], c["lic"], c.get("artist",""), c.get("src","")

final={}
for slug,(src,idx) in PICKS.items():
    path,title,lic,artist,source=resolve(slug,src,idx)
    im=Image.open(path); im=ImageOps.exif_transpose(im)
    if im.mode in ("RGBA","LA","P"):
        bg=Image.new("RGB",im.size,(255,255,255)); im=im.convert("RGBA"); bg.paste(im,mask=im.split()[-1]); im=bg
    else: im=im.convert("RGB")
    g=ImageOps.autocontrast(ImageOps.grayscale(im),cutoff=1)
    w,h=g.size
    if w>460: g=g.resize((460,round(h*460/w)),Image.LANCZOS)
    out=os.path.join(FF,slug+".jpg"); g.convert("RGB").save(out,"JPEG",quality=80,optimize=True)
    anc,subj=ANCHOR[slug]
    clean=title.replace("File:","").strip()
    final[slug]={"anchor":anc,"subject":subj,"file":f"flora_fauna/{slug}.jpg",
                 "title":clean,"credit":CREDIT.get(slug) or None,
                 "license":lic,"artist":artist,"source":source,"src":src,"idx":idx}
json.dump(final,open(os.path.join(HERE,"plates_final.json"),"w"),indent=1,ensure_ascii=False)
SKIP=["coast-redwood","douglas-fir","sword-fern","sitka-spruce","spotted-owl","roughskin-newt",
      "red-alder","banana-slug","wandering-salamander","bead-lily","huckleberry"]
print(f"assembled {len(final)} plates; skipped {len(SKIP)}: {', '.join(SKIP)}")
tot=sum(os.path.getsize(os.path.join(FF,f)) for f in os.listdir(FF))
print(f"flora_fauna total: {tot/1024:.0f} KB across {len(os.listdir(FF))} files")
