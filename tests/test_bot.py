"""Pruebas unitarias sin necesidad de MetaTrader 5 (corren en Linux/Windows en cada push)."""
import datetime as dt
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

# Mock de MetaTrader5 para poder importar bot_nasdaq en Linux/CI sin terminal instalado
if 'MetaTrader5' not in sys.modules:
    mt5_mock = types.ModuleType('MetaTrader5')
    mt5_mock.ORDER_FILLING_FOK = 0
    mt5_mock.ORDER_FILLING_IOC = 1
    mt5_mock.ORDER_FILLING_RETURN = 2
    mt5_mock.ORDER_TYPE_BUY = 0
    mt5_mock.ORDER_TYPE_SELL = 1
    mt5_mock.ORDER_TYPE_BUY_STOP = 4
    mt5_mock.ORDER_TYPE_SELL_STOP = 5
    mt5_mock.ORDER_TIME_GTC = 0
    mt5_mock.ORDER_TIME_DAY = 1
    mt5_mock.TRADE_ACTION_DEAL = 1
    mt5_mock.TRADE_ACTION_PENDING = 5
    mt5_mock.TRADE_ACTION_SLTP = 6
    mt5_mock.TRADE_ACTION_REMOVE = 8
    mt5_mock.TRADE_RETCODE_DONE = 10009
    mt5_mock.POSITION_TYPE_BUY = 0
    mt5_mock.POSITION_TYPE_SELL = 1
    mt5_mock.DEAL_ENTRY_IN = 0
    mt5_mock.DEAL_ENTRY_OUT = 1
    mt5_mock.DEAL_REASON_SL = 4
    mt5_mock.DEAL_REASON_TP = 5
    mt5_mock.DEAL_REASON_SO = 6
    mt5_mock.DEAL_TYPE_BUY = 0
    mt5_mock.DEAL_TYPE_SELL = 1
    mt5_mock.ACCOUNT_TRADE_MODE_DEMO = 0
    sys.modules['MetaTrader5'] = mt5_mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import estrategias
import contexto
import bot_nasdaq


class TestEstrategias(unittest.TestCase):
    def _dia(self, fecha, precios, vol=100):
        idx = pd.date_range(f'{fecha} 09:30', periods=len(precios), freq='5min')
        return pd.DataFrame({
            'o': [p[0] for p in precios],
            'h': [p[1] for p in precios],
            'l': [p[2] for p in precios],
            'c': [p[3] for p in precios],
            'v': [vol] * len(precios),
        }, index=idx)

    def test_piso_usd(self):
        self.assertIsNone(estrategias.piso_usd('orb', 149.9))
        self.assertEqual(estrategias.piso_usd('orb', 150.0), 0.0)
        self.assertIsNone(estrategias.piso_usd('ruido', 199.9))
        self.assertEqual(estrategias.piso_usd('ruido', 200.0), 100.0)
        self.assertEqual(estrategias.piso_usd('ruido', 299.0), 100.0)
        self.assertEqual(estrategias.piso_usd('ruido', 300.0), 200.0)
        self.assertEqual(estrategias.piso_usd('ruido', 407.0), 300.0)

    def test_modelo_orb_breakout_y_stop(self):
        # 6 velas ORB: hi=110, lo=100
        velas = [(105, 110, 100, 105)] * 6
        # Vela 10:00 rompe arriba (112) sin tocar stop
        velas.append((105, 112, 104, 111))
        df = self._dia('2026-11-20', velas)
        hi, lo = estrategias.niveles_orb(df)
        self.assertEqual((hi, lo), (110.0, 100.0))
        self.assertEqual(estrategias.modelo_orb(df, hi, lo), (1, 'activo'))
        # Siguiente vela toca stop (99)
        velas.append((111, 111, 99, 100))
        df2 = self._dia('2026-11-20', velas)
        self.assertEqual(estrategias.modelo_orb(df2, hi, lo), (1, 'stop'))

    def test_modelo_ruido_volumen_cero_no_rompe_vwap(self):
        previos = [self._dia(f'2026-11-{d:02d}', [(100, 101, 99, 100)] * 78) for d in range(1, 16)]
        hoy = self._dia('2026-11-20', [(100, 100.5, 99.5, 100)] * 12, vol=0)
        pos, info, _ = estrategias.modelo_ruido(hoy, previos, 100.0, dt.datetime(2026, 11, 20, 10, 35))
        self.assertEqual(pos, 0)
        self.assertIn('VWAP 100.00', info)


class TestContexto(unittest.TestCase):
    def test_palabras_mercado_sin_falsos_positivos(self):
        post_deportes = "Congratulations to Anderson University! She was awarded Tournament MVP."
        self.assertIsNone(contexto.PALABRAS_MERCADO.search(post_deportes))
        post_aranceles = "New tariffs on China semiconductors announced today."
        self.assertIsNotNone(contexto.PALABRAS_MERCADO.search(post_aranceles))
        post_fed = "Powell and the Fed keep interest rates steady."
        self.assertIsNotNone(contexto.PALABRAS_MERCADO.search(post_fed))
        post_palabra_parcial = "Great corporate strategy and ideal software syntax!"
        self.assertIsNone(contexto.PALABRAS_MERCADO.search(post_palabra_parcial))


class TestBotLogica(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path('/tmp/test_bot_nasdaq_unit')
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._orig_estado = bot_nasdaq.ESTADO
        self._orig_bit = bot_nasdaq.BITACORA
        bot_nasdaq.ESTADO = str(self.tmp_dir / 'estado_test.json')
        bot_nasdaq.BITACORA = str(self.tmp_dir / 'bitacora_test.csv')
        for p in (bot_nasdaq.ESTADO, bot_nasdaq.BITACORA):
            if Path(p).exists():
                Path(p).unlink()

    def tearDown(self):
        bot_nasdaq.ESTADO = self._orig_estado
        bot_nasdaq.BITACORA = self._orig_bit

    def test_guardar_estado_atomico(self):
        bot_nasdaq.guardar_estado({'ok': 123})
        self.assertEqual(bot_nasdaq.leer_estado(), {'ok': 123})
        self.assertFalse(Path(bot_nasdaq.ESTADO + '.tmp').exists())

    def test_ftmo_cierre_no_suma_dia_sin_operaciones(self):
        bot_nasdaq.guardar_estado({
            'ftmo': {'fase': 1, 'inicio': '2026-11-19', 'base': 100000.0, 'cierre_prev': 100000.0,
                     'dias': 1, 'listo': False, 'login': 999, 'etapa': 'reto'},
            'dia': {'fecha': '2026-11-20', 'quemado': False}
        })
        bot_nasdaq.FTMO_INICIAL = 100000.0
        bot_nasdaq.ETAPA = 'reto'
        bot_nasdaq.ftmo_cierre(100000.0, dt.date(2026, 11, 20), opero=False)
        est = bot_nasdaq.leer_estado()
        self.assertEqual(est['ftmo']['dias'], 1)
        bot_nasdaq.ftmo_cierre(101000.0, dt.date(2026, 11, 21), opero=True)
        est2 = bot_nasdaq.leer_estado()
        self.assertEqual(est2['ftmo']['dias'], 2)

    def test_hubo_operaciones_error_devuelve_false(self):
        bot_nasdaq.mt5.history_deals_get = MagicMock(side_effect=RuntimeError('desconectado'))
        # Sin entradas en bitacora -> debe devolver False (antes devolvia True!)
        self.assertFalse(bot_nasdaq.hubo_operaciones(dt.date(2026, 11, 20)))

    def test_sincronizar_repone_orden_pendiente_faltante(self):
        # Si ya existe BUY_STOP pero falta SELL_STOP, debe poner SOLO la SELL_STOP
        bot_nasdaq.DESFASE = 7 * 3600
        bot_nasdaq.CONTEXTO = {}
        idx = pd.date_range('2026-11-20 09:30', periods=7, freq='5min')
        df = pd.DataFrame({'o': [105]*7, 'h': [110]*6 + [107], 'l': [100]*6 + [103], 'c': [105]*7, 'v': [100]*7}, index=idx)
        prev = pd.DataFrame({'o': [105]*78, 'h': [110]*78, 'l': [100]*78, 'c': [105]*78, 'v': [100]*78},
                            index=pd.date_range('2026-11-19 09:30', periods=78, freq='5min'))
        full_df = pd.concat([prev, df])

        buy_order = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.ORDER_TYPE_BUY_STOP, ticket=1)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[buy_order])
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=types.SimpleNamespace(point=0.01, digits=2, trade_stops_level=10))
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(ask=105.5, bid=105.0))
        enviadas = []
        orig_poner = bot_nasdaq.poner_pendiente
        bot_nasdaq.poner_pendiente = lambda sym, clave, lado, *a, **kw: enviadas.append(lado) or True
        try:
            bot_nasdaq.sincronizar('USTEC', full_df, dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 10, 5), {'orb': 2.0, 'ruido': 2.0})
        finally:
            bot_nasdaq.poner_pendiente = orig_poner
        self.assertEqual(enviadas, [-1])

    def test_activo_no_duplica_si_la_pendiente_se_lleno_al_cancelar(self):
        # El precio rompió el rango (modelo «activo») con una BUY STOP todavía viva: el bot la cancela, pero si en ese
        # instante se llenó (ya hay posición), NO debe entrar otra vez a mercado.
        bot_nasdaq.DESFASE = 7 * 3600
        bot_nasdaq.CONTEXTO = {}
        idx = pd.date_range('2026-11-20 09:30', periods=7, freq='5min')
        df = pd.DataFrame({'o': [105]*7, 'h': [110]*6 + [111], 'l': [100]*6 + [104], 'c': [105]*6 + [110.5], 'v': [100]*7}, index=idx)
        prev = pd.DataFrame({'o': [105]*78, 'h': [110]*78, 'l': [100]*78, 'c': [105]*78, 'v': [100]*78},
                            index=pd.date_range('2026-11-19 09:30', periods=78, freq='5min'))
        full_df = pd.concat([prev, df])
        buy_order = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.ORDER_TYPE_BUY_STOP, ticket=1,
                                          volume_current=2.0, price_open=110.01)
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.POSITION_TYPE_BUY, ticket=9, volume=2.0,
                                    price_open=110.01, sl=100.0, tp=0.0, time=0)
        llamadas = {'n': 0}
        def posiciones(**kw):
            llamadas['n'] += 1
            return [] if llamadas['n'] == 1 else [pos]       # vacío al principio; lleno después de cancelar
        bot_nasdaq.mt5.positions_get = MagicMock(side_effect=posiciones)
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[buy_order])
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        abiertas = []
        orig = (bot_nasdaq.cancelar_pendientes, bot_nasdaq.abrir)
        bot_nasdaq.cancelar_pendientes = lambda *a, **k: None
        bot_nasdaq.abrir = lambda *a, **k: abiertas.append(a)
        try:
            bot_nasdaq.sincronizar('USTEC', full_df, dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 10, 6), {'orb': 2.0, 'ruido': 2.0})
        finally:
            bot_nasdaq.cancelar_pendientes, bot_nasdaq.abrir = orig
        self.assertEqual(abiertas, [])

    def test_ftmo_listo_revierte_si_baja_de_meta(self):
        bot_nasdaq.FTMO_INICIAL = 100000.0
        orig_etapa = bot_nasdaq.ETAPA
        bot_nasdaq.ETAPA = 'fase1'
        try:
            bot_nasdaq.guardar_estado({'ftmo': {'fase': 1, 'inicio': '2026-11-19', 'base': 100000.0, 'cierre_prev': 100000.0,
                                                'dias': 1, 'listo': False, 'login': 999, 'etapa': 'fase1'}})
            bot_nasdaq.ftmo_cierre(110050.0, dt.date(2026, 11, 23), opero=True)
            f = bot_nasdaq.leer_estado()['ftmo']
            self.assertTrue(f['listo']); self.assertEqual(f['dias'], 2); self.assertFalse(f.get('aprobada'))
            bot_nasdaq.ftmo_cierre(109650.0, dt.date(2026, 11, 24), opero=True)
            f = bot_nasdaq.leer_estado()['ftmo']
            self.assertFalse(f['listo']); self.assertEqual(f['dias'], 3)
            bot_nasdaq.ftmo_cierre(109750.0, dt.date(2026, 11, 25), opero=True)
            f = bot_nasdaq.leer_estado()['ftmo']
            self.assertEqual(f['dias'], 4); self.assertFalse(f['listo']); self.assertFalse(f.get('aprobada'))
            bot_nasdaq.ftmo_cierre(110050.0, dt.date(2026, 11, 27), opero=True)
            f = bot_nasdaq.leer_estado()['ftmo']
            self.assertTrue(f['listo']); self.assertEqual(f['dias'], 5); self.assertTrue(f.get('aprobada'))
        finally:
            bot_nasdaq.ETAPA = orig_etapa

    def _margen(self, margin_free, m1, equity=100000.0, ordenes=(), posiciones=(), modo='lucid'):
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(margin_free=margin_free, equity=equity))
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=types.SimpleNamespace(
            volume_step=0.01, volume_min=0.01, trade_tick_value=0.01, trade_tick_size=0.01))   # 1 lote = US$1 por punto
        bot_nasdaq.mt5.order_calc_margin = MagicMock(return_value=m1)
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=list(ordenes))
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=list(posiciones))
        self._modo = bot_nasdaq.MODO
        bot_nasdaq.MODO = modo
        self.addCleanup(setattr, bot_nasdaq, 'MODO', self._modo)

    def test_lotes_por_margen_sobrado_no_recorta(self):
        self._margen(100000, 1800)
        self.assertEqual(bot_nasdaq.lotes_por_margen('USTEC', 1, 24.0, 27000.0, 'orb'), 24.0)

    def test_lotes_por_margen_recorta_en_drawdown(self):
        self._margen(47800, 1800)
        self.assertAlmostEqual(bot_nasdaq.lotes_por_margen('USTEC', 1, 24.0, 27000.0, 'orb'), 22.57)

    def test_lotes_por_margen_insuficiente_devuelve_cero(self):
        self._margen(10, 1800)
        self.assertEqual(bot_nasdaq.lotes_por_margen('USTEC', -1, 12.0, 27000.0, 'ruido'), 0.0)

    def test_lotes_por_margen_emula_ftmo_swing_en_tickmill(self):
        # Tickmill (1:100) sí tendría margen, pero FTMO Swing (1:15) sobre la cuenta virtual de 100K en −2,000 no:
        # 27,000 × $1 / 15 = $1,800 por lote; (98,000 × 0.85) / 1,800 = 46.27 lotes
        bot_nasdaq.guardar_estado({'ftmo': {'fase': 1, 'base': 48491.10}})
        self._margen(40000, 270, equity=46491.10, modo='ftmo')
        self.assertAlmostEqual(bot_nasdaq.lotes_por_margen('USTEC', 1, 48.0, 27000.0, 'ruido'), 46.27)
        self.assertEqual(bot_nasdaq.lotes_por_margen('USTEC', 1, 24.0, 27000.0, 'ruido'), 24.0)

    def test_lotes_por_margen_aparta_pendientes_de_la_otra_estrategia(self):
        # Pendientes del rango (24 lotes por lado; solo una se llena) apartan 24 × 1,800 = 43,200 del margen de la zona de ruido
        orb = [types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], volume_current=24.0) for _ in range(2)]
        self._margen(100000, 1800, ordenes=orb)
        self.assertAlmostEqual(bot_nasdaq.lotes_por_margen('USTEC', 1, 30.0, 27000.0, 'ruido'), 26.82)
        self.assertEqual(bot_nasdaq.lotes_por_margen('USTEC', 1, 24.0, 27000.0, 'ruido'), 24.0)

    def test_estado_ftmo_sin_datos_mock(self):
        # Valida que los archivos JSON de estado del repo no tengan login=1 de prueba
        p = ROOT / 'estado_nasdaq_ftmo.json'
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            self.assertNotEqual((data.get('ftmo') or {}).get('login'), 1)


if __name__ == '__main__':
    unittest.main()
