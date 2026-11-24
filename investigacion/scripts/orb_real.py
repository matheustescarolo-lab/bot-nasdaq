import os, re, numpy as np, pandas as pd
os.environ['ARCH']='historia_nas_dukascopy.csv'
G={}; exec(open('agresivo.py').read().split("D_orb=[]; D_ru=[]")[0],G); arr=G['arr']; USD=G['USD']; CIERRE=G['CIERRE']; gestiona=G['gestiona']
exec(open('final.py').read().split("K=range")[0].split("def caminos")[1].join(["def caminos",""]) if False else "")
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
def orb_v(g, ambos_pierde, sacudida):
    o,h,l,c=g.o,g.h,g.l,g.c; hi,lo=h[:6].max(),l[:6].min()
    for i in range(6,CIERRE+1):
        up,dn=h[i]>hi,l[i]<lo
        if up and dn:
            if not ambos_pierde: return []
            s=1 if abs(o[i]-hi)<=abs(o[i]-lo) else -1      # primero el lado más cercano a la apertura de la vela
            e=max(hi,o[i]) if s==1 else min(lo,o[i]); st=lo if s==1 else hi
            return [(s,e,st,i,i)]
        if up or dn:
            s=1 if up else -1; st=lo if up else hi; e=max(hi,o[i]) if up else min(lo,o[i])
            if (s==1 and c[i]<=st) or (s==-1 and c[i]>=st): return [(s,e,st,i,i)]
            if sacudida and i>0 and s*(c[i]/c[i-1]-1) < -0.006: return [(s,e,c[i],i,i)]
            maxp=max(0,(c[i]-e)*s*USD)
            for j in range(i+1,CIERRE+1):
                x,maxp=gestiona(s,e,j,g,st,None,dict(tipo='be',activa=150),maxp)
                if x is not None: return [(s,e,x,i,j)]
                if sacudida and s*(c[j]/c[j-1]-1) < -0.006: return [(s,e,c[j],i,j)]
            return [(s,e,c[CIERRE],i,CIERRE)]
    return []
Z=dict(np.load('final_caminos.npz',allow_pickle=True))
K=range(20,len(arr))
nambos=0
for tag,amb,sac in (('ambos',True,False),('sac',False,True),('ambos_sac',True,True)):
    Co=[];Wo=[]
    for k in K:
        g=arr[k]
        to=[] if pd.Timestamp(g.d) in FOMC else orb_v(g,amb,sac)
        a,b=caminos(to,g,3); Co.append(a); Wo.append(b)
    Z[f'{tag}_0']=np.array(Co); Z[f'{tag}_1']=np.array(Wo); Z[f'{tag}_2']=Z['real_2']; Z[f'{tag}_3']=Z['real_3']
    print(tag,'ORB $/día 1 MNQ sin capas:',round(np.array(Co)[:,-1].mean(),2),flush=True)
print('real ORB $/día:',round(Z['real_0'][:,-1].mean(),2))
# días con vela que rompe los dos lados
cnt=0
for k in K:
    g=arr[k]; hi,lo=g.h[:6].max(),g.l[:6].min()
    for i in range(6,CIERRE+1):
        up,dn=g.h[i]>hi,g.l[i]<lo
        if up or dn: cnt+= (up and dn); break
print('días "ambos":',cnt,'de',len(K))
np.savez('final_caminos2.npz',**Z)
