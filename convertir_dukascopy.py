"""Convierte las velas de 5 min de Dukascopy (UTC) a hora de Nueva York y deja solo el horario de bolsa 9:30–16:00."""
import glob, pandas as pd
df = pd.concat(pd.read_csv(f) for f in sorted(glob.glob('datos/*.csv')))
df['ny'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None)
df = df[(df.ny.dt.time >= pd.Timestamp('09:30').time()) & (df.ny.dt.time < pd.Timestamp('16:00').time()) & (df.ny.dt.weekday < 5)]
df = df.drop_duplicates('ny').sort_values('ny')
out = df.rename(columns={'volume': 'tick_volume'})[['ny', 'open', 'high', 'low', 'close', 'tick_volume']]
out['spread'] = 0
out.to_csv('historia_nas_dukascopy.csv', index=False)
print(f'{len(out)} velas · del {out.ny.iloc[0]} al {out.ny.iloc[-1]} · {out.ny.dt.date.nunique()} días')
