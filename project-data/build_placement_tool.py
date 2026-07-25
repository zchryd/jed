#!/usr/bin/env python3
"""Build "Place Campsites.html" — Zach's hand-placement tool.

Self-contained page: satellite + real roads + all current site markers.
- Drag any site dot to fix it.
- Or type a range (e.g. 76-106), press Start, then tap the map once per site.
- Undo / Skip / auto-save in the browser; Save button downloads a JSON file
  that becomes the final campsites.json (his placements = ground truth).
- The official 2017 map is embedded and toggleable inside the page.
"""
import base64, json, os

HERE=os.path.dirname(os.path.abspath(__file__))
JED=os.path.dirname(HERE)

leaf_js=open(f'{HERE}/leaflet.js').read()
leaf_css=open(f'{HERE}/leaflet.css').read()
def data(n): return open(f'{HERE}/geo-layers/{n}.geojson').read()
sites=open(f'{HERE}/campsites.json').read()
import re as _re
_tpl=open(f'{HERE}/tpl_campground.html',encoding='utf-8').read()
_m=_re.search(r'var FACILITIES=\[(.*?)\];',_tpl,_re.S)
_ents=_re.findall(r'\{n:"([^"]+)",lat:([\d.]+),lng:(-[\d.]+),note:"([^"]*)"\}',_m.group(1))
facs=json.dumps([{"id":"F%d"%i,"n":n,"lat":float(la),"lng":float(lo),"note":note}
                 for i,(n,la,lo,note) in enumerate(_ents)])
OFFICIAL=os.environ.get("OFFICIAL_IMG", "/private/tmp/claude-501/-Users-zach-Desktop-jed/64cddecd-6b5d-4c02-a346-a2ba14e28f5e/scratchpad/official2017_campground.jpg")
off_b64=base64.b64encode(open(OFFICIAL,'rb').read()).decode()

page = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Place Campsites — hand-placement tool</title>
<style>/*__LEAFLET_CSS__*/</style>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%}
body{font:14px/1.5 "Seravek","Avenir Next","Helvetica Neue",sans-serif;display:flex;overflow:hidden;color:#2A241C}
#panel{width:330px;min-width:330px;background:#3B2A20;color:#EFE7D8;padding:16px;overflow-y:auto;z-index:1000}
#map{flex:1}
h1{font:700 19px/1.25 Georgia,serif;color:#F5EFE0;margin-bottom:8px}
.step{font-size:12.5px;color:#D8CFB8;margin:7px 0;padding-left:20px;position:relative}
.step b{color:#F5EFE0}
.step .no{position:absolute;left:0;top:1px;width:15px;height:15px;border-radius:50%;background:#C9A227;color:#20160F;font:700 10px/15px sans-serif;text-align:center}
.box{background:#ffffff12;border-radius:6px;padding:10px;margin-top:12px}
label{font:600 11px/1 sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#C9B896}
input#range{width:100%;margin-top:6px;font:600 15px/1 sans-serif;padding:8px;border-radius:5px;border:1.5px solid #ffffff44;background:#ffffff10;color:#F5EFE0}
button{font:700 13px/1 sans-serif;padding:9px 12px;border-radius:5px;border:0;cursor:pointer;margin:6px 6px 0 0}
#startbtn{background:#C9A227;color:#20160F}
#stopbtn{background:transparent;color:#EFE7D8;border:1.5px solid #ffffff44;display:none}
#undobtn,#skipbtn{background:transparent;color:#EFE7D8;border:1.5px solid #ffffff44}
#savebtn{background:#58A08F;color:#0E2A24;width:100%;padding:12px;font-size:14px;margin-top:12px}
#resetbtn{background:transparent;color:#C9B896;border:1px solid #ffffff33;font-weight:600;font-size:11px;margin-top:10px}
#offbtn{background:#EFE7D8;color:#20160F;width:100%;margin-top:12px}
#status{margin-top:10px;font-size:12.5px;color:#C9B896}
#banner{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:2000;background:#C9A227;color:#20160F;
  font:800 16px/1 sans-serif;padding:12px 18px;border-radius:999px;box-shadow:0 3px 14px #0009;display:none}
#official{position:fixed;top:0;right:0;width:46%;height:100%;background:#fff;z-index:1500;display:none;
  border-left:4px solid #3B2A20;overflow:auto}
#official img{width:100%;display:block}
#official .zoom{position:sticky;top:8px;margin:8px;display:flex;gap:6px}
#official .zoom button{background:#3B2A20;color:#fff}
.sm{border-radius:50%;border:1.5px solid #fff;box-shadow:0 1px 4px #0008;color:#fff;
  font:700 10px/17px sans-serif;text-align:center;background:#1F6B45;cursor:grab}
.sm.cabin{background:#C05B12}.sm.hb{background:#4E3E9E}.sm.ada{box-shadow:0 0 0 2px #7FB5E8,0 1px 4px #0008}
.sm.moved{box-shadow:0 0 0 3px #C9A227,0 1px 4px #0008}
.sm.current{box-shadow:0 0 0 4px #ff5252,0 1px 6px #000}
@media (max-width:760px){body{flex-direction:column}#panel{width:100%;min-width:0;max-height:45%;order:2}#map{order:1;min-height:55%}#official{width:100%}}
</style>
</head>
<body>
<aside id="panel">
  <h1>Place the campsites by hand</h1>
  <div class="step"><span class="no">1</span><b>Drag</b> any site dot — or any dark <b>label</b> (Restrooms, Visitor center…) — to where it belongs. The little gold dot under a label marks its exact spot. Or:</div>
  <div class="step"><span class="no">2</span>Type the numbers to redo below and press <b>Start placing</b> — then <b>tap the map once per site</b>, in order. Undo/Skip any time.</div>
  <div class="step"><span class="no">3</span>Use <b>Show official map</b> (bottom) to see the reference beside the satellite.</div>
  <div class="step"><span class="no">4</span>When it looks right, press <b>Save my placements</b> — it downloads a file. Then just tell Claude "done".</div>
  <div class="box">
    <label>Sites to place, in order</label>
    <input id="range" value="76-106" placeholder="e.g. 76-106 or 59,60,46 or A-E">
    <button id="startbtn">▶ Start placing</button>
    <button id="stopbtn">■ Stop</button>
    <div>
      <button id="undobtn">↩ Undo</button>
      <button id="skipbtn">⤼ Skip</button>
    </div>
    <div id="status">Everything auto-saves in this browser as you work.</div>
  </div>
  <button id="savebtn">⬇ Save my placements (when finished)</button>
  <button id="offbtn">🗺 Show / hide official map</button>
  <button id="resetbtn">Reset all my changes</button>
</aside>
<div id="map"></div>
<div id="banner"></div>
<div id="official">
  <div class="zoom"><button onclick="zoomOff(1)">Small</button><button onclick="zoomOff(1.8)">Medium</button><button onclick="zoomOff(3)">Large</button></div>
  <img id="offimg" src="data:image/jpeg;base64,__OFFICIAL_B64__" alt="Official campground map (2017)">
</div>

<script>/*__LEAFLET_JS__*/</script>
<script>
var LAYERS={roads:__DATA_camp_roads__,areas:__DATA_camp_areas__,water:__DATA_water__};
var SITES=__DATA_sites__;
var FACS=__DATA_facs__;
var KEY='jed-placement-v2';

var map=L.map('map',{zoomControl:true}).setView([41.7955,-124.0857],17);
map.zoomControl.setPosition('topright');
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:19,attribution:'Imagery © Esri'}).addTo(map);
L.geoJSON(LAYERS.water,{style:{color:'#5FA8C7',weight:1,fillColor:'#8FC7DC',fillOpacity:.4,interactive:false}}).addTo(map);
L.geoJSON(LAYERS.areas,{style:{color:'#C9B896',weight:1.4,fillOpacity:0,dashArray:'6 5',interactive:false}}).addTo(map);
L.geoJSON(LAYERS.roads,{style:{color:'#E8D9A0',weight:3,opacity:.95,interactive:false}}).addTo(map);

var store={};
try{ store=JSON.parse(localStorage.getItem(KEY)||'{}'); }catch(e){ store={}; }
if(!store.pos) store.pos={};
if(!store.fac) store.fac={};
function persist(){ localStorage.setItem(KEY,JSON.stringify(store)); }

var markers={}, undoStack=[];
function siteLatLng(s){ var p=store.pos[String(s.n)]; return p?[p[0],p[1]]:[s.lat,s.lng]; }
function iconFor(s,current){
  var cls='sm'+(s.cabin?' cabin':'')+(s.hikebike?' hb':'')+(s.ada?' ada':'');
  if(store.pos[String(s.n)]) cls+=' moved';
  if(current) cls+=' current';
  return L.divIcon({className:'',iconSize:[21,21],iconAnchor:[10.5,10.5],
    html:'<div class="'+cls+'" style="width:21px;height:21px">'+s.n+'</div>'});
}
SITES.forEach(function(s){
  var m=L.marker(siteLatLng(s),{icon:iconFor(s),draggable:true,title:'Site '+s.n});
  m.on('dragstart',function(){ undoStack.push({n:String(s.n),prev:store.pos[String(s.n)]||null}); });
  m.on('dragend',function(){
    var ll=m.getLatLng(); store.pos[String(s.n)]=[+ll.lat.toFixed(6),+ll.lng.toFixed(6)];
    persist(); m.setIcon(iconFor(s)); setStatus('Moved site '+s.n+'.');
  });
  m.addTo(map); markers[String(s.n)]=m;
});

var facMarkers={};
function facIcon(f){
  var moved=store.fac[f.id]?'box-shadow:0 0 0 3px #C9A227;':'';
  return L.divIcon({className:'',iconSize:[0,0],iconAnchor:[0,0],
    html:'<div style="transform:translate(-50%,-100%);cursor:grab">'
        +'<div style="background:#3B2A20;color:#F5EFE0;border:1px solid #fff9;'+moved+'border-radius:4px;font:600 11px/1.25 sans-serif;padding:3px 6px;white-space:nowrap">'+f.n+'</div>'
        +'<div style="width:7px;height:7px;border-radius:50%;background:#C9A227;border:1.5px solid #fff;margin:2px auto 0"></div></div>'});
}
FACS.forEach(function(f){
  var pos=store.fac[f.id]||[f.lat,f.lng];
  var m=L.marker(pos,{icon:facIcon(f),draggable:true,title:f.n});
  m.on('dragstart',function(){ undoStack.push({fac:f.id,prev:store.fac[f.id]||null}); });
  m.on('dragend',function(){
    var ll=m.getLatLng(); store.fac[f.id]=[+ll.lat.toFixed(6),+ll.lng.toFixed(6)];
    persist(); m.setIcon(facIcon(f)); setStatus('Moved label: '+f.n);
  });
  m.addTo(map); facMarkers[f.id]=m;
});

function setStatus(t){ document.getElementById('status').textContent=t; }

/* ---- queue mode ---- */
var queue=[], qi=-1;
function parseRange(txt){
  var out=[];
  txt.split(',').forEach(function(part){
    part=part.trim().toUpperCase(); if(!part) return;
    var m=part.match(/^(\d+)\s*-\s*(\d+)$/);
    if(m){ for(var i=+m[1];i<=+m[2];i++) if(exists(i)) out.push(String(i)); return; }
    var a=part.match(/^([A-E])\s*-\s*([A-E])$/);
    if(a){ for(var c=a[1].charCodeAt(0);c<=a[2].charCodeAt(0);c++){ var L1=String.fromCharCode(c); if(exists(L1)) out.push(L1);} return; }
    if(exists(part)) out.push(part);
    else if(exists(+part)) out.push(String(+part));
  });
  return out;
}
function exists(n){ return SITES.some(function(s){ return String(s.n)===String(n); }); }
function banner(){
  var b=document.getElementById('banner');
  if(qi>=0 && qi<queue.length){
    b.style.display='block';
    b.textContent='TAP WHERE SITE '+queue[qi]+' GOES  ('+(qi+1)+' of '+queue.length+')';
    SITES.forEach(function(s){ markers[String(s.n)].setIcon(iconFor(s, String(s.n)===queue[qi])); });
  } else {
    b.style.display='none';
    SITES.forEach(function(s){ markers[String(s.n)].setIcon(iconFor(s,false)); });
    document.getElementById('stopbtn').style.display='none';
    document.getElementById('map').style.cursor='';
    if(qi>=queue.length && queue.length) setStatus('Range finished. Drag any dot to fine-tune, or Save.');
    qi=-1; queue=[];
  }
}
function place(n,latlng){
  undoStack.push({n:n,prev:store.pos[n]||null});
  store.pos[n]=[+latlng.lat.toFixed(6),+latlng.lng.toFixed(6)];
  persist();
  var s=SITES.filter(function(x){return String(x.n)===n})[0];
  markers[n].setLatLng(store.pos[n]); markers[n].setIcon(iconFor(s));
}
document.getElementById('startbtn').addEventListener('click',function(){
  queue=parseRange(document.getElementById('range').value);
  if(!queue.length){ setStatus('No valid site numbers in the box.'); return; }
  qi=0; document.getElementById('stopbtn').style.display='inline-block';
  document.getElementById('map').style.cursor='crosshair';
  setStatus('Placing '+queue.length+' sites. Tap the map for each.');
  banner();
});
document.getElementById('stopbtn').addEventListener('click',function(){ qi=queue.length; banner(); });
document.getElementById('skipbtn').addEventListener('click',function(){ if(qi>=0){ qi++; banner(); } });
document.getElementById('undobtn').addEventListener('click',function(){
  var u=undoStack.pop(); if(!u){ setStatus('Nothing to undo.'); return; }
  if(u.fac){
    if(u.prev) store.fac[u.fac]=u.prev; else delete store.fac[u.fac];
    persist();
    var f=FACS.filter(function(x){return x.id===u.fac})[0];
    facMarkers[u.fac].setLatLng(store.fac[u.fac]||[f.lat,f.lng]);
    facMarkers[u.fac].setIcon(facIcon(f));
    setStatus('Undid label move: '+f.n); return;
  }
  if(u.prev) store.pos[u.n]=u.prev; else delete store.pos[u.n];
  persist();
  var s=SITES.filter(function(x){return String(x.n)===u.n})[0];
  markers[u.n].setLatLng(siteLatLng(s));
  if(qi>0 && queue[qi-1]===u.n) qi--;
  banner(); setStatus('Undid site '+u.n+'.');
});
map.on('click',function(e){
  if(qi<0||qi>=queue.length) return;
  place(queue[qi],e.latlng); qi++; banner();
});

/* ---- save / reset ---- */
document.getElementById('savebtn').addEventListener('click',function(){
  var out=SITES.map(function(s){
    var ll=siteLatLng(s);
    var r={n:s.n,lat:ll[0],lng:ll[1],cabin:!!s.cabin,ada:!!s.ada};
    if(s.hikebike) r.hikebike=true;
    return r;
  });
  var facout=FACS.map(function(f){
    var p=store.fac[f.id]||[f.lat,f.lng];
    return {n:f.n,lat:p[0],lng:p[1],note:f.note};
  });
  var blob=new Blob([JSON.stringify({placed_by:'Zach placement tool v2',sites:out,facilities:facout},null,1)],{type:'application/json'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='jed-campsite-placements.json'; a.click(); URL.revokeObjectURL(a.href);
  setStatus('Saved! The file is in your Downloads. Now tell Claude "done".');
});
document.getElementById('resetbtn').addEventListener('click',function(){
  if(confirm('Throw away ALL your moves and start over from the current map?')){
    store.pos={}; store.fac={}; persist(); undoStack=[];
    FACS.forEach(function(f){ facMarkers[f.id].setLatLng([f.lat,f.lng]); facMarkers[f.id].setIcon(facIcon(f)); });
    SITES.forEach(function(s){ markers[String(s.n)].setLatLng([s.lat,s.lng]); markers[String(s.n)].setIcon(iconFor(s)); });
    setStatus('Reset. All dots back to where the map had them.');
  }
});
document.getElementById('offbtn').addEventListener('click',function(){
  var o=document.getElementById('official');
  o.style.display = o.style.display==='block'?'none':'block';
});
function zoomOff(f){ document.getElementById('offimg').style.width=(f*100)+'%'; }

/* ---- headless self-test hook ---- */
if(location.search.indexOf('selftest')>=0){
  try{
    var q=parseRange('76-78');
    place(q[0],L.latLng(41.7940,-124.0855));
    place(q[1],L.latLng(41.7941,-124.0856));
    var u=undoStack.length;
    document.getElementById('undobtn').click();
    store.fac['F0']=[41.7999,-124.0850];
    var f0=FACS.filter(function(x){return x.id==='F0'})[0];
    var ok=(q.length===3)&&(store.pos['76'])&&(!store.pos['77'])&&(undoStack.length===u-1)
           &&(FACS.length===16)&&(!!facMarkers['F0'])&&(f0.note.length>0);
    document.title='SELFTEST-'+(ok?'OK':'FAIL');
  }catch(e){ document.title='SELFTEST-ERR-'+e.message; }
}
</script>
</body>
</html>
'''
page=page.replace('/*__LEAFLET_CSS__*/',leaf_css).replace('/*__LEAFLET_JS__*/',leaf_js)
page=page.replace('__DATA_camp_roads__',data('camp_roads')).replace('__DATA_camp_areas__',data('camp_areas')).replace('__DATA_water__',data('water'))
page=page.replace('__DATA_sites__',sites).replace('__DATA_facs__',facs).replace('__OFFICIAL_B64__',off_b64)
out=f'{JED}/Place Campsites.html'
open(out,'w').write(page)
print(f"wrote {out} ({os.path.getsize(out)//1024} KB)")
