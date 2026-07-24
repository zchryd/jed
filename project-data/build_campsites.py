#!/usr/bin/env python3
"""Rebuild campsites.json from the official-map transcription (official_layout.json)
projected onto the real OSM road graph (geo-layers/camp_roads.geojson).

The official map is schematic ("not to scale"): what it fixes is TOPOLOGY —
which road each site is on, in what order, and on which side. This script
makes that the single source of truth:

  chain spec (below)  =  ordered sites + side + a list of real-world waypoints
  placement           =  shortest path through the road graph between waypoints,
                         sites spread by arclength, offset ~11 m to the correct side.

Modes:
  --explore   print graph junctions (degree>=3) so chain waypoints can be picked
  --build     write campsites.json + a debug plot
  --check     run topology checks against the generated file
"""
import json, math, os, sys, heapq
from collections import defaultdict

HERE=os.path.dirname(os.path.abspath(__file__))
MLAT=111320.0; MLON=111320.0*math.cos(math.radians(41.798))
def m_xy(lat,lng): return (lng*MLON, lat*MLAT)
def dist_m(a,b):
    ax,ay=m_xy(*a); bx,by=m_xy(*b); return math.hypot(ax-bx,ay-by)

# ---------- graph ----------
def key(p): return (round(p[1],7), round(p[0],7))   # (lat,lng) rounded
def build_graph():
    gj=json.load(open(f"{HERE}/geo-layers/camp_roads.geojson"))
    adj=defaultdict(dict)   # node -> {nbr: dist_m}
    for f in gj['features']:
        g=f['geometry']; cs=g['coordinates']
        lines=cs if g['type']=='MultiLineString' else [cs]
        for ln in lines:
            for i in range(len(ln)-1):
                a=key(ln[i]); b=key(ln[i+1])
                if a==b: continue
                d=dist_m(a,b)
                adj[a][b]=min(adj[a].get(b,1e9),d)
                adj[b][a]=min(adj[b].get(a,1e9),d)
    return adj
def nearest_node(adj,lat,lng):
    return min(adj, key=lambda n: dist_m(n,(lat,lng)))
def dijkstra(adj,src,dst):
    pq=[(0.0,src,None)]; prev={}; seen=set()
    while pq:
        d,u,pr=heapq.heappop(pq)
        if u in seen: continue
        seen.add(u); prev[u]=pr
        if u==dst:
            path=[u]
            while prev[path[-1]] is not None: path.append(prev[path[-1]])
            return list(reversed(path)), d
        for v,w in adj[u].items():
            if v not in seen: heapq.heappush(pq,(d+w,v,u))
    return None, float('inf')

def chain_path(adj,waypoints):
    """waypoints: [(lat,lng),...] -> concatenated node path."""
    nodes=[nearest_node(adj,la,lo) for la,lo in waypoints]
    full=[nodes[0]]
    for a,b in zip(nodes,nodes[1:]):
        p,d=dijkstra(adj,a,b)
        if p is None: raise RuntimeError(f"no path {a}->{b}")
        full.extend(p[1:])
    return full

def arclen(path):
    out=[0.0]
    for a,b in zip(path,path[1:]): out.append(out[-1]+dist_m(a,b))
    return out

def point_at(path,cum,t_m):
    """point + unit tangent at arclength t_m along node path"""
    t_m=max(0.0,min(cum[-1]-1e-6,t_m))
    for i in range(len(cum)-1):
        if cum[i+1]>=t_m:
            f=(t_m-cum[i])/max(1e-9,(cum[i+1]-cum[i]))
            a,b=path[i],path[i+1]
            lat=a[0]+f*(b[0]-a[0]); lng=a[1]+f*(b[1]-a[1])
            tx=(b[1]-a[1])*MLON; ty=(b[0]-a[0])*MLAT
            L=math.hypot(tx,ty) or 1.0
            return (lat,lng),(tx/L,ty/L)
    return path[-1],(1,0)

CARD={'N':(0,1),'S':(0,-1),'E':(1,0),'W':(-1,0),
      'NE':(0.707,0.707),'NW':(-0.707,0.707),'SE':(0.707,-0.707),'SW':(-0.707,-0.707)}
def offset(pt,tang,side,dist=11.0,ring_centroid=None):
    """offset pt perpendicular to tangent toward `side`."""
    if side in ('on','cluster') or side is None: return pt
    nx,ny=-tang[1],tang[0]           # left normal
    if side in ('in','out') and ring_centroid:
        cx,cy=m_xy(*ring_centroid); px,py=m_xy(*pt)
        vx,vy=cx-px,cy-py
        L=math.hypot(vx,vy) or 1.0; vx,vy=vx/L,vy/L
        want=(vx,vy) if side=='in' else (-vx,-vy)
    else:
        want=CARD[side]
    if nx*want[0]+ny*want[1] < 0: nx,ny=-nx,-ny
    return (pt[0]+ny*dist/MLAT, pt[1]+nx*dist/MLON)

# ---------- chain specs: waypoints in REAL coords (snap to graph) ----------
# span: fraction of the path (after trimming) where the run of sites lives.
CHAINS=[]  # filled by configure() after --explore informs the waypoints
def configure():
    global CHAINS
    CHAINS=json.load(open(f"{HERE}/chain_spec.json"))

def load_layout():
    """global site-id -> {side, cabin, ada} from the official transcription"""
    lay=json.load(open(f"{HERE}/official_layout.json"))
    info={}
    for c in lay['chains']:
        for s in c['sites']:
            if s.get('facility'): continue
            info[str(s['n'])]={'n':s['n'],'side':s.get('side'),
                              'cabin':s.get('cabin',False),'ada':s.get('ada',False)}
    return info

# ordered site lists per spec chain (order = travel order along the waypoints)
CHAIN_SITES={
 'north_west':[23,22,20,21,19,18,17,16],
 'north_top':[15,14,12,13,10,8,9,6,7,5],
 'north_east':[4,2,3,1],
 'north_seedge':[28,27,25,26,24],
 'b_chain':[29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44],
 'west_edge':[50,53,54,55,56,49,57,48,58,47,45],
 'teardrop':[51,52],
 'boatlaunch_road':[46,59,60],
 'east_chain':[106,104,105,103,102,100,101,98,99,97,96,95,94,93,92],
 'east_outer':[91,90,89,88,87,86],
 'bottom_road':[85,84,83,82,81],
 'river_branch':[80,79,78,77,76],
 'hikebike':['A','B','C','D','E'],
}

def build():
    adj=build_graph(); info=load_layout()
    out=[]; report=[]
    placed=[]
    for spec in CHAINS:
        cid=spec['id']
        sites=[info[str(n)] for n in CHAIN_SITES[cid]]
        if spec.get('cluster'):
            for s,pos in zip(sites,spec['positions']):
                rec={"n":s['n'],"lat":pos[0],"lng":pos[1]}
                if s.get('cabin'): rec['cabin']=True
                if s.get('ada'): rec['ada']=True
                if isinstance(s['n'],str): rec['hikebike']=True
                out.append(rec)
            report.append(f"[{cid}] cluster: {len(sites)} sites at explicit positions")
            continue
        path=chain_path(adj,spec['waypoints'])
        cum=arclen(path); L=cum[-1]
        # per-waypoint segment fractions, for t tuning
        wp_nodes=[nearest_node(adj,la,lo) for la,lo in spec['waypoints']]
        marks=[]
        for wn in wp_nodes:
            if wn in path: marks.append(round(cum[path.index(wn)]/max(L,1e-9),3))
        sides=spec.get('sides',{})
        t0=spec.get('span',[0.0,1.0])[0]*L; t1=spec.get('span',[0.0,1.0])[1]*L
        n=len(sites)
        ring=tuple(spec['ring_centroid']) if spec.get('ring_centroid') else None
        overrides=spec.get('t_overrides',{})
        for i,s in enumerate(sites):
            frac=overrides.get(str(s['n']), (i+0.5)/n)
            t=t0+(t1-t0)*frac
            pt,tang=point_at(path,cum,t)
            side=sides.get(str(s['n']), s.get('side'))
            pos=offset(pt,tang,side,spec.get('offset_m',11.0),ring)
            rec={"n":s['n'],"lat":round(pos[0],6),"lng":round(pos[1],6)}
            if s.get('cabin'): rec['cabin']=True
            if s.get('ada'): rec['ada']=True
            if isinstance(s['n'],str): rec['hikebike']=True
            out.append(rec)
        report.append(f"[{cid}] path {L:.0f}m, {n} sites, span {spec.get('span',[0,1])}, waypoint marks {marks}")
    # normalize flags: ensure booleans exist like the old schema
    for rec in out:
        rec.setdefault('cabin',False); rec.setdefault('ada',False)
        if isinstance(rec['n'],str): rec.setdefault('hikebike',True)
    out.sort(key=lambda r:(isinstance(r['n'],str),r['n'] if isinstance(r['n'],int) else 0,str(r['n'])))
    json.dump(out,open(f"{HERE}/campsites.json","w"),indent=0)
    print("\n".join(report)); print(f"WROTE {len(out)} sites -> campsites.json")

def explore():
    adj=build_graph()
    deg3=[(n,len(v)) for n,v in adj.items() if len(v)>=3]
    deg3.sort()
    print(f"nodes={len(adj)}  junctions(deg>=3)={len(deg3)}")
    for n,d in deg3: print(f"  ({n[0]:.6f}, {n[1]:.6f})  deg{d}")

def check():
    adj=build_graph()
    sites=json.load(open(f"{HERE}/campsites.json"))
    segs=[]
    for a,nb in adj.items():
        for b in nb:
            if a<b: segs.append((a,b))
    def road_dist(lat,lng):
        best=1e9
        for a,b in segs:
            ax,ay=m_xy(*a); bx,by=m_xy(*b); px,py=m_xy(lat,lng)
            dx,dy=bx-ax,by-ay; L2=dx*dx+dy*dy
            t=0 if L2==0 else max(0,min(1,((px-ax)*dx+(py-ay)*dy)/L2))
            best=min(best,math.hypot(ax+t*dx-px,ay+t*dy-py))
        return best
    bad=[]
    for s in sites:
        d=road_dist(s['lat'],s['lng'])
        if d>18 or (d<3 and False): bad.append((s['n'],round(d,1)))
    print("sites too far from any road (>18m):", bad or "none")
    # min pairwise separation
    worst=(1e9,None)
    for i in range(len(sites)):
        for j in range(i+1,len(sites)):
            d=dist_m((sites[i]['lat'],sites[i]['lng']),(sites[j]['lat'],sites[j]['lng']))
            if d<worst[0]: worst=(d,(sites[i]['n'],sites[j]['n']))
    print(f"min pairwise separation: {worst[0]:.1f}m between {worst[1]}")

if __name__=="__main__":
    if "--explore" in sys.argv: explore()
    elif "--check" in sys.argv: configure() if False else check()
    else: configure(); build()
