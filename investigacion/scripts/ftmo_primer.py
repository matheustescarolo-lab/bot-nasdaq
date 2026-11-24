exec(open('ftmo_nasdaq.py').read().split("def tabla(")[0])
def primer(s,bc,ini=100000):
    estado='p1'; bal=prev=0.0; dias=0; listo=False; t=0
    for k in range(s,len(C)):
        t+=1
        meta_fase=(0.10 if estado=='p1' else 0.05)*ini
        r,peor=(0.0,0.0) if listo else corre(k,n_de(bc,k),max(meta_fase-bal,100),None)
        piso=max(prev-0.05*ini,-0.10*ini)
        if bal+peor<=piso: return 'quema',t,estado,('diaria' if prev-0.05*ini>-0.10*ini else 'maxima')
        bal+=r; prev=bal; dias+=1
        if bal>=meta_fase: listo=True
        if listo and dias>=4:
            if estado=='p1': estado='p2'; bal=prev=0.0; dias=0; listo=False
            else: return 'pasa',t,estado,''
    return 'sigue',t,estado,''
for bc in (3,4,5,6):
    R=[primer(s,bc) for s in range(0,len(C)-300,3)]
    p=[r for r in R if r[0]=='pasa']; q=[r for r in R if r[0]=='quema']
    print(f"reto {bc} MNQ: pasa las 2 fases {len(p)/len(R):.0%} (en {np.median([r[1] for r in p]):.0f} días hábiles) · se quema {len(q)/len(R):.0%} (en {np.median([r[1] for r in q]) if q else 0:.0f} días; en fase 1 {sum(r[2]=='p1' for r in q)/max(len(q),1):.0%}; por pérdida diaria {sum(r[3]=='diaria' for r in q)/max(len(q),1):.0%})")
