exec(open('manana_examen.py').read().split("resumen('Antes")[0])
def corre(k, n, meta, freno):
    c=n*C[k]; w=n*W[k]; peor=0.0
    for t in range(78):
        if freno is not None and w[t] <= -freno: return -freno-n*1.0, -freno-n*1.0
        peor=min(peor,w[t])
        if meta is not None and c[t]>=meta: return c[t],peor
    return c[-1],peor
def examen2(idx, P, cierre_ok=False):
    bal=alto=mejor=0.0; mll=-2000.0; bloq=False
    for i,k in enumerate(idx):
        n=max(1,round(P.get('base',6)*peso[k]))
        if r9.iloc[k]>1.10:
            if P.get('salta_miedo'): continue
            n=max(1,round(n*0.5))
        colchon=bal-mll
        if P.get('colchon'): n=max(1,round(n*min(1,colchon/2000)))
        meta=1550
        if P.get('meta_din'):                       # lo justo para llegar a 3,000 respetando la consistencia (día ≤ saldo previo)
            falta=3000-bal; meta=min(1550, falta+50) if falta+50<=max(bal,0) else min(1550, max(bal,0)) if bal>0 else 1550
            meta=max(meta,300)
        freno=None
        if P.get('freno'): freno=P['freno']
        if P.get('freno_frac'): freno=P['freno_frac']*colchon
        r,peor=corre(k,n,meta,freno)
        if (bal+peor<=mll and not cierre_ok) or bal+r<=mll: return 'quema',i+1
        bal+=r; mejor=max(mejor,r)
        if not bloq:
            alto=max(alto,bal); mll=alto-2000
            if bal>2100: mll=100; bloq=True
        if bal>=3000 and mejor<=0.5*bal: return 'pasa',i+1
    return 'sigue',len(idx)
def mide(nombre,P,cierre_ok=False):
    R=[examen2(range(s,min(s+80,len(C))),P,cierre_ok) for s in range(len(C)-80)]
    ps=np.array([r=='pasa' for r,d in R]); d=np.array([d for r,d in R]); m=len(R)//2
    ch=[]; ex=[]
    for s in range(0,len(C)-400,5):
        k=s; n=0
        while k<len(C)-80:
            r,dd=examen2(range(k,k+80),P,cierre_ok); n+=1; k+=dd
            if r=='pasa': ch.append(k-s); ex.append(n); break
    print(f"{nombre:<58} pasa {ps.mean():4.0%} ({ps[:m].mean():.0%}/{ps[m:].mean():.0%}) · {d.mean():4.1f} días/intento · fondeado en mediana {np.median(ch):3.0f} días hábiles (75%: {np.percentile(ch,75):3.0f}) · exámenes {np.mean(ex):.1f}")
mide('Mañana tal cual',{})
mide('+ no operar (en vez de ½) con miedo de corto plazo',{'salta_miedo':1})
for f in (600,900,1200): mide(f'+ freno diario fijo −${f}',{'freno':f})
for fr in (0.4,0.5,0.6): mide(f'+ freno = {fr:.0%} del colchón (siempre quedan "vidas")',{'freno_frac':fr})
mide('+ tamaño según colchón',{'colchon':1})
mide('+ meta del día = lo justo que falta',{'meta_din':1})
mide('+ colchón + freno 50% + meta justa',{'colchon':1,'freno_frac':0.5,'meta_din':1})
mide('+ freno 50% + meta justa',{'freno_frac':0.5,'meta_din':1})
for b in (3,4,8):
    mide(f'base {b} MNQ + freno 50% + meta justa',{'base':b,'freno_frac':0.5,'meta_din':1})
print('\nSi Lucid solo revisa el MLL al cierre (por confirmar):')
mide('Mañana tal cual',{},True); mide('+ freno 50% + meta justa',{'freno_frac':0.5,'meta_din':1},True)
