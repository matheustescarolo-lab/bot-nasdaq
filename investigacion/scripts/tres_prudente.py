exec(open('tres_versiones.py').read().split("V=[(")[0])
C=C-15.0*np.arange(1,79)/78; W=W-15.0*np.arange(1,79)/78        # quita $15/día por MNQ ≈ la mitad de la ventaja
V=[('A · Conservadora (examen 3 MNQ)',3),('B · Equilibrada (examen 4 MNQ)',4),('C · Agresiva (examen 6 MNQ)',6)]
for H,nom in ((126,'6 MESES'),(252,'12 MESES')):
    for bf in (1,2):
        print(f'\n== PRUDENTE (mitad de la ventaja) · {nom} · fondeada {bf} MNQ ==')
        for v,be in V:
            R=[ciclo(s,H,be,bf) for s in range(0,len(C)-H,3)]
            net=np.array([r[0] for r in R]); ex=np.array([r[1] for r in R]); pf=[r[3] for r in R if r[3]]
            print(f"{v:<34} neto mediana ${np.median(net):6,.0f} · promedio ${net.mean():6,.0f} · gana dinero {np.mean(net>0):4.0%} · peor 10% ${np.percentile(net,10):6,.0f} · exámenes {ex.mean():4.1f} · 1er fondeo día {np.median(pf):.0f} ({len(pf)/len(R):.0%})")
