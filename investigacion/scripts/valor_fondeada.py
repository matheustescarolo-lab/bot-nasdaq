exec(open('tres_versiones.py').read().split("V=[(")[0])
import sys
def lucid_f(s,bf,H=252):
    bal=alto=0.0; mll=-2000.0; bloq=False; d150=0; cg=0.0; cob=0.0; pagos=0
    for i,k in enumerate(range(s,min(s+H,len(C)))):
        r,peor=corre(k,n_de(bf,k),None,None)
        if bal+peor<=mll: return cob,pagos,'quema',i+1
        bal+=r
        if not bloq:
            alto=max(alto,bal); mll=alto-2000
            if bal>2100: mll=100; bloq=True
        d150+=r>=150; cg+=r
        if d150>=5 and cg>0 and bal>=1000:
            p=min(0.5*bal,2000); cob+=0.9*p; bal-=p; mll=100; bloq=True; pagos+=1; d150=0; cg=0.0
            if pagos>=5: return cob,pagos,'real',i+1
    return cob,pagos,'sigue',H
def ftmo_f(s,bf,H=252,ini=100000):
    bal=prev=0.0; cob=0.0; pagos=0; df=0
    for i,k in enumerate(range(s,min(s+H,len(C)))):
        r,peor=corre(k,n_de(bf,k),None,None)
        if bal+peor<=max(prev-0.05*ini,-0.10*ini): return cob,pagos,'quema',i+1
        bal+=r; prev=bal; df+=1
        if df%10==0 and bal>0: cob+=0.8*bal; bal=prev=0.0; pagos+=1
    return cob,pagos,'sigue',H
if len(sys.argv)>1: C=C-15.0*np.arange(1,79)/78; W=W-15.0*np.arange(1,79)/78
for nombre,fn,bfs in (('Lucid 50K fondeada',lucid_f,(1,2)),('FTMO 100K fondeada',ftmo_f,(3,4))):
    for bf in bfs:
        R=[fn(s,bf) for s in range(0,len(C)-252,3)]
        v=np.array([r[0] for r in R]); q=np.mean([r[2]=='quema' for r in R])
        print(f"{nombre} con {bf} MNQ: vale en promedio ${v.mean():,.0f} en retiros (mediana ${np.median(v):,.0f}) · se quema en el año {q:.0%} · retiros {np.mean([r[1] for r in R]):.1f}")
