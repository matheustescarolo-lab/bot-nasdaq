exec(open('productos.py').read().split("import sys")[0])
def dia(k,base,C,meta,room):
    Co,Wo,Cr,Wr=C; no=round(base*MO[k]); nr=round(base*MR[k])
    if no+nr==0: return 0.0,False
    c=no*Co[k]+nr*Cr[k]; w=no*Wo[k]+nr*Wr[k]; fr=room-max(400,60*(no+nr))
    for t in range(78):
        if w[t]<=-room: return -room,True          # brecha (salto más allá del límite)
        if w[t]<=-fr: return -fr-2*(no+nr)*2,False  # freno: sale en su nivel + 2 pts de deslizamiento
        if meta is not None and c[t]>=meta: return c[t],False
    return c[-1],False
for mit,nom in ((False,'pruebas'),(True,'mitad')):
    C=caminos(mit); print('==',nom,flush=True)
    print('2-Step 6/4  €439 4 retos', res(lambda s: dos_pasos(s,C,4)),flush=True)
    print('2-Step 4/3  €439 4 retos', res(lambda s: dos_pasos(s,C,4,4,3)),flush=True)
    for bc,bf in ((2,2),(3,2),(3,3),(4,3)):
        print(f'1-Step {bc}/{bf} €399 4 retos', res(lambda s: un_paso(s,C,4,bc,bf,fee=399)),flush=True)
    for bf in (2,3):
        print(f'Instant {bf}   €2,999 1 cta', res(lambda s: instant(s,C,1,bf)),flush=True)
