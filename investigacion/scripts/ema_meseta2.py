exec(open('ema200.py').read().split("T=pd.DataFrame(rows)")[0].replace("ema5=pd.Series(closes).ewm(span=200,adjust=False).mean().values","EMAS={sp:pd.Series(closes).ewm(span=sp,adjust=False).mean().values for sp in (50,100,150,200,300,400,600)}").replace("e5=np.sign(px-ema5[off[k]+a]),","**{f'e{sp}':np.sign(px-EMAS[sp][off[k]+ie]) for sp in EMAS},"))
T=pd.DataFrame(rows); dias=pd.DatetimeIndex(sorted({pd.Timestamp(g.d) for g in arr[220:]})); m=len(dias)//2
sh=lambda z: z.mean()/z.std()*np.sqrt(252)
base=T.groupby('fecha').pnl.sum().reindex(dias,fill_value=0); print(f"sin filtro: ${base.mean():.1f}/día · Sharpe {sh(base):.2f} ({sh(base.iloc[:m]):.2f}/{sh(base.iloc[m:]):.2f}) · caída {(base.cumsum()-base.cumsum().cummax()).min():,.0f}")
for sp in (50,100,150,200,300,400,600):
    z=T[T.s==T[f'e{sp}']].groupby('fecha').pnl.sum().reindex(dias,fill_value=0)
    contra=T[T.s!=T[f'e{sp}']]
    print(f"EMA {sp:3} velas de 5 min: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z.iloc[:m]):.2f}/{sh(z.iloc[m:]):.2f}) · caída {(z.cumsum()-z.cumsum().cummax()).min():,.0f} · trades en contra ganan ${contra.pnl.mean():5.1f}/trade (t {contra.pnl.mean()/contra.pnl.std()*np.sqrt(len(contra)):.2f})")
