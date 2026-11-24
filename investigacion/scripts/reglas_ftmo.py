"""FTMO 2-Step (4 retos, 12 m, freno actual + agotado 0.8% = el bot) y Sharpe para el bot completo y el bot sin cada regla."""
import pickle, numpy as np
import reglas as R
exec(open('freno_v3.py').read().split("if __name__")[0])
CB = pickle.load(open('rg_base.pkl', 'rb')); V = pickle.load(open('rg_var.pkl', 'rb'))
act = hacer(lambda m: max(400, 60*m), ('reto', 'fond'))
def mitad(C):
    q = 15.0*np.arange(1, 79)/78
    return tuple(x-q/2 for x in C)
def corre(C, mo, mr, nom):
    global MO, MR
    MO, MR = mo, mr
    d, _, _ = R.diario(C, mo, mr); sh = d.mean()/d.std()*np.sqrt(252)
    out = [f"{nom:42} Sharpe {sh:4.2f}"]
    for Cx in (C, mitad(C)):
        A = np.array([dos_pasos3(s, Cx, 4, act, 800) for s in starts]); g = A[:, 0]
        out.append(f"no cobra {np.mean(A[:,1]==0):4.0%} med ${np.median(g)/1e3:5.1f}k")
    print(' · '.join(out), flush=True)
MO0, MR0 = R.pesos()
print('regla quitada → Sharpe · FTMO pruebas · FTMO mitad', flush=True)
corre(CB, MO0, MR0, 'BOT COMPLETO')
for nom, C in V.items():
    if nom.startswith('Ruido stop'):
        corre(C, MO0, MR0, 'con ' + nom.split(' vs')[0])
    else:
        corre(C, MO0, MR0, 'sin ' + nom)
for nom, s in (('Tamaño por volatilidad', 'vol'), ('VIX9D/VIX ×0.5', 'r9'), ('Gigantes ×1.5', 'gig'), ('COT ×0.5', 'cot'), ('NFP ruido ×1.5', 'nfp'),
               ('Filtro de caída', 'caida'), ('Cierre de ayer en su rango', 'pay'), ('Tope 2×', 'tope')):
    mo, mr = R.pesos((s,)); corre(CB, mo, mr, 'sin ' + nom)
