exec(open('freno_ab.py').read().split("for mit,nom")[0])
sinf=hacer(None); act=hacer(lambda m:max(400,60*m)); c400=hacer(lambda m:400)
def mixto(fond):
    def d(k,base,C,meta,room):
        return (fond if meta is None else sinf)(k,base,C,meta,room)   # en la fondeada meta=None
    return d
for mit,nom in ((False,'pruebas'),(True,'mitad')):
    C=caminos(mit)
    for etq,f in (('reto sin freno · fondeada actual',act),('reto sin freno · fondeada $400',c400)):
        globals()['dia']=mixto(f); print(f"{nom:7} {etq:34}", res(lambda s: dos_pasos(s,C,4)),flush=True)
