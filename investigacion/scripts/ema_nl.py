import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
closes=np.concatenate([g.c for g in arr]); off=np.cumsum([0]+[len(g.c) for g in arr])
SP=(100,150,200,300,400,600); EM={sp:pd.Series(closes).ewm(span=sp,adjust=False).mean().values for sp in SP}
rows=[]
for k in range(220,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    for est,trs in (('orb',orb_t(g)),('ru',ruido_t(g,hist,arr[k-1].c[-1]))):
        for s,e,x,a,b in trs:
            px,ie=(e,a-1) if est=='orb' else (g.c[a],a)          # ORB: precio de entrada vs EMA de la vela anterior (sin ver el futuro)
            rows.append(dict(fecha=pd.Timestamp(g.d),est=est,s=s,pnl=s*(x-e)*USD-COSTO,**{f'e{sp}':np.sign(px-EM[sp][off[k]+ie]) for sp in SP}))
T=pd.DataFrame(rows); dias=pd.DatetimeIndex(sorted({pd.Timestamp(g.d) for g in arr[220:]})); m=len(dias)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252); dd=lambda z:(z.cumsum()-z.cumsum().cummax()).min()
b=T.groupby('fecha').pnl.sum().reindex(dias,fill_value=0); print(f"sin filtro: ${b.mean():.1f}/día · Sharpe {sh(b):.2f} ({sh(b.iloc[:m]):.2f}/{sh(b.iloc[m:]):.2f}) · caída {dd(b):,.0f}")
for sp in SP:
    z=T[T.s==T[f'e{sp}']].groupby('fecha').pnl.sum().reindex(dias,fill_value=0); c=T[T.s!=T[f'e{sp}']]
    print(f"EMA {sp:3}: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · caída {dd(z):,.0f} · en contra: {len(c)} trades, ${c.pnl.mean():5.1f}/trade (t {c.pnl.mean()/c.pnl.std()*np.sqrt(len(c)):.2f}) · ORB en contra ${c[c.est=='orb'].pnl.mean():.1f} · ruido en contra ${c[c.est=='ru'].pnl.mean():.1f}")
T.to_pickle('ema_trades.pkl')
