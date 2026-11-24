exec(open('ftmo_nasdaq.py').read().split("def tabla(")[0])
def primer(s,bc,ini=100000,freno=400):
    estado='p1'; bal=prev=0.0; dias=0; listo=False; t=0; frenados=0
    for k in range(s,len(C)):
        t+=1
        meta_fase=(0.10 if estado=='p1' else 0.05)*ini
        piso=max(prev-0.05*ini,-0.10*ini)
        if listo: r,peor=0.0,0.0
        else:
            n=n_de(bc,k); lim=piso+freno-bal                       # pérdida del día en la que el bot cierra todo
            if lim>=0: return 'quema',t,estado,'sin margen'
            r,peor=corre(k,n,max(meta_fase-bal,100),-lim)          # corre() con freno = cierra al tocar -lim (con 1 punto de deslizamiento)
            if r<-lim*0.999 and bal+r<=piso: return 'quema',t,estado,'salto'
            if r<=-lim+1e-6 or abs(r+lim+n*1.0)<1e-6: frenados+=1
        bal+=r; prev=bal; dias+=1
        if bal<=-0.10*ini+freno*1.0 and not listo: return 'quema',t,estado,'sin margen'
        if bal>=meta_fase: listo=True
        if listo and dias>=4:
            if estado=='p1': estado='p2'; bal=prev=0.0; dias=0; listo=False
            else: return 'pasa',t,estado,frenados
    return 'sigue',t,estado,''
for bc in (4,5,6):
    R=[primer(s,bc) for s in range(0,len(C)-300,3)]
    p=[r for r in R if r[0]=='pasa']; q=[r for r in R if r[0]=='quema']
    print(f"reto {bc} MNQ (con freno): pasa {len(p)/len(R):.0%} en {np.median([r[1] for r in p]):.0f} días hábiles · se quema {len(q)/len(R):.0%} · días con freno antes de pasar (prom.) {np.mean([r[3] for r in p]):.1f}")
