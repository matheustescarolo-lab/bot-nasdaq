import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
D=pd.read_pickle('flujo.pkl')
def fade(g, hist, prev, d, stop_m, fin_h=900, solo_dentro=True):
    """Reversión: en los chequeos de cada 30 min (10:00–fin), si el precio se alejó del VWAP más de d×(movimiento típico a esa hora),
    entra hacia el VWAP. Sale al tocar el VWAP, con stop a stop_m×la distancia, o a las 15:55."""
    o,h,l,c,v = g.o,g.h,g.l,g.c,g.v; op=o[0]
    sig = np.array([np.mean([m[i] if len(m)>i else m[-1] for m in hist]) for i in range(len(c))])
    ub = max(op,prev)*(1+sig); lb = min(op,prev)*(1-sig)
    vw = np.cumsum((h+l+c)/3*v)/np.maximum(np.cumsum(v),1)
    for i in range(CIERRE):
        fin=(i+1)*5+570
        if fin < 600 or fin % 30 or fin > fin_h: continue
        dev=(c[i]-vw[i])/(vw[i]*max(sig[i],1e-6))
        if abs(dev) < d: continue
        if solo_dentro and not (lb[i] < c[i] < ub[i]): continue          # si está fuera de la zona de ruido, es tendencia: no se pelea
        s=-1 if dev>0 else 1; e=c[i]; dist=abs(c[i]-vw[i]); st=e - s*stop_m*dist
        for j in range(i+1, CIERRE+1):
            if (s==1 and l[j]<=st) or (s==-1 and h[j]>=st): return s*(st-e)*USD-COSTO
            if (s==1 and h[j]>=vw[j]) or (s==-1 and l[j]<=vw[j]): return s*(max(vw[j],o[j]) - e if s==1 else e-min(vw[j],o[j]))*USD-COSTO if False else s*((vw[j] if (s==1 and o[j]<vw[j]) or (s==-1 and o[j]>vw[j]) else o[j])-e)*USD-COSTO
        return s*(c[CIERRE]-e)*USD-COSTO
    return 0.0
fechas=[pd.Timestamp(arr[k].d) for k in range(20,len(arr))]; m=len(fechas)//2
sh=lambda a: a.mean()/a.std()*np.sqrt(252)
for dentro in (True,False):
  for d in (0.5,0.75,1.0,1.5):
    for sm in (1.0,2.0):
        z=pd.Series([fade(arr[k],[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)],arr[k-1].c[-1],d,sm,900,dentro) for k in range(20,len(arr))],index=fechas)
        t=z[z!=0]; comb=D.tot.add(z,fill_value=0).reindex(D.index)
        print(f"{'dentro zona' if dentro else 'siempre   '} d={d:<4} stop {sm}×: {len(t):4} trades · gana {(t>0).mean():.0%} · ${z.mean():5.1f}/día · Sharpe {sh(z):5.2f} ({sh(z.iloc[:m]):5.2f}/{sh(z.iloc[m:]):5.2f}) · corr {np.corrcoef(z.reindex(D.index).fillna(0),D.tot)[0,1]:+.2f} · bot+esta {sh(comb):.2f}")
