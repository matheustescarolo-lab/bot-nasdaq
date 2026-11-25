"""Baja toda la historia de velas de 5 min de USTEC que dé el servidor (solo horario de bolsa 9:30–16:00 NY) a historia_ustec_m5.csv.
No opera. Lo usa el flujo «Exportar historia»."""
import os, sys, datetime as dt
import pandas as pd
import MetaTrader5 as mt5
import bot_nasdaq as b

if not b.iniciar() or mt5.account_info() is None:
    print(f'No pude conectar ({mt5.last_error()})'); sys.exit(1)
sym = b.buscar_simbolo(); b.calcular_desfase(sym)
fin = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
partes, desde = [], dt.datetime(2019, 1, 1, tzinfo=dt.timezone.utc)
while desde < fin:
    hasta = min(desde + dt.timedelta(days=90), fin)
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, desde, hasta)
    if r is not None and len(r):
        partes.append(pd.DataFrame(r))
    desde = hasta
df = pd.concat(partes).drop_duplicates('time').sort_values('time')
df['ny'] = [b.a_ny(t) for t in df['time']]
if os.environ.get('MADRUGADA') == 'true':      # estudio de Londres: solo 2:00–9:30 NY
    df = df[(df.ny.dt.time >= dt.time(2, 0)) & (df.ny.dt.time < dt.time(9, 30)) & (df.ny.dt.weekday < 5)]
    destino = os.path.join(b.HERE, 'extra', 'ustec_m5_madrugada.csv')
else:
    df = df[(df.ny.dt.time >= dt.time(9, 30)) & (df.ny.dt.time < dt.time(16, 0))]
    destino = os.path.join(b.HERE, 'historia_ustec_m5.csv')
out = df[['ny', 'open', 'high', 'low', 'close', 'tick_volume', 'spread']]
out.to_csv(destino, index=False)
print(f'{len(out)} velas · del {out.ny.iloc[0]} al {out.ny.iloc[-1]} · {out.ny.dt.date.nunique()} días')
mt5.shutdown()
