exec(open('bpr.py').read().split("niv_orb=")[0])
import itertools
def correr(nivel_fn, objf, entrada='mitad', pide_bpr=True):
    out=[]
    for d in sorted(D):
        if d in FOMC: continue
        v=D[d]; o,h,l,c=(v[k].values for k in ('open','high','low','close'))
        for lado in (1,-1):
            r=setup2(o,h,l,c,lado,nivel_fn,objf,entrada,pide_bpr)
            if r: out.append((d,r))
    return out
def setup2(o,h,l,c,lado,nivel_fn,objf,entrada,pide_bpr):
    if lado==-1: o,h,l,c=-o,-l,-h,-c
    nivel=nivel_fn(o,h,l,c)
    for b in range(6,CIERRE):
        if h[b]>nivel: break
    else: return None
    prev_min=l[max(0,b-6):b].min(); pico=b; bull=None; estado=None
    for j in range(b+1,CIERRE):
        if h[j]>h[pico]: pico=j
        if bull is None:
            for i in range(max(2,b-6),pico+1):
                if l[i]>h[i-2]: bull=(h[i-2],l[i])
        if pide_bpr:
            if bull and j>=pico+2 and h[j]<l[j-2]:
                bear=(h[j],l[j-2]); lo_=max(bull[0],bear[0]); hi_=min(bull[1],bear[1])
                if hi_>lo_: estado=(lo_,hi_)
        if c[j]<prev_min and (estado or not pide_bpr):
            if not pide_bpr: estado=(prev_min,(prev_min+h[pico])/2)     # sin BPR: vuelve a la mitad de la caída
            lo_,hi_=estado; ent={'mitad':(lo_+hi_)/2,'borde':lo_,'arriba':hi_}[entrada]; stop=h[pico]+0.5; obj=objf(o,h,l,c,j,ent,stop)
            if obj>=ent: return None
            for k in range(j+1,ULTIMA_ENTRADA+1):
                if h[k]>=stop: return None
                if h[k]>=ent:
                    for m in range(k,CIERRE+1):
                        if h[m]>=stop: return -(stop-ent)*USD-COSTO
                        if m>k and l[m]<=obj: return (ent-obj)*USD-COSTO
                    return (ent-c[CIERRE])*USD-COSTO
            return None
    return None
niv_orb=lambda o,h,l,c: h[:6].max()
objs={'liquidez':lambda o,h,l,c,j,ent,stop: min(l[:6].min(), l[:j+1].min()),'1R':lambda o,h,l,c,j,ent,stop: ent-(stop-ent),'2R':lambda o,h,l,c,j,ent,stop: ent-2*(stop-ent),'3R':lambda o,h,l,c,j,ent,stop: ent-3*(stop-ent),'cierre':lambda o,h,l,c,j,ent,stop: -1e9}
filas=[]
for (on,of),ent,pb in itertools.product(objs.items(),('mitad','borde','arriba'),(True,False)):
    r=correr(niv_orb,of,ent,pb); v=np.array([x[1] for x in r])
    if len(v)<20: continue
    mitad=len(v)//2
    filas.append((f"{'BPR' if pb else 'sin BPR'} · entrada {ent} · objetivo {on}",len(v),v.mean(),v.mean()/v.std()*np.sqrt(len(v)),v[:mitad].mean(),v[mitad:].mean()))
F=pd.DataFrame(filas,columns=['variante','trades','$/trade','t','1a mitad','2a mitad']).sort_values('t',ascending=False)
print(F.round(1).to_string(index=False))
