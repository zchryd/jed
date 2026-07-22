#!/usr/bin/env python3
"""Inject the 36 verified public-domain plates into Field Guide.html:
 - SVG duotone filter (paper->emerald ink) so mixed-era plates read as one set
 - a <figure class="plate"> with an inlined base64 image at the top of each card,
   matched to its card by the exact <h4> heading text
 - an illustration-credits section, and an updated trust note.
Idempotent: removes any prior injected block before re-injecting."""
import base64, json, os, re, sys, importlib.util

HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.dirname(HERE)
HTML=os.path.join(ROOT,"Field Guide.html")
final=json.load(open(os.path.join(HERE,"plates_final.json")))
spec=importlib.util.spec_from_file_location("fp",os.path.join(HERE,"fetch_plates.py"))
fp=importlib.util.module_from_spec(spec); spec.loader.exec_module(fp)
ORDER=[s[0] for s in fp.SPECIES]   # zone order

html=open(HTML,encoding="utf-8").read()

# ---- 0. strip any previous injection (idempotent re-runs) ----
html=re.sub(r'<svg class="duo"[^>]*>.*?</svg>\n?', '', html, flags=re.S)
html=re.sub(r'<figure class="plate">.*?</figure>', '', html, flags=re.S)
html=re.sub(r'\n?<section id="credits">.*?</section>', '', html, flags=re.S)
html=re.sub(r'/\* PLATES \*/.*?/\* END PLATES \*/\n?', '', html, flags=re.S)

# ---- 1. dry-run heading match ----
problems=[]
for slug,v in final.items():
    needle=f'<h4>{v["anchor"]}</h4>'
    n=html.count(needle)
    if n!=1: problems.append((slug,v["anchor"],n))
if problems:
    print("HEADING MATCH PROBLEMS:")
    for slug,a,n in problems: print(f"  {slug}: {n}x  <h4>{a}</h4>")
    sys.exit(1)
if "--check" in sys.argv:
    print(f"OK: all {len(final)} headings match exactly once."); sys.exit(0)

def data_uri(relpath):
    with open(os.path.join(HERE,relpath),"rb") as fh:
        return "data:image/jpeg;base64,"+base64.b64encode(fh.read()).decode()

# ---- 2. inject figures ----
for slug,v in final.items():
    uri=data_uri(v["file"])
    alt=f'{v["subject"]} — historical scientific illustration (public domain)'
    fig=(f'<figure class="plate"><img loading="lazy" alt="{alt}" '
         f'src="{uri}"></figure>')
    needle=f'<h4>{v["anchor"]}</h4>'
    html=html.replace(needle, fig+needle, 1)

# ---- 3. CSS ----
css="""
/* PLATES */
svg.duo{position:absolute;width:0;height:0}
figure.plate{margin:-12px -14px 12px;background:#F2EEE3;border-bottom:1px solid var(--rule);text-align:center;padding:9px 10px 7px;overflow:hidden}
figure.plate img{max-width:100%;max-height:190px;width:auto;height:auto;vertical-align:middle;filter:url(#jed-duotone)}
@supports not (filter:url(#jed-duotone)){figure.plate img{filter:grayscale(1) contrast(1.02)}}
#credits{margin-top:64px}
#credits .grid{columns:2;column-gap:26px;font:12.5px/1.5 "Seravek","Avenir Next",sans-serif;color:var(--ink-soft)}
#credits .grid p{break-inside:avoid;margin:0 0 8px}
#credits .grid i{color:var(--ink)}
#credits a{color:var(--bark)}
@media (max-width:640px){#credits .grid{columns:1}}
/* END PLATES */
"""
html=html.replace("</style>", css+"</style>",1)

# ---- 4. SVG duotone filter after <body> ----
svg=('<svg class="duo" aria-hidden="true"><filter id="jed-duotone" color-interpolation-filters="sRGB">'
     '<feColorMatrix type="saturate" values="0"/>'
     '<feComponentTransfer>'
     '<feFuncR type="table" tableValues="0.078 0.949"/>'
     '<feFuncG type="table" tableValues="0.196 0.933"/>'
     '<feFuncB type="table" tableValues="0.173 0.890"/>'
     '</feComponentTransfer></filter></svg>\n')
html=html.replace("<body>", "<body>\n"+svg,1)

# ---- 5. credits section before footer-nav ----
def clean_title(t):
    t=re.sub(r'\.(jpg|jpeg|png|tif|tiff)$','',t,flags=re.I)
    t=t.replace('_',' ').strip()
    return t
rows=[]
for slug in ORDER:
    if slug not in final: continue
    v=final[slug]
    src=v.get("source","")
    title=v.get("credit") or clean_title(v["title"])
    lic=v.get("license","public domain")
    label=f'<i>{v["subject"]}</i> — {title}. {lic}, via Wikimedia Commons.'
    if src:
        label=f'<a href="{src}">{label}</a>' if False else label+f' <a href="{src}">[source]</a>'
    rows.append(f'<p>{label}</p>')
credits=('\n<section id="credits">\n'
 '  <div class="bearing"><span class="zno">SOURCES</span><h2>Where the illustrations come from</h2></div>\n'
 '  <p class="standhere">Every engraving on this page is a historical <b>public-domain</b> scientific illustration '
 '(mostly 1840s–1910s), sourced and license-checked from Wikimedia Commons and tinted to one ink so the mixed sources read as a single set. '
 'Species without a faithful public-domain plate are shown as text only rather than paired with a look-alike.</p>\n'
 '  <div class="grid">\n    '+"\n    ".join(rows)+'\n  </div>\n</section>\n')
html=html.replace('<nav class="footer-nav">', credits+'\n<nav class="footer-nav">',1)

# ---- 6. update trust note ----
old="they don't spawn in the Smith.</div>"
new=("they don't spawn in the Smith. <strong>The engravings</strong> beside each species are historical "
     "public-domain scientific plates, license-checked and tinted to match this guide; the ~10 species without a "
     "faithful public-domain plate are left unillustrated on purpose. Full sources are listed at the foot of the page.</div>")
if old in html: html=html.replace(old,new,1)

open(HTML,"w",encoding="utf-8").write(html)
kb=os.path.getsize(HTML)/1024
print(f"injected {len(final)} plates into Field Guide.html  ({kb:.0f} KB)")
