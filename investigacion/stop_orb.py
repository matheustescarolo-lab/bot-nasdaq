exec(open("stop_seg.py").read().split("BASE=6")[0]); BASE=6; P=27000
src=open('orb_real.py').read(); exec(src[src.index('def orb_v'):src.index("Z=dict(")],G); orb_v=G['orb_v']
FOMC=set(pd.to_datetime(re.search(r'FOMC="""(.*?)"""',open('calendario.py').read(),re.S).group(1).split()))
T=[]
for k in range(14,len(arr)):
    g=arr[k]; i=idx.get(pd.Timestamp(g.d))
    if i is None or np.isnan(mo[i]) or pd.Timestamp(g.d) in FOMC: continue
    no=min(round(BASE*mo[i]),2*BASE)
    if no==0: continue
    for s,e,x,a,b in orb_v(g,True,True):
        adv=[(e-g.l[t])/e if s==1 else (g.h[t]-e)/e for t in range(a,b+1)]
        T.append((no,max([0]+adv),s*(x-e)/e))
T=np.array(T); n,mae,res=T.T; dias=len(T)
print(f'ORB: {len(T)} operaciones · ${(res*P*2*n).sum()/len(T):,.0f} por operación (base {BASE}, precio 27,000)')
for B in (3000,4000,4500):
    X=B/(2*n*P); hit=mae>=X; ef=((-X-2/P)-res)[hit]*P*2*n[hit]
    print(f' tope ${B:,}: salta {hit.sum()} ({hit.mean()*100:.1f}%) · efecto {ef.sum():+,.0f} US$ en 8 años ({ef.sum()/len(T):+.2f} por operación)')
