import numpy as np, pandas as pd
Z=np.load('final_caminos2.npz',allow_pickle=True); fechas=pd.DatetimeIndex(Z['fechas']); ret1=Z['ret1']; pay=Z['pay']
W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]'); W=W.reindex(fechas)
vol=W.vol.values; r9=W.r9.values; cot=W.cot.fillna(1).values; gig=W.gig.fillna(False).values; nfp=W.nfp.fillna(False).values
ev=cot*np.where(gig,1.5,1)
MO=np.minimum(vol*r9*ev*np.where(ret1<-0.02,0,1),2.0)
MR=np.minimum(vol*r9*ev*np.where(nfp,1.5,1)*np.where(ret1<-0.01,0,1)*np.where(pay>0.8,1.5,np.where(pay<0.2,0.5,1)),2.0)
EUR=1.10
def caminos(mitad):
    Co,Wo,Cr,Wr=(Z[f'ambos_sac_{i}'] for i in range(4))
    if mitad: q=15.0*np.arange(1,79)/78; Co=Co-q/2; Wo=Wo-q/2; Cr=Cr-q/2; Wr=Wr-q/2
    return Co,Wo,Cr,Wr
def dia(k,base,C,meta,room):
    """un día con freno: room = pérdida permitida hasta quemar (min diario/total). Devuelve (resultado, quema)"""
    Co,Wo,Cr,Wr=C; no=round(base*MO[k]); nr=round(base*MR[k])
    if no+nr==0: return 0.0,False
    c=no*Co[k]+nr*Cr[k]; w=no*Wo[k]+nr*Wr[k]
    colchon=max(400,30*2*(no+nr)); freno=room-colchon
    for t in range(78):
        if w[t]<=-room: return -room,True
        if w[t]<=-freno: return w[t],False          # el freno cierra (peor punto de la vela, conservador)
        if meta is not None and c[t]>=meta: return c[t],False
    return c[-1],False
# ---------- productos ----------
def dos_pasos(s,C,nmax,bc=6,bf=4,fee=439,H=252):
    pago=0; compras=0; reemb=0; est=None
    for k in range(s,min(s+H,len(fechas))):
        if est in (None,'x'):
            if compras>=nmax: break
            est='p1'; bal=prev=0.0; dias=0; compras+=1; df=0; reemb_ok=True
        if est in('p1','p2'):
            mf=(0.10 if est=='p1' else 0.05)*1e5
            room=min(prev+5000-0, bal+10000) if False else min(5000, bal+10000)
            r,q=(0.0,False) if bal>=mf else dia(k,bc,C,max(mf-bal,100),room)
            if q: est='x'; continue
            bal+=r; dias+=1
            if bal>=mf and dias>=4: est='p2' if est=='p1' else 'f'; bal=0.0; dias=0
        else:
            r,q=dia(k,bf,C,None,min(5000,bal+10000))
            if q: est='x'; continue
            bal+=r; df+=1
            if df%10==0 and bal>0:
                pago+=0.8*bal; bal=0.0
                if reemb_ok: reemb+=1; reemb_ok=False
    return pago-(compras-reemb)*fee*EUR, pago>0, compras
def un_paso(s,C,nmax,bc,bf,fee=499,H=252,R=6000):
    """1-Step: meta 10%, diario 3%, máx 10% trailing EOD (sin bloqueo), mejor día ≤50% de días positivos; fondeada 90%, cada 10 días, piso se queda en el pico."""
    pago=0; compras=0; est=None
    for k in range(s,min(s+H,len(fechas))):
        if est in (None,'x'):
            if compras>=nmax: break
            est='c'; bal=0.0; pico=0.0; pos=[]; compras+=1; df=0
        piso=max(0.0,pico)-10000
        room=min(3000, bal-piso)
        if est=='c':
            r,q=dia(k,bc,C,max(10000-bal,100),room)
            if q: est='x'; continue
            bal+=r; pico=max(pico,bal)
            if r>0: pos.append(r)
            if bal>=10000 and pos and max(pos)<=0.5*sum(pos): est='f'; bal=0.0; pico=0.0; pos=[]
        else:
            r,q=dia(k,bf,C,None,room)
            if q: est='x'; continue
            bal+=r; pico=max(pico,bal); df+=1
            if r>0: pos.append(r)
            if df%10==0 and pos and max(pos)<=0.5*sum(pos):
                retiro=bal-(max(0.0,pico)-10000+R)       # deja R de espacio sobre el piso
                if retiro>0: pago+=0.9*retiro; bal-=retiro; pos=[]
    return pago-compras*fee*EUR, pago>0, compras
def instant(s,C,nmax,bf,fee=2999,H=252,R=6000):
    pago=0; compras=0; est=None
    for k in range(s,min(s+H,len(fechas))):
        if est in (None,'x'):
            if compras>=nmax: break
            est='f'; bal=0.0; pico=0.0; pos=[]; compras+=1; df=0
        room=min(3000, bal-(pico-10000))
        r,q=dia(k,bf,C,None,room)
        if q: est='x'; continue
        bal+=r; pico=max(pico,bal); df+=1
        if r>0: pos.append(r)
        if df>=10 and df%10==0 and pos and max(pos)<=0.3*sum(pos):
            retiro=bal-(pico-10000+R)
            if retiro>0: pago+=0.9*retiro; bal-=retiro; pos=[]
    return pago-compras*fee*EUR, pago>0, compras
starts=list(range(0,len(fechas)-260,3))
def res(f):
    A=np.array([f(s) for s in starts]); g=A[:,0]
    return f"no cobra {np.mean(A[:,1]==0):4.0%} · termina ganando {np.mean(g>0):4.0%} · mediana ${np.median(g):>8,.0f} · p10 ${np.percentile(g,10):>8,.0f} · p90 ${np.percentile(g,90):>8,.0f} · retos {A[:,2].mean():.1f}"
import sys
for mit,nom in ((False,'pruebas'),(True,'mitad')):
    C=caminos(mit)
    print('==',nom,flush=True)
    print('2-Step  6/4 4 retos ', res(lambda s: dos_pasos(s,C,4)),flush=True)
    for bc,bf in ((3,2),(4,3),(5,3),(6,4)):
        print(f'1-Step {bc}/{bf} 4 retos', res(lambda s: un_paso(s,C,4,bc,bf)),flush=True)
    for bf in (2,3,4):
        print(f'Instant {bf} 1 cuenta', res(lambda s: instant(s,C,1,bf)),flush=True)
