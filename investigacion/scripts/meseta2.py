exec(open('meseta.py').read().split("D=arr[20:]")[0])
D=arr[20:]; m=len(D)//2; sh=lambda a: a.mean()/a.std()*np.sqrt(252)
for f in (1.0,1.25,1.5):
    for tp in (3,4,None):
        z=np.array([orb_p(g,f,tp) or 0.0 for g in D])
        print(f"stop {f}× rango, objetivo {tp}: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z[:m]):.2f}/{sh(z[m:]):.2f}) · peor día {z.min():,.0f}")
for be in (100,150,200,300,None):
    z=np.array([orb_p(g,1.0,None,be if be else 1e9) or 0.0 for g in D])
    print(f"break even en +{be}: ${z.mean():5.1f}/día · Sharpe {sh(z):.2f} ({sh(z[:m]):.2f}/{sh(z[m:]):.2f})")
