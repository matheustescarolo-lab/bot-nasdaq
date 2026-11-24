import pickle, numpy as np, pandas as pd
import reglas as R
CB = pickle.load(open('rg_base.pkl','rb')); MO, MR = R.pesos()
no = np.round(6*MO); nr = np.round(6*MR)
orb = no*CB[0][:,-1]/6; ru = nr*CB[2][:,-1]/6
y = R.fechas.year
print('año  | ORB con capas $/día (t) | Ruido con capas $/día (t) | Ruido sin capas $/op (n)')
for a in sorted(set(y)):
    m = y==a; z = CB[2][m,-1]; z = z[z!=0]
    f = lambda x: f"{x.mean():6.1f} (t {x.mean()/x.std()*np.sqrt(len(x)):+4.1f})"
    print(a, '|', f(orb[m]), '|', f(ru[m]), '|', f"{z.mean():6.1f} ({len(z)})")
sh = lambda d, m: d[m].mean()/d[m].std()*np.sqrt(252)
d0,_,_ = R.diario(CB, MO, MR)
print('\nSharpe bot completo vs sin la capa: 1.ª mitad | 2.ª mitad | 2025–26')
print('completo', ' | '.join(f"{sh(d0,m):.2f}" for m in (R.h1,R.h2,R.r2526)))
for s in ('vol','r9','cot','caida','tope','gig','pay','nfp'):
    d,_,_ = R.diario(CB, *R.pesos((s,)))
    print(f"sin {s:6}", ' | '.join(f"{sh(d,m):.2f}" for m in (R.h1,R.h2,R.r2526)))
d,_,_ = R.diario(CB, MO, MR*0); print('sin ruido', ' | '.join(f"{sh(d,m):.2f}" for m in (R.h1,R.h2,R.r2526)), '· $/día', ' | '.join(f"{d[m].mean():.1f}" for m in (R.h1,R.h2,R.r2526)))
print('completo $/día', ' | '.join(f"{d0[m].mean():.1f}" for m in (R.h1,R.h2,R.r2526)))
