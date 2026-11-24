exec(open('mejor_examen.py').read().split("mide('Mañana tal cual',{})")[0])
for b in (1,2,3,4,6):
    R=[examen2(range(s,min(s+400,len(C))),{'base':b,'meta_din':1}) for s in range(0,len(C)-400,3)]
    ps=np.array([r=='pasa' for r,d in R]); dp=[d for r,d in R if r=='pasa']; dq=[d for r,d in R if r=='quema']
    print(f"base {b} MNQ (+ capas + meta justa): pasa {ps.mean():4.0%} · si pasa, en {np.median(dp):3.0f} días (mediana) · si quema, en {np.median(dq) if dq else 0:3.0f} días · sin terminar {np.mean([r=='sigue' for r,d in R]):.0%}")
