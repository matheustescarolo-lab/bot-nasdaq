exec(open('mejor_examen.py').read().split("mide('Mañana tal cual',{})")[0])
for b in (1,2,3,4,6):
    ch=[]; ex=[]
    for s in range(0,len(C)-500,5):
        k=s; n=0
        while k<len(C)-300:
            r,dd=examen2(range(k,k+300),{'base':b,'meta_din':1}); n+=1; k+=dd
            if r=='pasa': ch.append(k-s); ex.append(n); break
    ch=np.array(ch); ex=np.array(ex)
    print(f"base {b}: fondeado en mediana {np.median(ch):3.0f} días hábiles (25-75%: {np.percentile(ch,25):.0f}-{np.percentile(ch,75):.0f}; peor 10%: {np.percentile(ch,90):.0f}) · exámenes mediana {np.median(ex):.0f}, promedio {ex.mean():.1f} · pasa al 1º {np.mean(ex==1):.0%} · costo prom. ${ex.mean()*90:,.0f}")
