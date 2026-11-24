exec(open('ftmo_nasdaq.py').read().split("def tabla(")[0])
import sys
def primer(s,bc,ini=100000):
    estado='p1'; bal=prev=0.0; dias=0; listo=False; t=0
    for k in range(s,len(C)):
        t+=1; meta_fase=(0.10 if estado=='p1' else 0.05)*ini
        r,peor=(0.0,0.0) if listo else corre(k,n_de(bc,k),max(meta_fase-bal,100),None)
        if bal+peor<=max(prev-0.05*ini,-0.10*ini): return 'quema',t
        bal+=r; prev=bal; dias+=1
        if bal>=meta_fase: listo=True
        if listo and dias>=4:
            if estado=='p1': estado='p2'; bal=prev=0.0; dias=0; listo=False
            else: return 'pasa',t
    return 'sigue',t
pru=len(sys.argv)>1
if pru: C=C-15.0*np.arange(1,79)/78; W=W-15.0*np.arange(1,79)/78
print('PRUDENTE (½ ventaja)' if pru else 'HISTÓRICO')
for bc in (5,6,8,10,12,15):
    R=[primer(s,bc) for s in range(0,len(C)-300,3)]
    p=np.mean([r[0]=='pasa' for r in R]); dp=np.median([r[1] for r in R if r[0]=='pasa']); dq=np.median([r[1] for r in R if r[0]=='quema'] or [0])
    N=[ftmo(s,252,bc,4) for s in range(0,len(C)-252,3)]; net=np.array([x[0] for x in N]); rt=np.mean([x[1] for x in N])
    print(f"reto {bc:2} MNQ: pasa {p:4.0%} · si pasa en {dp:3.0f} días hábiles · si quema en {dq:3.0f} · 12 meses (fondeada 4): neto mediana ${np.median(net):7,.0f} · promedio ${net.mean():7,.0f} · gana {np.mean(net>0):4.0%} · retos {rt:4.1f}")
