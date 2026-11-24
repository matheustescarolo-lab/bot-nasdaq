import os, warnings, numpy as np, pandas as pd; warnings.filterwarnings('ignore')
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('bt.py').read().split("print(f'{len(dias)}")[0].replace("print(f'{len(dias)}","pass #"))
exec(open('bt.py').read().split("class G: pass")[1].split("def corre")[0].replace("arr=[]","arr=[]",1)) if False else None
# reconstruye arr (78 velas por día, 9:30–15:55)
class G: pass
arr=[]
for d,g in dias:
    idx=pd.date_range(pd.Timestamp(d)+pd.Timedelta(hours=9,minutes=30), periods=78, freq='5min')
    g=g.reindex(idx); g['close']=g.close.ffill(); g['tick_volume']=g.tick_volume.fillna(0)
    for k in ['open','high','low']: g[k]=g[k].fillna(g.close)
    x=G(); x.o,x.h,x.l,x.c,x.v=(g[k].values for k in ['open','high','low','close','tick_volume']); x.d=pd.Timestamp(d); arr.append(x)
USD=2.0; CO=3.4   # spread 0.7 + 1 punto de deslizamiento, por 1 MNQ
F=[a.d for a in arr]
def rep(nombre, pnl):
    s=pd.Series(pnl,index=F); s=s.iloc[20:]; m=len(s)//2; n=(s!=0).sum()
    sh=lambda z: z.mean()/z.std()*np.sqrt(252) if z.std()>0 else 0
    tr=s[s!=0]
    print(f"{nombre:<60} ${s.mean():5.1f}/día · Sharpe {sh(s):5.2f} ({sh(s[:m]):5.2f}/{sh(s[m:]):5.2f}) · {n} trades · aciertos {(tr>0).mean():.0%} · caída ${(s.cumsum()-s.cumsum().cummax()).min():,.0f}")
    return s
# ---------- A. Entrar con la sacudida ----------
def sacudida_entrada(umbral, modo, hold):
    out=[]
    for a in arr:
        r=a.c/np.r_[a.o[0],a.c[:-1]]-1; res=0.0
        for i in range(6, 70):                         # desde las 10:00, primera sacudida del día
            if abs(r[i])>umbral:
                s=np.sign(r[i])*(1 if modo=='momentum' else -1); e=a.c[i]; tam=abs(a.c[i]-a.o[i]) or abs(r[i])*e
                st=e-s*tam                              # stop: el tamaño de la vela de la sacudida
                fin=min(i+hold, 76) if hold else 76; x=a.c[fin]
                for j in range(i+1, fin+1):
                    if (s>0 and a.l[j]<=st) or (s<0 and a.h[j]>=st): x=st; break
                res=s*(x-e)*USD-CO; break
        out.append(res)
    return out
print('A) ENTRAR CON LA SACUDIDA (1 MNQ, primera sacudida del día desde las 10:00, stop = tamaño de la vela)')
for u in (0.004,0.006,0.008):
    for modo in ('momentum','reversión'):
        for hold in (6,12,0):
            rep(f'  >{u:.1%} · {modo} · {"hasta 15:55" if not hold else str(hold*5)+" min"}', sacudida_entrada(u,modo,hold))
# ---------- B. Momentum intradía (Gao, Han, Li y Zhou 2018) ----------
def gao(con_penultima):
    out=[]
    for k,a in enumerate(arr):
        if k==0: out.append(0.0); continue
        r1=a.c[5]/arr[k-1].c[-1]-1                     # cierre de ayer → 10:00
        r2=a.c[70]/a.c[64]-1                           # 15:00 → 15:30
        sig=np.sign(r1) if not con_penultima else (np.sign(r1) if np.sign(r1)==np.sign(r2) else 0)
        e=a.c[71]; x=a.c[76]                           # entra 15:30 (cierre de la vela 15:25), sale 15:55
        out.append(sig*(x-e)*USD-CO if sig else 0.0)
    return out
print('\nB) MOMENTUM INTRADÍA: la primera media hora predice la última (Gao, Han, Li y Zhou 2018)')
rep('  Señal = cierre de ayer→10:00; opera 15:30→15:55', gao(False))
rep('  Solo si 15:00→15:30 va en la misma dirección', gao(True))
# ---------- C. Cierre de gaps ----------
def gap(umbral, modo):
    out=[]
    for k,a in enumerate(arr):
        if k==0: out.append(0.0); continue
        pc=arr[k-1].c[-1]; g=a.o[0]/pc-1
        if abs(g)<umbral: out.append(0.0); continue
        s=-np.sign(g) if modo=='cerrar' else np.sign(g); e=a.o[0]; obj=pc; st=e+np.sign(g)*abs(e-pc)*(1 if modo=='cerrar' else -1)
        x=a.c[76]
        for j in range(0,77):
            if modo=='cerrar' and ((s>0 and a.h[j]>=obj) or (s<0 and a.l[j]<=obj)): x=obj; break
            if (s>0 and a.l[j]<=st) or (s<0 and a.h[j]>=st): x=st; break
        out.append(s*(x-e)*USD-CO)
    return out
print('\nC) GAPS DE APERTURA (objetivo = cierre de ayer, stop = tamaño del gap)')
for u in (0.003,0.006,0.01):
    rep(f'  gap >{u:.1%} · apostar a que se cierra', gap(u,'cerrar'))
    rep(f'  gap >{u:.1%} · seguir el gap', gap(u,'seguir'))
