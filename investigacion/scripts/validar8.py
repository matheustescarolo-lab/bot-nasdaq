import os, numpy as np, pandas as pd
exec(open('bt2.py').read().split("print('RANGO 30 MIN")[0])
R = pd.read_pickle(os.environ['ARCH']+'.pkl')
# protecciones: ¿se sostienen en 8 años?
def serie(fn):
    out=[]; f=[]
    for k in range(20,len(arr)):
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        out.append(sum(x*USD-COSTO for x in fn(arr[k],hist,arr[k-1].c[-1]))); f.append(arr[k].d)
    return pd.Series(out,index=pd.to_datetime(f))
sh=lambda z: z.mean()/z.std()*np.sqrt(252)
dd=lambda z: (z.cumsum()-z.cumsum().cummax()).min()
S={'ORB sin protección':serie(lambda g,h,p: orb_g(g)),
   'ORB con break even $150':serie(lambda g,h,p: orb_g(g,regla=dict(tipo='be',activa=150))),
   'Ruido sin protección':serie(lambda g,h,p: ruido_g(g,h,p)),
   'Ruido con escalera $200':serie(lambda g,h,p: ruido_g(g,h,p,regla=dict(tipo='escalera',activa=200))),
   'Ruido cada 60 min (sin protección)':serie(lambda g,h,p: ruido_g(g,h,p,cada=60))}
tf = pd.Series(np.where(R.lado_orb.values==R.tend.values, R.orb.values, 0.0), index=S['ORB con break even $150'].index)
S['ORB con break even + filtro tendencia']=tf
S['Combinado actual (BE + escalera)']=S['ORB con break even $150']+S['Ruido con escalera $200']
S['Combinado con filtro tendencia']=tf+S['Ruido con escalera $200']
print(f"{'':<40} {'US$/día':>8} {'Sharpe':>7} {'peor caída':>11}   Sharpe por año")
for k,z in S.items():
    años=' '.join(f"{y}:{sh(z[z.index.year==y]):5.2f}" for y in sorted(set(z.index.year)))
    print(f"{k:<40} {z.mean():8.1f} {sh(z):7.2f} {dd(z):11,.0f}   {años}")
