"""Une los CSV de Dukascopy (UTC) de un instrumento y deja velas de 5 min en hora de NY, 9:30–16:00. Uso: python convertir_generico.py carpeta salida.csv"""
import sys, glob, pandas as pd
df = pd.concat(pd.read_csv(f) for f in sorted(glob.glob(f'{sys.argv[1]}/**/*.csv', recursive=True)))
df['ny'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None)
df = df[(df.ny.dt.time >= pd.Timestamp('09:30').time()) & (df.ny.dt.time < pd.Timestamp('16:00').time()) & (df.ny.dt.weekday < 5)]
df = df.drop_duplicates('ny').sort_values('ny')
out = df.rename(columns={'volume': 'tick_volume'})[['ny', 'open', 'high', 'low', 'close', 'tick_volume']]; out['spread'] = 0
out.to_csv(sys.argv[2], index=False)
print(f'{sys.argv[2]}: {len(out)} velas · {out.ny.dt.date.nunique()} días')
