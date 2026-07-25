#!/usr/bin/env python3
"""Zach's overlay idea, made executable: thin-plate-spline warp of the official
campground map (page-2 render, pixel space) onto real lat/lng space using
shared reference points (kiosk, camp hosts, VC, boat launch, junctions...).

Outputs:
  - per-site distance table: our campsites.json vs the warped official position
  - overlay PNG: warped official map under the real roads + our sites + targets
"""
import json, math, os, sys
import numpy as np

HERE=os.path.dirname(os.path.abspath(__file__))
MLAT=111320.0; MLON=111320.0*math.cos(math.radians(41.798))
def to_m(lat,lng): return np.array([lng*MLON, lat*MLAT])
def from_m(x,y): return (y/MLAT, x/MLON)

def tps_fit(src,dst):
    """thin-plate spline src (N,2) -> dst (N,2), normalized for conditioning.
    lam adds slight smoothing so dense, slightly-inconsistent road controls
    bend gracefully instead of rippling."""
    src=np.asarray(src,float); dst=np.asarray(dst,float); N=len(src)
    sc=src.mean(0); ss=max(np.abs(src-sc).max(),1e-9)
    dc=dst.mean(0); ds=max(np.abs(dst-dc).max(),1e-9)
    src=(src-sc)/ss; dst=(dst-dc)/ds
    def U(r2):
        with np.errstate(divide='ignore',invalid='ignore'):
            v=r2*np.log(r2); v[~np.isfinite(v)]=0.0
        return v
    d2=((src[:,None,:]-src[None,:,:])**2).sum(-1)
    K=U(d2)+np.eye(N)*1e-4
    P=np.hstack([np.ones((N,1)),src])
    A=np.zeros((N+3,N+3)); A[:N,:N]=K; A[:N,N:]=P; A[N:,:N]=P.T
    Y=np.zeros((N+3,2)); Y[:N]=dst
    W=np.linalg.solve(A+np.eye(N+3)*1e-9,Y)
    def f(pts):
        pts=(np.atleast_2d(np.asarray(pts,float))-sc)/ss
        d2=((pts[:,None,:]-src[None,:,:])**2).sum(-1)
        out=U(d2)@W[:N] + np.hstack([np.ones((len(pts),1)),pts])@W[N:]
        return out*ds+dc
    return f

# control points are built from road_pairs.json: each official polyline is
# sampled at k fractions of arclength and paired with the same fractions of
# the corresponding REAL road path (routed through the road graph).
import importlib.util as _ilu
_spec=_ilu.spec_from_file_location("bc", os.path.join(HERE,"build_campsites.py"))
_bc=_ilu.module_from_spec(_spec); _spec.loader.exec_module(_bc)

def _poly_sample(pts, fracs):
    pts=[tuple(p) for p in pts]
    seg=[0.0]
    for a,b in zip(pts,pts[1:]):
        seg.append(seg[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
    L=seg[-1]; out=[]
    for f in fracs:
        t=f*L
        for i in range(len(seg)-1):
            if seg[i+1]>=t:
                r=(t-seg[i])/max(1e-9,seg[i+1]-seg[i])
                a,b=pts[i],pts[i+1]
                out.append((a[0]+r*(b[0]-a[0]), a[1]+r*(b[1]-a[1])))
                break
        else: out.append(pts[-1])
    return out

def build_controls():
    rp=json.load(open(f"{HERE}/road_pairs.json"))
    adj=_bc.build_graph()
    src=[]; dst=[]; names=[]
    for pr in rp['pairs']:
        k=pr['k']; fr=[i/(k-1) for i in range(k)]
        px=_poly_sample(pr['px'],fr)
        path=_bc.chain_path(adj,pr['real'])
        cum=_bc.arclen(path); L=cum[-1]
        rl=[_bc.point_at(path,cum,f*L)[0] for f in fr]
        for a,b in zip(px,rl):
            src.append(a); dst.append(to_m(b[0],b[1])); names.append(pr['name'])
    for pt in rp['points']:
        src.append(tuple(pt['px'])); dst.append(to_m(*pt['real'])); names.append(pt['name'])
    return src,dst,names

def build_warp():
    src,dst,names=build_controls()
    fwd=tps_fit(src,dst)
    inv=tps_fit(dst,src)
    return fwd,inv


def main():
    fwd,inv=build_warp()
    lay=json.load(open(f"{HERE}/official_layout.json"))
    targets={}
    for c in lay['chains']:
        for s in c['sites']:
            if s.get('facility'): continue
            m=fwd([s['px']])[0]
            targets[str(s['n'])]=from_m(m[0],m[1])
    ours={str(s['n']):s for s in json.load(open(f"{HERE}/campsites.json"))}
    rows=[]
    for n,t in targets.items():
        o=ours[n]
        d=math.hypot((o['lng']-t[1])*MLON,(o['lat']-t[0])*MLAT)
        rows.append((d,n,t))
    rows.sort(reverse=True)
    print(f"{'site':>5} {'off-by':>7}   (warped official target)")
    for d,n,t in rows[:30]:
        print(f"{n:>5} {d:6.0f}m   ({t[0]:.6f},{t[1]:.6f})")
    good=sum(1 for d,_,_ in rows if d<=25)
    print(f"\nwithin 25m of warped official position: {good}/{len(rows)}")
    json.dump({n:{'lat':round(t[0],6),'lng':round(t[1],6)} for _,n,t in rows},
              open(f"{HERE}/warp_targets.json","w"),indent=0)

    # ---------- overlay image ----------
    if "--overlay" in sys.argv:
        from PIL import Image
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        OFF=Image.open(sys.argv[sys.argv.index("--overlay")+1]).convert("L")
        offA=np.asarray(OFF)
        # output frame in lat/lng
        lat0,lat1=41.7920,41.8030; lng0,lng1=-124.0885,-124.0825
        Wp,Hp=1100,1500
        lats=np.linspace(lat1,lat0,Hp); lngs=np.linspace(lng0,lng1,Wp)
        gl,gn=np.meshgrid(lats,lngs,indexing='ij')
        pts=np.stack([gn.ravel()*MLON, gl.ravel()*MLAT],1)
        px=inv(pts).reshape(Hp,Wp,2)
        xs=np.clip(px[:,:,0],0,offA.shape[1]-1).astype(int)
        ys=np.clip(px[:,:,1],0,offA.shape[0]-1).astype(int)
        warped=offA[ys,xs]
        fig,ax=plt.subplots(figsize=(14,19),dpi=120)
        ax.imshow(warped,extent=[lng0,lng1,lat0,lat1],origin='upper',cmap='gray',alpha=.42,aspect='auto')
        gj=json.load(open(f"{HERE}/geo-layers/camp_roads.geojson"))
        for f in gj['features']:
            g=f['geometry']; cs=g['coordinates']
            lines=cs if g['type']=='MultiLineString' else [cs]
            for ln in lines: ax.plot([p[0] for p in ln],[p[1] for p in ln],color='#b8860b',lw=1.6,zorder=3)
        for n,t in targets.items():
            ax.plot(t[1],t[0],'x',color='#c00',ms=7,mew=2,zorder=5)
        for n,o in ours.items():
            t=targets[n]
            d=math.hypot((o['lng']-t[1])*MLON,(o['lat']-t[0])*MLAT)
            col='#1f6b45' if d<=25 else '#c05b12' if d<=45 else '#b00020'
            ax.plot(o['lng'],o['lat'],'o',ms=11,color=col,zorder=6)
            ax.annotate(str(n),(o['lng'],o['lat']),color='w',fontsize=6,ha='center',va='center',zorder=7,weight='bold')
            if d>25: ax.plot([o['lng'],t[1]],[o['lat'],t[0]],color='#b00020',lw=1,zorder=4)
        ax.set_xlim(lng0,lng1); ax.set_ylim(lat0,lat1); ax.set_aspect(1/0.745)
        ax.set_title("warped official map (gray) + real roads (gold) + our sites (green<=25m, orange<=45m, red>45m; X = warped official position)")
        out=sys.argv[sys.argv.index("--overlay")+2] if len(sys.argv)>sys.argv.index("--overlay")+2 else f"{HERE}/warp_overlay.png"
        plt.tight_layout(); plt.savefig(out); print("overlay ->",out)

if __name__=="__main__":
    main()
