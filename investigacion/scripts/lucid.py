exec(open('bt2.py').read().split("print('RANGO 30 MIN")[0])
import numpy as np
def serie(fo, fr):
    out=[]
    for k in range(14, len(arr)):
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        a=sum(x*USD-COSTO for x in fo(arr[k],hist,arr[k-1].c[-1])); b=sum(x*USD-COSTO for x in fr(arr[k],hist,arr[k-1].c[-1]))
        out.append(a+b)
    return np.array(out)
base = serie(lambda g,h,p: orb_g(g), lambda g,h,p: ruido_g(g,h,p))
prot = serie(lambda g,h,p: orb_g(g, regla=dict(tipo='be', activa=150)), lambda g,h,p: ruido_g(g,h,p, regla=dict(tipo='escalera', activa=200)))
print(f'días {len(base)} · base ${base.mean():.1f}/día · con protección ${prot.mean():.1f}/día · días ≥$150: {np.mean(prot>=150):.0%}')

def simula(pnl, dias=252, precio=150, mensual=29, n=20000, seed=1):
    rng=np.random.default_rng(seed); netos=[]; cobros=[]; examenes=[]; pasa_dias=[]
    for _ in range(n):
        gasto=precio; neto=0.0; fase='examen'; bal=50000.0; alto=50000.0; mll=48000.0; bloq=False
        mejor_dia=0.0; ciclo_dias=0; ciclo_pnl=0.0; npagos=0; ex=1; d_pase=None
        for d in range(dias):
            x = pnl[rng.integers(len(pnl))]
            bal += x
            if fase=='examen':
                mejor_dia=max(mejor_dia,x)
            else:
                ciclo_pnl+=x; ciclo_dias += x>=150
            if bal <= mll:                                     # quemó la cuenta: compra otro examen
                gasto+=precio; ex+=1; fase='examen'; bal=50000.0; alto=50000.0; mll=48000.0; bloq=False; mejor_dia=0.0
                continue
            if not bloq:
                alto=max(alto,bal); mll=alto-2000
                if bal>52100: mll=50100; bloq=True
            if fase=='examen':
                g=bal-50000
                if g>=3000 and mejor_dia<=0.5*g:
                    fase='fondeada'; bal=50000.0; alto=50000.0; mll=48000.0; bloq=False; ciclo_dias=0; ciclo_pnl=0.0
                    if d_pase is None: d_pase=d
            else:
                g=bal-50000
                if ciclo_dias>=5 and ciclo_pnl>0 and npagos<5:
                    retiro=min(0.5*g, 2000)
                    if retiro>=500:
                        neto+=0.9*retiro; bal-=retiro; npagos+=1; mll=50100; bloq=True; ciclo_dias=0; ciclo_pnl=0.0
        netos.append(neto - gasto - mensual*dias/21); cobros.append(npagos); examenes.append(ex); pasa_dias.append(d_pase)
    netos=np.array(netos); cobros=np.array(cobros)
    pd_ = [p for p in pasa_dias if p is not None]
    return dict(neto_medio=netos.mean(), neto_mediana=np.median(netos), p_cobra=np.mean(cobros>0), cobros=cobros.mean(),
                examenes=np.mean(examenes), p_pierde=np.mean(netos<0), dias_pasar=np.median(pd_) if pd_ else None, p10=np.percentile(netos,10), p90=np.percentile(netos,90))
for nombre, s in [('Actual (sin protección)', base), ('Con break even + escalera', prot)]:
    for esc, ser in [('historia', s), ('prudente (mitad de la ventaja)', s - s.mean()/2)]:
        r=simula(ser)
        print(f"{nombre:<27} {esc:<31} neto medio ${r['neto_medio']:>6,.0f} · mediana ${r['neto_mediana']:>6,.0f} · p10 ${r['p10']:>6,.0f} · p90 ${r['p90']:>6,.0f} · cobra {r['p_cobra']:.0%} · retiros {r['cobros']:.1f} · exámenes {r['examenes']:.1f} · días para pasar {r['dias_pasar']} · pierde {r['p_pierde']:.0%}")
print('\nSensibilidad (con break even + escalera, historia):')
for etq, kw, ser in [('examen $90 con código + CrossTrade anual $23/mes', dict(precio=90, mensual=23), prot),
                     ('igual, escenario prudente', dict(precio=90, mensual=23), prot - prot.mean()/2),
                     ('2 MNQ por estrategia, examen $90, $23/mes', dict(precio=90, mensual=23), 2*prot + COSTO*0),
                     ('igual, a 24 meses', dict(precio=90, mensual=23, dias=504), prot)]:
    r=simula(ser, n=10000, **kw)
    print(f"{etq:<50} neto medio ${r['neto_medio']:>6,.0f} · mediana ${r['neto_mediana']:>6,.0f} · cobra {r['p_cobra']:.0%} · exámenes {r['examenes']:.1f} · pierde {r['p_pierde']:.0%}")
