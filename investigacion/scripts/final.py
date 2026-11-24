import os, re, sys, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
G={}; exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0],G); arr=G['arr']; USD=G['USD']
cal=open('calendario.py').read(); FOMC=set(pd.to_datetime(re.search(r'FOMC="""(.*?)"""',cal,re.S).group(1).split()))
def caminos(trs,g,cost):
    c=np.zeros(78); w=np.zeros(78)
    for t in range(78):
        vc=vw=0.0
        for s,e,x,a,b in trs:
            if t>b: r=s*(x-e)*USD-cost; vc+=r; vw+=r
            elif t>=a: vc+=s*(g.c[t]-e)*USD-cost; vw+=s*((g.l[t] if s==1 else g.h[t])-e)*USD-cost
        c[t]=vc; w[t]=vw
    return c,w
K=range(20,len(arr)); fechas=pd.DatetimeIndex([pd.Timestamp(arr[k].d) for k in K]).astype('datetime64[ns]')
P={}
for nom,co,cr in (('ideal',2,2),('real_mercado',10,4),('real',3,4)):
    Co=[];Wo=[];Cr=[];Wr=[]
    for k in K:
        g=arr[k]; hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        to=[] if pd.Timestamp(g.d) in FOMC else G['orb_t'](g)
        a,b=caminos(to,g,co); Co.append(a); Wo.append(b); a,b=caminos(G['ruido_t'](g,hist,arr[k-1].c[-1]),g,cr); Cr.append(a); Wr.append(b)
    P[nom]=tuple(np.array(x) for x in (Co,Wo,Cr,Wr))
W=pd.read_pickle('todo_pesos.pkl'); W.index=W.index.astype('datetime64[ns]'); W=W.reindex(fechas)
ret1=np.array([arr[k-1].c[-1]/arr[k-2].c[-1]-1 for k in K]); pay=np.array([(arr[k-1].c[-1]-arr[k-1].l.min())/max(arr[k-1].h.max()-arr[k-1].l.min(),1e-9) for k in K])
np.savez('final_caminos.npz',fechas=fechas.values,ret1=ret1,pay=pay,**{f'{n}_{i}':P[n][i] for n in P for i in range(4)})
print('listo',len(fechas),'días')
