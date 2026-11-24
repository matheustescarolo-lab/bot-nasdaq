exec(open('mejor_examen.py').read().split("mide('Mañana tal cual',{})")[0])
EXAMEN=90; CROSS=23            # $ examen 50K con código; CrossTrade anual / 12
def n_de(base,k):
    n=max(1,round(base*peso[k]))
    return max(1,round(n*0.5)) if r9.iloc[k]>1.10 else n
def meta_justa(bal):
    falta=3000-bal
    m=min(1550,falta+50) if (bal>0 and falta+50<=bal) else (min(1550,bal) if bal>0 else 1550)
    return max(m,300)
def ciclo(s,H,be,bf):
    gasto=EXAMEN; cobrado=0.0; examenes=1; pagos=0; fondeos=0; primer_fondeo=None; estado='examen'
    bal=alto=mejor=0.0; mll=-2000.0; bloq=False; d150=0; ciclo_g=0.0
    for i,k in enumerate(range(s,min(s+H,len(C)))):
        if estado=='examen':
            r,peor=corre(k,n_de(be,k),meta_justa(bal),None)
        else:
            r,peor=corre(k,n_de(bf,k),None,None)
        if bal+peor<=mll:                                   # quemada (examen o fondeada) → otro examen
            gasto+=EXAMEN; examenes+=1; estado='examen'; bal=alto=mejor=0.0; mll=-2000.0; bloq=False; continue
        bal+=r
        if not bloq:
            alto=max(alto,bal); mll=alto-2000
            if bal>2100: mll=100; bloq=True
        if estado=='examen':
            mejor=max(mejor,r)
            if bal>=3000 and mejor<=0.5*bal:
                estado='fondeada'; fondeos+=1; primer_fondeo=primer_fondeo or i+1
                bal=alto=0.0; mll=-2000.0; bloq=False; d150=0; ciclo_g=0.0
        else:
            d150+= r>=150; ciclo_g+=r
            if d150>=5 and ciclo_g>0 and bal>=1000:
                pago=min(0.5*bal,2000); cobrado+=0.9*pago; bal-=pago; mll=100; bloq=True; pagos+=1; d150=0; ciclo_g=0.0
                if pagos>=5: break                        # pasa a cuenta real
    meses=min(H,len(C)-s)/21
    return cobrado-gasto-CROSS*meses, examenes, pagos, primer_fondeo
V=[('A · Conservadora (examen 3 MNQ)',3),('B · Equilibrada (examen 4 MNQ)',4),('C · Agresiva (examen 6 MNQ, actual)',6)]
for H,nom in ((126,'6 MESES'),(252,'12 MESES')):
    for bf in (1,2):
        print(f'\n===== {nom} · ya fondeada opera con {bf} MNQ base (con capas, sin meta) =====')
        for v,be in V:
            S=list(range(0,len(C)-H,3)); R=[ciclo(s,H,be,bf) for s in S]
            net=np.array([r[0] for r in R]); ex=np.array([r[1] for r in R]); pg=np.array([r[2] for r in R]); pf=[r[3] for r in R if r[3]]
            m=len(net)//2
            print(f"{v:<38} neto mediana ${np.median(net):6,.0f} · promedio ${net.mean():6,.0f} ({net[:m].mean():,.0f}/{net[m:].mean():,.0f}) · gana dinero {np.mean(net>0):4.0%} · peor 10% ${np.percentile(net,10):6,.0f} · exámenes {ex.mean():4.1f} · retiros {pg.mean():.1f} · 1er fondeo día {np.median(pf):.0f} ({len(pf)/len(R):.0%} lo logra)")
