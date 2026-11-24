import pandas as pd, numpy as np
h=pd.read_csv('/home/claude/bot-nasdaq/historia_nas_dukascopy.csv',parse_dates=['ny']).set_index('ny')
h=h[(h.index.time>=pd.Timestamp('09:30').time())&(h.index.time<pd.Timestamp('16:00').time())]
USD=2.0; COSTO=2.0  # puntos por ida y vuelta
def prueba(tf, intradia=True):
    b=h.resample(f'{tf}min',origin='start_day',offset='30min' if tf>=60 else '0min').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    b=b[(b.index.time>=pd.Timestamp('09:30').time())&(b.index.time<pd.Timestamp('16:00').time())]
    c=b.close; e4,e8,e16=(c.ewm(span=n,adjust=False).mean() for n in (4,8,16))
    arriba=(e4>e8)&(e4>e16); abajo=(e4<e8)&(e4<e16)
    sig=pd.Series(np.where(arriba,1,np.where(abajo,-1,np.nan)),index=b.index).ffill().fillna(0)
    pos=sig.shift(1).fillna(0)                       # señal al cierre de la vela, entra en la siguiente (sin ver el futuro)
    dia=pd.Series(b.index.date,index=b.index)
    ultima=dia!=dia.shift(-1)
    if intradia:
        primera=dia!=dia.shift(1)
        pos[primera]=0                                # no lleva posición de la noche: reabre con la señal vigente
        pos=pos.where(~primera, 0)
    ret=(b.open.shift(-1)-b.open).fillna(0)          # de apertura a apertura de la siguiente vela
    ret[ultima]=(b.close-b.open)[ultima]             # última vela: cierra al cierre del día
    pnl=pos*ret*USD
    cambios=(pos.diff().abs().fillna(pos.abs()))
    pnl-=cambios*COSTO/2*USD                          # medio costo por cada lado
    pd_dia=pnl.groupby(dia).sum()
    n=len(pd_dia); m=pd_dia.mean(); t=m/pd_dia.std()*np.sqrt(n); mitad=n//2
    trades=cambios.sum()/2
    return f"{tf:>3} min: ${m:6.1f}/día · t {t:5.2f} · mitades ${pd_dia.iloc[:mitad].mean():6.1f} / ${pd_dia.iloc[mitad:].mean():6.1f} · operaciones/día {trades/n:4.1f} · días que gana {np.mean(pd_dia>0):.0%}"
for tf in (5,15,30,60): print('cruce EMA 4 sobre 8 y 16, solo de día, 1 MNQ, costo 2 pts:',prueba(tf))
# como filtro del ORB: ¿la alineación de EMAs a las 10:00 predice el resultado del ORB?
import sys
