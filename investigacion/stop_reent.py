exec(open("stop_seg.py").read().split("BASE=6")[0]); BASE=6; P=27000
def chk(i): fin=(i+1)*5+570; return fin>=600 and fin%30==0
A=[];B=[];F=[]
for k in range(14,len(arr)):
    g=arr[k]; i=idx.get(pd.Timestamp(g.d))
    if i is None or np.isnan(mr[i]): continue
    nr=min(round(BASE*mr[i]),2*BASE)
    if nr==0: continue
    hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
    for s,e,x,a,b in ruido_t(g,hist,arr[k-1].c[-1]):
        X=min(0.01,4500/(2*nr*P))
        base=s*(x-e)/e; tot=0; ee,aa=e,a
        while True:
            hit=None
            for t in range(aa+1,b+1):
                if (e_adv:=((ee-g.l[t])/ee if s==1 else (g.h[t]-ee)/ee))>=X: hit=t; break
            if hit is None: tot+=s*(x-ee)/ee*ee/e; break
            tot+=(-X-2/P)*ee/e
            nxt=[t for t in range(hit,b) if chk(t)]          # re-entra en el siguiente chequeo si el modelo sigue dentro
            if not nxt: break
            aa=nxt[0]; ee=g.c[aa]
        A.append(base*P*2*nr); B.append(tot*P*2*nr); F.append(k)
A=np.array(A);B=np.array(B); dias=1805
print(f'sin tope ${A.sum()/dias:,.1f}/día · tope con re-entrada ${B.sum()/dias:,.1f}/día · efecto {(B-A).sum()/dias:+.2f}/día')
# por mitades y peor día (bot vivo, con re-entrada)
D={}; k0=0
F=np.array(F); h=np.median(F)
for nom,m in (('1.ª mitad',F<=h),('2.ª mitad',F>h)):
    print(f'{nom}: efecto {(B-A)[m].sum()/(dias/2):+.2f}/día')
dA=pd.Series(A).groupby(F).sum(); dB=pd.Series(B).groupby(F).sum()
print(f'peor día zona de ruido: sin tope ${dA.min():,.0f} · con tope y re-entrada ${dB.min():,.0f}')
