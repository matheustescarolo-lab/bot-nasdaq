exec(open("stop_orb.py").read().split("T=[]")[0])
src=open('orb_real.py').read()
rows=[]
for k in range(14,len(arr)):
    g=arr[k]; i=idx.get(pd.Timestamp(g.d))
    if i is None or np.isnan(vol[i]) or pd.Timestamp(g.d) in FOMC: continue
    r1=ret1[i]
    if not (r1 < -0.01): continue
    gap=g.o[0]/arr[k-1].c[-1]-1
    no=min(round(BASE*vol[i]*r9[i]*ev[i]),2*BASE); nr=min(round(BASE*vol[i]*r9[i]*ev[i]*np.where(nfp[i],1.5,1)),2*BASE)
    orb=sum(s*(x-e)/e*P*2*no - 1.5*2*no for s,e,x,a,b in orb_v(g,True,True)) if no else 0
    hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    ru=sum(s*(x-e)/e*P*2*nr - 2*2*nr for s,e,x,a,b in ruido_t(g,hist,arr[k-1].c[-1])) if nr else 0
    lados=[s for s,*_ in orb_v(g,True,True)]
    rows.append((g.d,r1,gap,orb,ru,lados[0] if lados else 0, g.c[-1]/g.o[0]-1))
D=pd.DataFrame(rows,columns=['d','ayer','gap','orb','ruido','lado','dia'])
def tabla(m,nom):
    x=D[m]; print(f'{nom:45s} días {len(x):3d} · ORB ${x.orb.mean():+7,.0f}/día (gana {(x.orb>0).mean()*100:3.0f}%) · ruido ${x.ruido.mean():+7,.0f}/día · suma ${x.orb.sum()+x.ruido.sum():+9,.0f}')
print('Días que hoy bloquea el filtro (base 6 MNQ con las demás capas, costos incluidos, precio 27,000):')
tabla(D.ayer<-0.02,'ayer < −2% (ORB y ruido bloqueados)')
tabla((D.ayer<-0.02)&(D.gap>0.01),'  … y hoy abre con gap ≥ +1%')
tabla((D.ayer<-0.02)&(D.gap>0.005)&(D.gap<=0.01),'  … gap +0.5% a +1%')
tabla((D.ayer<-0.02)&(D.gap<=0.005),'  … gap < +0.5%')
tabla((D.ayer>=-0.02)&(D.ayer<-0.01),'ayer −1% a −2% (solo ruido bloqueado)')
tabla((D.ayer>=-0.02)&(D.ayer<-0.01)&(D.gap>0.01),'  … y hoy abre con gap ≥ +1%')
print('\nDías ayer<−2% y gap ≥ +1%:'); print(D[(D.ayer<-0.02)&(D.gap>0.01)][['d','ayer','gap','dia','orb','ruido']].round(4).to_string(index=False))
from math import sqrt
for thr in (0.0075,0.01,0.015):
    x=D[(D.ayer<-0.02)&(D.gap>thr)]; s=x.orb+x.ruido
    a=x[pd.to_datetime(x.d)<'2023-01-01']; b=x[pd.to_datetime(x.d)>='2023-01-01']
    print(f'gap>{thr*100:.2f}%: n={len(x)} t(ORB)={x.orb.mean()/x.orb.std()*sqrt(len(x)):.2f} t(total)={s.mean()/s.std()*sqrt(len(x)):.2f} · 2019–2022 ${(a.orb+a.ruido).mean():+,.0f}/día (n={len(a)}) · 2023–2026 ${(b.orb+b.ruido).mean():+,.0f}/día (n={len(b)})')
