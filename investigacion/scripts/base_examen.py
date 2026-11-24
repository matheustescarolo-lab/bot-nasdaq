exec(open('manana_examen.py').read().split("resumen('Antes")[0])
def n_dia(k, regla):
    base,vol_on=regla
    n=max(1,round(base*peso[k])) if vol_on else base
    if vol_on and r9.iloc[k]>1.10: n=max(1,round(n*0.5))
    return n
for base in (6,7,8,9):
    for vol_on in (False,True):
        R=[examen(range(s,min(s+60,len(C))),(base,vol_on)) for s in range(len(C)-60)]
        p=np.mean([r=='pasa' for r,d in R]); dpi=np.mean([d for r,d in R])
        print(f"base {base} MNQ {'con capas' if vol_on else 'fijo     '}: pasa {p:.0%} · {dpi:.1f} días/intento · ~{dpi/p:.0f} días hábiles y {1/p:.1f} exámenes hasta fondearse (promedio)")
