import numpy as np, pandas as pd
F=pd.read_pickle('rebote.pkl'); F['año']=pd.to_datetime(F.fecha).dt.year
X=['rango_atr','rsi','vol_apertura','vol_previa','vwap','liq_ayer','liq_noche','gap','cierre_rango','minuto','sp_confirma','ret_ayer','pos_ayer']
t=lambda v: v.mean()/v.std()*np.sqrt(len(v)) if len(v)>2 else 0
print('Por quintil del indicador: ORB $/trade (desvanecer $/trade). Peor quintil para el ORB, con t y mitades')
mitad=F.fecha.iloc[len(F)//2]
for x in X:
    q=pd.qcut(F[x].rank(method='first'),5,labels=False) if F[x].nunique()>5 else F[x]
    gr=F.groupby(q)
    orb=' '.join(f"{m:6.1f}" for m in gr.pnl.mean()); fade=' '.join(f"{m:6.1f}" for m in gr.fade.mean())
    w=gr.pnl.mean().idxmin(); sub=F[q==w]
    print(f"{x:13} ORB [{orb}] · fade [{fade}] · peor: ORB t {t(sub.pnl):5.2f}, fade ${sub.fade.mean():6.1f} t {t(sub.fade):5.2f}, mitades fade ${sub[sub.fecha<mitad].fade.mean():6.1f}/${sub[sub.fecha>=mitad].fade.mean():6.1f}")
# modelo fuera de muestra (entrena con años anteriores)
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
out=[]
for y in range(2021,2027):
    tr,te=F[F.año<y],F[F.año==y]
    Xtr,Xte=tr[X].fillna(0),te[X].fillna(0)
    for nom,mod in (('lineal',Ridge(alpha=10.0)),('árboles',GradientBoostingRegressor(n_estimators=150,max_depth=2,learning_rate=0.05,subsample=0.7,random_state=0))):
        po=mod.fit(Xtr,tr.pnl).predict(Xte); pf=type(mod)(**mod.get_params()).fit(Xtr,tr.fade).predict(Xte)
        for i,(a_,b_) in enumerate(zip(po,pf)):
            r=te.iloc[i]
            elegido=r.pnl if a_>=b_ and a_>0 else (r.fade if b_>a_ and b_>0 else 0.0)
            solo_orb=r.pnl if a_>0 else 0.0
            out.append(dict(año=y,modelo=nom,base=r.pnl,ambas=elegido,filtro=solo_orb,fade_usado=int(b_>a_ and b_>0)))
O=pd.DataFrame(out)
for nom,G in O.groupby('modelo'):
    print(f"\nFuera de muestra 2021–2026 ({nom}), $/trade: solo ORB {G.base.mean():.1f} · ORB con filtro {G.filtro.mean():.1f} · ORB + desvanecer según el modelo {G.ambas.mean():.1f} (desvanece {G.fade_usado.mean():.0%} de los días)")
    print('   por año ORB / con modelo:', ' '.join(f"{y}: {g.base.mean():.0f}/{g.ambas.mean():.0f}" for y,g in G.groupby('año')))
