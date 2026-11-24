import sys, numpy as np, pandas as pd
Z=np.load('final_caminos.npz',allow_pickle=True); fechas=pd.DatetimeIndex(Z['fechas']); ret1=Z['ret1']; pay=Z['pay']
W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]'); W=W.reindex(fechas)
vol=W.vol.values; r9=W.r9.values; cot=W.cot.fillna(1).values; gig=W.gig.fillna(False).values; nfp=W.nfp.fillna(False).values
def mult(version):
    """factores por día (orb, ruido) sin el tamaño base"""
    mo=vol*r9; mr=vol*r9
    if version=='todo':
        ev=cot*np.where(gig,1.5,1); mo=mo*ev*np.where(ret1<-0.02,0,1)
        mr=mr*ev*np.where(nfp,1.5,1)*np.where(ret1<-0.01,0,1)*np.where(pay>0.8,1.5,np.where(pay<0.2,0.5,1))
    return mo,mr
def escenario(costos, version, mitad=False):
    Co,Wo,Cr,Wr=(Z[f'{costos}_{i}'] for i in range(4))
    if mitad:
        q=15.0*np.arange(1,79)/78; Co=Co-q/2; Wo=Wo-q/2; Cr=Cr-q/2; Wr=Wr-q/2
    return Co,Wo,Cr,Wr,*mult(version)
def corre(k,base,E,meta):
    Co,Wo,Cr,Wr,mo,mr=E
    no=round(base*mo[k]); nr=round(base*mr[k]); c=no*Co[k]+nr*Cr[k]; w=no*Wo[k]+nr*Wr[k]; peor=0.0
    for t in range(78):
        peor=min(peor,w[t])
        if meta is not None and c[t]>=meta: return c[t],peor
    return c[-1],peor
def reto(s,base,E,ini=100000):
    estado='p1'; bal=prev=0.0; dias=0; listo=False; t=0
    for k in range(s,len(fechas)):
        t+=1; mf=(0.10 if estado=='p1' else 0.05)*ini
        r,peor=(0.0,0.0) if listo else corre(k,base,E,max(mf-bal,100))
        if bal+peor<=max(prev-0.05*ini,-0.10*ini): return 'quema',t
        bal+=r; prev=bal; dias+=1
        if bal>=mf: listo=True
        if listo and dias>=4:
            if estado=='p1': estado='p2'; bal=prev=0.0; dias=0; listo=False
            else: return 'pasa',t
    return 'sigue',t
def doce(s,bc,bf,E,H=252,ini=100000,fee=594):
    gasto=fee; cob=0.0; estado='p1'; bal=prev=0.0; dias=0; listo=False; reemb=True; df=0
    for i,k in enumerate(range(s,min(s+H,len(fechas)))):
        if estado in ('p1','p2'):
            mf=(0.10 if estado=='p1' else 0.05)*ini; r,peor=(0.0,0.0) if listo else corre(k,bc,E,max(mf-bal,100))
        else: r,peor=corre(k,bf,E,None)
        if bal+peor<=max(prev-0.05*ini,-0.10*ini): gasto+=fee; estado='p1'; bal=prev=0.0; dias=0; listo=False; reemb=True; continue
        bal+=r; prev=bal; dias+=1
        if estado in ('p1','p2'):
            if bal>=mf: listo=True
            if listo and dias>=4:
                if estado=='p1': estado='p2'
                else: estado='f'; df=0
                bal=prev=0.0; dias=0; listo=False
        else:
            df+=1
            if df%10==0 and bal>0:
                cob+=0.8*bal+(fee if reemb else 0); reemb=False; bal=prev=0.0
    return cob-gasto
def diario(E):
    Co,Wo,Cr,Wr,mo,mr=E; z=mo*Co[:,-1]+mr*Cr[:,-1]; h=len(z)//2; sh=lambda a:a.mean()/a.std()*np.sqrt(252)
    return f"${z.mean():5.1f}/día (1 MNQ base) · Sharpe {sh(z):.2f} ({sh(z[:h]):.2f}/{sh(z[h:]):.2f})"
for nom,costos,version,mit in (('Lo que creíamos (costo 1 pt, capas viejas)','ideal','viejo',False),
                               ('Realidad sin arreglos (entra a mercado: ORB 5 pts)','real_mercado','viejo',False),
                               ('Real con órdenes pendientes, capas viejas','real','viejo',False),
                               ('Real con órdenes pendientes + TODO lo nuevo','real','todo',False),
                               ('Ídem, con media ventaja (prudente)','real','todo',True)):
    E=escenario(costos,version,mit)
    R=[reto(s,12,E) for s in range(0,len(fechas)-300,3)]; p=np.mean([r[0]=='pasa' for r in R]); dp=np.median([r[1] for r in R if r[0]=='pasa'] or [0])
    N=np.array([doce(s,12,4,E) for s in range(0,len(fechas)-252,3)])
    print(f"{nom}\n   {diario(E)}\n   reto FTMO 12 MNQ: pasa {p:.0%} en {dp:.0f} días · 12 meses: mediana ${np.median(N):,.0f} · promedio ${N.mean():,.0f} · gana {np.mean(N>0):.0%} · peor 10% ${np.percentile(N,10):,.0f}")
