import os, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0])
C=np.load('caminos_C.npy'); W=np.load('caminos_W.npy')
fechas=pd.DatetimeIndex([pd.Timestamp(arr[k].d) for k in range(20,len(arr))]); assert len(fechas)==len(C)
vol=pd.Series([np.mean([arr[j].h.max()-arr[j].l.min() for j in range(k-14,k)])/arr[k-1].c[-1] for k in range(20,len(arr))],index=fechas)
med=vol.rolling(250,min_periods=60).median().fillna(vol.expanding().median())
v=pd.read_csv('extra/vix_curva.csv',parse_dates=['fecha']).set_index('fecha'); r9=(v['^VIX9D']/v['^VIX']).shift(1).reindex(fechas)
peso=np.clip(med/vol,0.5,1.5).values
def n_dia(k, regla):
    if regla=='fijo': return 6
    n=max(1,round(6*peso[k]))
    if regla=='nuevo' and r9.iloc[k]>1.10: n=max(1,round(n*0.5))
    return n
def dia(k,n,meta=1550):
    c=n*C[k]; w=n*W[k]; peor=0.0
    for t in range(78):
        peor=min(peor,w[t])
        if c[t]>=meta: return c[t],peor
    return c[-1],peor
def examen(dias_idx, regla):
    """Reglas Lucid Flex 50K: meta +3,000; pérdida máxima −2,000 que sube con el máximo (al cierre) y se congela en +100 al pasar +2,100; consistencia 50%."""
    bal=alto=mejor=0.0; mll=-2000.0; bloq=False
    for i,k in enumerate(dias_idx):
        r,peor=dia(k,n_dia(k,regla))
        if bal+peor<=mll: return 'quema',i+1
        bal+=r; mejor=max(mejor,r)
        if not bloq:
            alto=max(alto,bal); mll=alto-2000
            if bal>2100: mll=100; bloq=True
        if bal>=3000 and mejor<=0.5*bal: return 'pasa',i+1
    return 'sigue',len(dias_idx)
def resumen(nombre, regla):
    # 1) en orden histórico real: un examen empezando en cada día de 2019–2026
    R=[examen(range(s,min(s+60,len(C))),regla) for s in range(len(C)-60)]
    P=[d for r,d in R if r=='pasa']; Q=[d for r,d in R if r=='quema']
    p=len(P)/len(R); dpi=np.mean([d for r,d in R])
    # 2) cadena real: si quema, compra otro al día siguiente; ¿cuántos días hábiles hasta fondearse?
    hasta=[]; examenes=[]
    for s in range(0,len(C)-300,5):
        k=s; n=0
        while k<len(C)-60:
            r,d=examen(range(k,k+60),regla); n+=1; k+=d
            if r=='pasa': hasta.append(k-s); examenes.append(n); break
    hasta=np.array(hasta); examenes=np.array(examenes)
    print(f"\n{nombre}\n  por intento: pasa {p:.0%} · quema {len(Q)/len(R):.0%} · dura {dpi:.1f} días (pasa en {np.median(P):.0f} días mediana, quema en {np.median(Q):.0f})")
    print(f"  hasta fondearse: mediana {np.median(hasta):.0f} días hábiles (~{np.median(hasta)/21:.1f} meses) · 25%-75%: {np.percentile(hasta,25):.0f}-{np.percentile(hasta,75):.0f} días · peor 10%: {np.percentile(hasta,90):.0f}+ días")
    print(f"  exámenes hasta fondearse: mediana {np.median(examenes):.0f} · promedio {examenes.mean():.1f} · 1er intento {np.mean(examenes==1):.0%} · 10% peor: {np.percentile(examenes,90):.0f}+")
    a=pd.Series([r for r,d in R],index=fechas[:len(R)]); print('  pasa por año:', a.groupby(a.index.year).apply(lambda z:(z=='pasa').mean()).round(2).to_dict())
resumen('Antes (6 MNQ fijos + meta diaria 1,550)','fijo')
resumen('MAÑANA (6 MNQ × volatilidad, ½ con miedo de corto plazo, meta 1,550)','nuevo')
print('\nHoy: peso por volatilidad =', round(float(np.clip(med.iloc[-1]/vol.iloc[-1],0.5,1.5)),2), '→', max(1,round(6*float(np.clip(med.iloc[-1]/vol.iloc[-1],0.5,1.5)))),'MNQ (aprox., con datos Dukascopy)')
