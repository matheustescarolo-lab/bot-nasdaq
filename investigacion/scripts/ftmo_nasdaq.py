exec(open('mejor_examen.py').read().split("mide('Mañana tal cual',{})")[0])
import sys
EURUSD=1.10
def n_de(base,k):
    n=max(1,round(base*peso[k])); return max(1,round(n*0.5)) if r9.iloc[k]>1.10 else n
def ftmo(s,H,bc,bf,ini0=100000,fee_eur=540):
    FEE=fee_eur*EURUSD; gasto=FEE; cobrado=0.0; retos=1; estado='p1'; ini=ini0; esc=1.0; split=0.8
    bal=0.0; prev=0.0; dias=0; listo=False; primer=None; pagos=0; reembolso=True; dias_f=0; ciclo_g=0.0; ciclo_p=0; ciclo_d=0
    for i,k in enumerate(range(s,min(s+H,len(C)))):
        if estado in ('p1','p2'):
            meta_fase=(0.10 if estado=='p1' else 0.05)*ini0
            if listo: r,peor=0.0,0.0                         # ya llegó a la meta: solo cumple días mínimos con un trade mínimo
            else: r,peor=corre(k,n_de(bc,k),max(meta_fase-bal,100),None)
        else:
            r,peor=corre(k,n_de(bf,k)*esc,None,None)
        piso=max(prev-0.05*ini, -0.10*ini)
        if bal+peor<=piso:                                       # pérdida diaria o máxima → reto nuevo
            gasto+=FEE; retos+=1; estado='p1'; ini=ini0; esc=1.0; split=0.8; bal=prev=0.0; dias=0; listo=False; reembolso=True; continue
        bal+=r; prev=bal; dias+=1
        if estado in ('p1','p2'):
            if bal>=meta_fase: listo=True
            if listo and dias>=4:
                if estado=='p1': estado='p2'
                else:
                    estado='fondeada'; primer=primer or i+1; dias_f=0; ciclo_g=0.0; ciclo_p=0; ciclo_d=0
                bal=prev=0.0; dias=0; listo=False
        else:
            dias_f+=1; ciclo_d+=1
            if dias_f%10==0 and bal>0:                           # cada 14 días naturales ≈ 10 hábiles
                cobrado+=split*bal; ciclo_g+=bal; ciclo_p+=1; pagos+=1
                if reembolso: cobrado+=FEE; reembolso=False
                bal=prev=0.0
            if ciclo_d>=84:                                      # plan de escalado: 4 meses, +10%, 2+ retiros
                if ciclo_g>=0.10*ini and ciclo_p>=2: ini*=1.25; esc*=1.25; split=0.9
                ciclo_g=0.0; ciclo_p=0; ciclo_d=0
    return cobrado-gasto, retos, pagos, primer
def tabla(H,combos,titulo,**kw):
    print(f'\n== {titulo} ==')
    for bc,bf in combos:
        R=[ftmo(s,H,bc,bf,**kw) for s in range(0,len(C)-H,3)]
        net=np.array([r[0] for r in R]); rt=np.array([r[1] for r in R]); pf=[r[3] for r in R if r[3]]; m=len(net)//2
        print(f"reto {bc} / fondeada {bf} MNQ: neto mediana ${np.median(net):7,.0f} · promedio ${net.mean():7,.0f} ({net[:m].mean():,.0f}/{net[m:].mean():,.0f}) · gana {np.mean(net>0):4.0%} · peor 10% ${np.percentile(net,10):7,.0f} · retos {rt.mean():4.1f} · fondeada día {np.median(pf) if pf else 0:.0f} ({len(pf)/len(R):.0%})")
combos=[(2,2),(3,3),(4,3),(4,4),(5,4),(6,4),(6,6)]
if len(sys.argv)>1 and sys.argv[1]=='prudente':
    C=C-15.0*np.arange(1,79)/78; W=W-15.0*np.arange(1,79)/78
    tabla(252,combos,'PRUDENTE · FTMO 100K 2-Step · 12 meses')
    tabla(126,combos,'PRUDENTE · FTMO 100K 2-Step · 6 meses')
else:
    tabla(252,combos,'FTMO 100K 2-Step (€540) · 12 meses')
    tabla(126,combos,'FTMO 100K 2-Step · 6 meses')
