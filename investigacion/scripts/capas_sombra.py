"""Efecto de pasar a sombra COT, VIX9D, NFP y cierre de ayer (24-nov): bot nuevo vs anterior, $/día por MNQ base y Sharpe."""
import pickle, numpy as np, reglas as R
CB = pickle.load(open('rg_base.pkl', 'rb')); sh = lambda x: x.mean()/x.std()*np.sqrt(252)
for nom, sin in (('anterior (8 capas)', ()), ('nuevo (sombra cot, r9, nfp, pay)', ('cot', 'r9', 'nfp', 'pay'))):
    d, _, _ = R.diario(CB, *R.pesos(sin)); print(f"{nom:34} todo ${d.mean():5.1f} ({sh(d):.2f}) · 2019–22 ${d[R.h1].mean():5.1f} ({sh(d[R.h1]):.2f}) · 2023–26 ${d[R.h2].mean():5.1f} ({sh(d[R.h2]):.2f}) · 2025–26 ${d[R.r2526].mean():5.1f}")
