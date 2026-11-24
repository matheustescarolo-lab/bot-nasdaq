import os, numpy as np, pandas as pd
src=open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0]
ARR={}
for nom,f in (('NQ','historia_nas_dukascopy.csv'),('ES','extra/m5_usa500idxusd.csv'),('YM','extra/m5_usa30idxusd.csv'),('ORO','extra/m5_xauusd.csv')):
    os.environ['ARCH']=f; G={}; exec(src,G); ARR[nom]=G['arr']; FN=G
nq={pd.Timestamp(g.d):g.o[0] for g in ARR['NQ']}
R={}
for nom,arr in ARR.items():
    out={}
    for k in range(20,len(arr)):
        g=arr[k]; d=pd.Timestamp(g.d)
        if d not in nq: continue
        FN['USD']=2.0*nq[d]/g.o[0]; FN['COSTO']=FN['USD']*1.0*g.o[0]/nq[d]      # mismo valor nominal que 1 MNQ y mismo costo ($2)
        hist=[np.abs(arr[j].c/arr[j].o[0]-1) for j in range(k-14,k)]
        o=sum(s*(x-e)*FN['USD']-FN['COSTO'] for s,e,x,a,b in FN['orb_t'](g)); r=sum(s*(x-e)*FN['USD']-FN['COSTO'] for s,e,x,a,b in FN['ruido_t'](g,hist,arr[k-1].c[-1]))
        out[d]=(o,r)
    R[nom]=pd.DataFrame(out,index=['orb','ru']).T
    print(nom,len(arr),'días')
pd.to_pickle(R,'div.pkl')
