import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
closes=np.concatenate([g.c for g in arr]); ema5=pd.Series(closes).ewm(span=200,adjust=False).mean().values
off=np.cumsum([0]+[len(g.c) for g in arr])
dcl=pd.Series([g.c[-1] for g in arr]); emad=dcl.ewm(span=200,adjust=False).mean().values; smad=dcl.rolling(200).mean().values
rows=[]
for k in range(220,len(arr)):
    g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    for est,trs in (('orb',orb_t(g)),('ru',ruido_t(g,hist,arr[k-1].c[-1]))):
        for s,e,x,a,b in trs:
            px=g.c[a]; rows.append(dict(k=k,fecha=pd.Timestamp(g.d),est=est,s=s,pnl=s*(x-e)*USD-COSTO,
               e5=np.sign(px-ema5[off[k]+a]), ed=np.sign(arr[k-1].c[-1]-emad[k-1]), sd=np.sign(arr[k-1].c[-1]-smad[k-1])))
T=pd.DataFrame(rows); dias=pd.DatetimeIndex(sorted({pd.Timestamp(g.d) for g in arr[220:]})); m=len(dias)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252)
def rep(n,mask):
    z=T[mask].groupby('fecha').pnl.sum().reindex(dias,fill_value=0)
    t=T[mask]; print(f"{n:<52} trades {len(t):5} · gana {(t.pnl>0).mean():.0%} · ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f})")
todo=T.pnl==T.pnl
rep('Bot actual (sin filtro)',todo)
for col,nom in (('e5','EMA 200 de velas de 5 min'),('ed','EMA 200 diaria'),('sd','media 200 días')):
    rep(f'A favor de la {nom} (largos arriba, cortos abajo)', T.s==T[col])
    rep(f'Solo compras arriba de la {nom}', (T.s==1)&(T[col]==1))
print('\nPor estrategia, a favor de la EMA 200 de 5 min:')
for est in ('orb','ru'):
    rep(f'  {est} sin filtro',T.est==est); rep(f'  {est} a favor',(T.est==est)&(T.s==T.e5)); rep(f'  {est} en contra',(T.est==est)&(T.s!=T.e5))
