exec(open("stop_orb.py").read().split("T=[]")[0])
M0=4600.0; SL=2/P
def mfe_hasta(g,s,e,a,t):  # mejor movimiento a favor (pts) entre a+1..t
    xs=[(g.h[k]-e) if s==1 else (e-g.l[k]) for k in range(a+1,min(t,77)+1)]
    return max([0]+xs)
def mae_desde(g,s,e,a,b):
    return max([0]+[((e-g.l[k]) if s==1 else (g.h[k]-e)) for k in range(a+1,b+1)])
base_tot=0; delta=0; saltadas=0; recortadas=0; dias=0; solapes=0; sobre=0
for k in range(14,len(arr)):
    g=arr[k]; i=idx.get(pd.Timestamp(g.d))
    if i is None or np.isnan(mo[i]) or np.isnan(mr[i]): continue
    dias+=1
    no=min(round(BASE*mo[i]),2*BASE) if pd.Timestamp(g.d) not in FOMC else 0
    nr=min(round(BASE*mr[i]),2*BASE)
    hi,lo=g.h[:6].max(),g.l[:6].min()
    T_=[]
    if no:
        for s,e,x,a,b in orb_v(g,True,True):
            rk=min(4500,(e-lo if s==1 else hi-e)*2*no*P/e)
            T_.append(('orb',s,e,x,a,b,no,rk))
    if nr:
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        for s,e,x,a,b in ruido_t(g,hist,arr[k-1].c[-1]):
            rk=min(0.01*e*2*nr*P/e, 4500)
            T_.append(('ruido',s,e,x,a,b,nr,rk))
    for t in T_: base_tot+=t[1]*(t[3]-t[2])/t[2]*P*2*t[6]
    T_.sort(key=lambda t:t[4])
    for j2,t2 in enumerate(T_):
        abiertas=[t1 for t1 in T_[:j2] if t1[0]!=t2[0] and t1[4]<t2[4]<=t1[5]]
        if not abiertas: continue
        solapes+=1
        riesgo_otro=0
        for t1 in abiertas:
            be=75 if t1[0]=='orb' else 100   # pts a favor (1 MNQ) en que el stop ya no arriesga
            riesgo_otro+= 0 if mfe_hasta(g,t1[1],t1[2],t1[4],t2[4])>=be*t1[2]/27000 else t1[7]
        if riesgo_otro+t2[7]>5000: sobre+=1
        cap=M0-riesgo_otro
        n=t2[6]; old=t2[1]*(t2[3]-t2[2])/t2[2]*P*2*n
        if cap<500:
            delta+=-old; saltadas+=1; continue
        if cap<t2[7]:
            dist=cap/(2*n*P)*t2[2]   # pts en precio del día
            if mae_desde(g,t2[1],t2[2],t2[4],t2[5])>=dist:
                new=-(cap+2*2*n); delta+=new-old; recortadas+=1
print(f'días {dias} · operaciones que se abren con la otra abierta: {solapes} · con riesgo combinado > $5,000: {sobre}')
print(f'C1 (la 2.ª posición recibe solo el margen que deja la 1.ª): saltadas {saltadas}, cortadas por el stop más cerca {recortadas}')
print(f'resultado base ${base_tot/dias:,.1f}/día · efecto {delta/dias:+.2f} $/día ({delta/base_tot*100:+.1f}%)')
