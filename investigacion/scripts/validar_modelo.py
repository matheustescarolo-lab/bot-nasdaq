import numpy as np, pandas as pd
T=pd.read_pickle('modelo_trades.pkl'); W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]')
T['fecha']=T.fecha.astype('datetime64[ns]'); T=T.join(W,on='fecha')
T['w']=T.vol*T.r9*T.cot*np.where(T.gig,1.5,1)*np.where(T.nfp&(T.estr=='ruido'),1.5,1)
T=T[T.año>=2021]; dias=W.index[W.index>=T.fecha.min()]
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
def s(m,col='w'): return (T[m].pnl*T[m][col]).groupby(T[m].fecha).sum().reindex(dias,fill_value=0)
base=s(T.pnl==T.pnl); mod=s(T.toma)
print('Fuera de muestra 2021–2026, con todas las capas activas (1 MNQ base):')
for n,z in (('sin modelo',base),('con modelo (salta 40% peor)',mod)):
    h=len(z)//2; print(f"  {n:<30} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
print('\nPor año ($ total sin → con modelo · aciertos de los que salta vs los que toma):')
for y,g in T.groupby('año'):
    b=(g.pnl*g.w).sum(); m=(g[g.toma].pnl*g[g.toma].w).sum(); sk=g[~g.toma]
    print(f"  {y}: ${b:8,.0f} → ${m:8,.0f} · saltados {len(sk)} ganan {sk.gana.mean():.0%} (${sk.pnl.mean():.1f}/trade) · tomados ganan {g[g.toma].gana.mean():.0%} (${g[g.toma].pnl.mean():.1f})")
for e in ('orb','ruido'):
    g=T[T.estr==e]; sk=g[~g.toma]; tk=g[g.toma]
    t=(tk.pnl.mean()-sk.pnl.mean())/np.sqrt(tk.pnl.var()/len(tk)+sk.pnl.var()/len(sk))
    print(f"{e}: tomados ${tk.pnl.mean():.1f}/trade ({len(tk)}) vs saltados ${sk.pnl.mean():.1f} ({len(sk)}) · t {t:.2f}")
# alternativa: medio tamaño en vez de saltar
T['w2']=T.w*np.where(T.toma,1,0.5); z=s(T.pnl==T.pnl,'w2'); h=len(z)//2
print(f"  medio tamaño en los 40% peores: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
for nom,f in (('solo zona de ruido: salta 40% peor',lambda t: np.where((t.estr=='ruido')&~t.toma,0,1)),('solo zona de ruido: medio tamaño',lambda t: np.where((t.estr=='ruido')&~t.toma,0.5,1))):
    T['w3']=T.w*f(T); z=s(T.pnl==T.pnl,'w3'); h=len(z)//2
    print(f"  {nom:<36} ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:h]):.2f}/{sh(z.iloc[h:]):.2f}) · caída ${dd(z):,.0f}")
