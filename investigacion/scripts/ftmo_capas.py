exec(open('ftmo_nasdaq.py').read().split("def tabla(")[0])
import sys
Wd=pd.read_pickle('todo_pesos.pkl'); Wd.index=Wd.index.astype('datetime64[ns]')
fx=pd.DatetimeIndex(fechas).astype('datetime64[ns]')
Wd=Wd.reindex(fx)
extra=(Wd.cot.fillna(1)*np.where(Wd.gig,1.5,1)*np.where(Wd.nfp,1.25,1)).values      # NFP: ×1.5 solo a la zona de ruido ≈ ×1.25 al día
pru=len(sys.argv)>1
if pru: C=C-15.0*np.arange(1,79)/78; W=W-15.0*np.arange(1,79)/78
def n_nuevo(base,k):
    n=max(1,round(base*peso[k]*extra[k]))
    return max(1,round(n*0.5)) if r9.iloc[k]>1.10 else n
def primer(s,bc,nfun,ini=100000):
    estado='p1'; bal=prev=0.0; dias=0; listo=False; t=0
    for k in range(s,len(C)):
        t+=1; meta_fase=(0.10 if estado=='p1' else 0.05)*ini
        r,peor=(0.0,0.0) if listo else corre(k,nfun(bc,k),max(meta_fase-bal,100),None)
        if bal+peor<=max(prev-0.05*ini,-0.10*ini): return 'quema',t
        bal+=r; prev=bal; dias+=1
        if bal>=meta_fase: listo=True
        if listo and dias>=4:
            if estado=='p1': estado='p2'; bal=prev=0.0; dias=0; listo=False
            else: return 'pasa',t
    return 'sigue',t
print('PRUDENTE (½ ventaja)' if pru else 'HISTÓRICO')
G=globals()
for nom,nfun in (('actual',n_de),('con capas nuevas',n_nuevo)):
    for bc in (8,12):
        R=[primer(s,bc,nfun) for s in range(0,len(C)-300,3)]
        p=np.mean([r[0]=='pasa' for r in R]); dp=np.median([r[1] for r in R if r[0]=='pasa'])
        G['n_de_orig']=G.get('n_de_orig',n_de); G['n_de']=nfun          # ftmo() usa n_de para reto y fondeada
        N=[ftmo(s,252,bc,4) for s in range(0,len(C)-252,3)]; G['n_de']=G['n_de_orig']
        net=np.array([x[0] for x in N]); m=len(net)//2
        print(f"{nom:<17} reto {bc:2} MNQ: pasa {p:4.0%} en {dp:3.0f} días · 12 meses: neto mediana ${np.median(net):7,.0f} · promedio ${net.mean():7,.0f} ({net[:m].mean():,.0f}/{net[m:].mean():,.0f}) · gana {np.mean(net>0):4.0%} · peor 10% ${np.percentile(net,10):,.0f}")
