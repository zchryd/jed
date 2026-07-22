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
html=re.sub(r'<!-- LIGHTBOX -->.*?<!-- END LIGHTBOX -->\n?', '', html, flags=re.S)
# revert any prior trust-note injection so step 6 re-applies cleanly (idempotent)
html=re.sub(r"they don't spawn in the Smith\..*?at the foot of the page\.</div>",
            "they don't spawn in the Smith.</div>", html, flags=re.S)

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
/* click-to-enlarge */
.cards .card{cursor:zoom-in;transition:transform .09s ease,box-shadow .14s ease}
.cards .card:hover{box-shadow:0 5px 18px rgba(30,26,18,.14);transform:translateY(-1px)}
.cards .card:focus-visible{outline:2px solid var(--emerald);outline-offset:3px}
.lb{position:fixed;inset:0;z-index:1000;display:none;align-items:center;justify-content:center;padding:24px;background:rgba(30,26,18,.64)}
.lb.on{display:flex}
.lb-panel{position:relative;background:#F7F3E9;max-width:660px;width:100%;max-height:92vh;overflow:auto;padding:30px 34px 34px;border-top:5px solid var(--emerald-soft);box-shadow:0 20px 64px rgba(0,0,0,.45);font:16.5px/1.62 "Seravek","Avenir Next","Helvetica Neue",sans-serif;color:var(--ink)}
.lb-panel.animal{border-top-color:#4A6FA5}
.lb-panel.fungus{border-top-color:#8C6D3F}
.lb-panel.hazard{border-top-color:var(--madrone)}
.lb-panel h4{font:700 30px/1.15 "Iowan Old Style",Georgia,serif;color:var(--emerald);margin:2px 0}
.lb-panel .sci{font-style:italic;color:var(--ink-soft);font-size:16px;margin-bottom:4px}
.lb-panel p{margin-top:10px;max-width:60ch}
.lb-panel .lk{color:var(--bark);font-weight:600}
.lb-panel .season{display:inline-block;margin-top:14px;font:600 11px/1 "Seravek",sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#fff;background:var(--emerald-soft);border-radius:3px;padding:5px 9px}
.lb-panel figure.plate{margin:0 0 20px!important;background:#F2EEE3;border:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:16px;text-align:center}
.lb-panel figure.plate img{max-width:100%;max-height:60vh;filter:url(#jed-duotone)}
#lb-x{position:absolute;top:6px;right:10px;border:0;background:none;font:300 32px/1 "Helvetica Neue",sans-serif;color:var(--ink-soft);cursor:pointer;padding:6px 10px}
#lb-x:hover,#lb-x:focus-visible{color:var(--madrone)}
.lb-hint{font:600 10px/1 "Seravek",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--bark);opacity:.5;margin-top:20px}
@media print{.lb{display:none!important}.cards .card{cursor:auto}}
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

# ---- 5b. lightbox modal + script before </body> ----
lightbox=r'''<!-- LIGHTBOX -->
<div id="lb" class="lb" role="dialog" aria-modal="true" aria-label="Enlarged species card" tabindex="-1">
  <div id="lb-panel" class="lb-panel"></div>
</div>
<script>
(function(){
  var cards=[].slice.call(document.querySelectorAll('.cards .card'));
  var lb=document.getElementById('lb'), panel=document.getElementById('lb-panel'), last=null;
  function open(card){
    last=card;
    var mods=card.className.split(/\s+/).filter(function(x){return x&&x!=='card';}).join(' ');
    panel.className='lb-panel '+mods;
    panel.innerHTML='<button id="lb-x" aria-label="Close">×</button>'+card.innerHTML+
      '<div class="lb-hint">Esc or tap outside to close</div>';
    lb.classList.add('on'); document.body.style.overflow='hidden';
    document.getElementById('lb-x').addEventListener('click',close);
    lb.focus();
  }
  function close(){ lb.classList.remove('on'); document.body.style.overflow=''; panel.innerHTML='';
    if(last){ last.focus(); last=null; } }
  cards.forEach(function(c){
    c.tabIndex=0; c.setAttribute('role','button');
    c.addEventListener('click',function(){open(c);});
    c.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){e.preventDefault();open(c);} });
  });
  lb.addEventListener('click',function(e){ if(e.target===lb) close(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&lb.classList.contains('on')) close(); });
  // deep-link / test hook: #lb<n> opens the nth species card on load
  var m=(location.hash||'').match(/^#lb(\d+)$/); if(m&&cards[+m[1]]) open(cards[+m[1]]);
})();
</script>
<!-- END LIGHTBOX -->
'''
html=html.replace("</body>", lightbox+"</body>",1)

# ---- 6. update trust note ----
old="they don't spawn in the Smith.</div>"
new=("they don't spawn in the Smith. <strong>The engravings</strong> beside each species are historical "
     "public-domain scientific plates, license-checked and tinted to match this guide; the species without a "
     "faithful public-domain plate are left unillustrated on purpose. <strong>Tap or click any card</strong> to "
     "enlarge its plate and text. Full sources are listed at the foot of the page.</div>")
if old in html: html=html.replace(old,new,1)

open(HTML,"w",encoding="utf-8").write(html)
kb=os.path.getsize(HTML)/1024
print(f"injected {len(final)} plates into Field Guide.html  ({kb:.0f} KB)")
