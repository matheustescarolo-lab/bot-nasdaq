exec(open('bt2.py').read().split("print('RANGO 30 MIN")[0])
print('Vecinos (para ver si la mejora es estable o suerte):')
for a in (100, 150, 200, 300, 400): corre(f'ORB · break even al ir +${a}', lambda g,h,p,a=a: orb_g(g, regla=dict(tipo='be', activa=a)))
for a in (150, 200, 300, 400): corre(f'Ruido · escalera desde +${a}', lambda g,h,p,a=a: ruido_g(g,h,p,regla=dict(tipo='escalera', activa=a)))
