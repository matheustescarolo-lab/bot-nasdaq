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
    mt5_mock.TRADE_ACTION_MODIFY = 7
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
        bot_nasdaq._AVISO_MARGEN.clear(); bot_nasdaq._SALIDA_PROT.clear(); bot_nasdaq._SACUDIDA_VISTA.clear()
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
            return [] if llamadas['n'] <= 2 else [pos]       # vacío al principio (guardia de MT5 y posicion); lleno después de cancelar
        bot_nasdaq.mt5.positions_get = MagicMock(side_effect=posiciones)
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[buy_order])
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        abiertas = []
        orig = (bot_nasdaq.cancelar_pendientes, bot_nasdaq.abrir)
        canceladas = []
        bot_nasdaq.cancelar_pendientes = lambda *a, **k: canceladas.append(a[2] if len(a) > 2 else '')
        bot_nasdaq.abrir = lambda *a, **k: abiertas.append(a)
        try:
            bot_nasdaq.sincronizar('USTEC', full_df, dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 10, 6), {'orb': 2.0, 'ruido': 2.0})
        finally:
            bot_nasdaq.cancelar_pendientes, bot_nasdaq.abrir = orig
        self.assertEqual(abiertas, [])
        self.assertTrue(canceladas and "entra a mercado" in canceladas[0])   # sí pasó por la rama «activo»

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

    def test_tope_stop_acerca_el_stop_si_pasa_de_4500(self):
        # 12 lotes de $1/punto (6 MNQ): $4,500 = 375 puntos. Rango de 600 pts -> el stop sube a entrada − 375
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=types.SimpleNamespace(
            trade_tick_value=0.01, trade_tick_size=0.01, digits=2))
        orig = bot_nasdaq.TOPE_POSICION_USD
        bot_nasdaq.TOPE_POSICION_USD = 4500.0
        try:
            self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26400.0), (26625.0, True))
            self.assertEqual(bot_nasdaq.tope_stop('USTEC', -1, 12.0, 27000.0, 27600.0), (27375.0, True))
            # stop ya más cerca que el tope: no se toca
            self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26800.0), (26800.0, False))
            # modo sin tope (Lucid): no se toca
            bot_nasdaq.TOPE_POSICION_USD = None
            self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26400.0), (26400.0, False))
        finally:
            bot_nasdaq.TOPE_POSICION_USD = orig

    def test_pendiente_sale_con_stop_de_seguridad(self):
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=types.SimpleNamespace(
            trade_tick_value=0.01, trade_tick_size=0.01, digits=2, point=0.01, volume_step=0.01, volume_min=0.01, trade_stops_level=0))
        bot_nasdaq.mt5.account_info = MagicMock(return_value=None)       # sin datos de margen: no recorta
        enviadas = []
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        orig = bot_nasdaq.TOPE_POSICION_USD
        bot_nasdaq.TOPE_POSICION_USD = 4500.0
        try:
            self.assertTrue(bot_nasdaq.poner_pendiente('USTEC', 'orb', -1, 12.0, 26999.99, 27600.0, 'prueba'))
        finally:
            bot_nasdaq.TOPE_POSICION_USD = orig
        self.assertEqual(enviadas[0]['sl'], 27374.99)

    # ===== AUDIT_005 =====
    def _info(self, **kw):
        base = dict(trade_tick_value=0.01, trade_tick_size=0.01, digits=2, point=0.01, volume_step=0.01, volume_min=0.01,
                    trade_stops_level=0)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def _con_tope(self, usd=4500.0):
        orig = bot_nasdaq.TOPE_POSICION_USD
        bot_nasdaq.TOPE_POSICION_USD = usd
        self.addCleanup(setattr, bot_nasdaq, 'TOPE_POSICION_USD', orig)

    def test_enviar_no_abre_sin_stop_valido(self):
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info(trade_stops_level=100))   # 1 punto mínimo
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=100.0, ask=100.5))
        bot_nasdaq.mt5.order_send = MagicMock(return_value=types.SimpleNamespace(retcode=10009, price=100.5))
        self.assertIsNone(bot_nasdaq.enviar('USTEC', 1, 2.0, 'ruido', sl=None))
        self.assertIsNone(bot_nasdaq.enviar('USTEC', 1, 2.0, 'ruido', sl=99.5))     # a 0.5 del bid: menos que el mínimo
        self.assertIsNone(bot_nasdaq.enviar('USTEC', -1, 2.0, 'ruido', sl=101.0))   # a 0.5 del ask
        bot_nasdaq.mt5.order_send.assert_not_called()
        self.assertEqual(bot_nasdaq.enviar('USTEC', 1, 2.0, 'ruido', sl=98.0), 100.5)
        self.assertEqual(bot_nasdaq.mt5.order_send.call_args[0][0]['sl'], 98.0)

    def test_abrir_sin_tick_no_envia(self):
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=None)
        bot_nasdaq.mt5.last_error = MagicMock(return_value=(0, ''))
        bot_nasdaq.mt5.order_send = MagicMock()
        bot_nasdaq.abrir('USTEC', 'ruido', 1, 2.0, 99.0, 'prueba')
        bot_nasdaq.mt5.order_send.assert_not_called()

    def test_tope_stop_alinea_al_tick_y_no_arriesga_de_mas(self):
        self._con_tope()
        # tick de 0.25 que vale $0.25 por lote (=$1/punto/lote); 7 lotes → $4,500 = 642.857 pts
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info(trade_tick_value=0.25, trade_tick_size=0.25))
        sl, top = bot_nasdaq.tope_stop('USTEC', 1, 7.0, 27000.0, 26000.0)
        self.assertTrue(top); self.assertEqual(sl % 0.25, 0); self.assertLessEqual((27000.0 - sl) * 7, 4500)
        sl, top = bot_nasdaq.tope_stop('USTEC', -1, 7.0, 27000.0, 28000.0)
        self.assertTrue(top); self.assertEqual(sl % 0.25, 0); self.assertLessEqual((sl - 27000.0) * 7, 4500)

    def test_tope_stop_datos_invalidos_deja_el_stop(self):
        self._con_tope()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info(trade_tick_value=0.0))
        self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26400.0), (26400.0, False))
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        self.assertEqual(bot_nasdaq.tope_stop('USTEC', 0, 12.0, 27000.0, 26400.0), (26400.0, False))
        self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, None), (None, False))
        self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 0, 27000.0, 26400.0), (26400.0, False))

    def test_tope_stop_usa_el_margen_que_queda_antes_del_freno(self):
        self._con_tope()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        modo = bot_nasdaq.MODO; bot_nasdaq.MODO = 'ftmo'; self.addCleanup(setattr, bot_nasdaq, 'MODO', modo)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        bot_nasdaq.guardar_estado({'dia': {'piso': 95000.0}})            # freno en 95,400
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=97400.0, balance=97400.0, margin_free=1e6))
        sl, top = bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26000.0)   # margen $2,000 → 166.67 pts
        self.assertTrue(top); self.assertAlmostEqual(sl, 26833.34, places=2)
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=95700.0, balance=95700.0, margin_free=1e6))
        self.assertEqual(bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26000.0), (None, True))   # $300 < mínimo: no abre

    def test_asegurar_tope_corrige_el_deslizamiento(self):
        self._con_tope()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=26990.0, ask=26990.5))
        # pidió 27,000 con stop 26,625 ($4,500), pero se llenó a 27,040: el stop real arriesga $4,980
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.POSITION_TYPE_BUY, ticket=7, volume=12.0,
                                    price_open=27040.0, sl=26625.0, tp=0.0, time=0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[])
        enviadas = []
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertEqual(len(enviadas), 1)
        self.assertEqual(enviadas[0]['action'], bot_nasdaq.mt5.TRADE_ACTION_SLTP)
        self.assertEqual(enviadas[0]['sl'], 26665.0)
        enviadas.clear(); pos.sl = 26665.0
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertEqual(enviadas, [])                                   # ya cumple: no gasta solicitudes

    def test_cerrar_todo_no_confirma_si_queda_abierta(self):
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['ruido'], type=bot_nasdaq.mt5.POSITION_TYPE_BUY, ticket=9, volume=2.0,
                                    price_open=100.0, sl=99.0, tp=0.0, time=0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=100.0, ask=100.5))
        bot_nasdaq.mt5.order_send = MagicMock(return_value=types.SimpleNamespace(retcode=10004, comment='requote'))
        self.assertFalse(bot_nasdaq.cerrar_todo('USTEC', 'prueba'))
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        self.assertTrue(bot_nasdaq.cerrar_todo('USTEC', 'prueba'))

    def test_colchon_del_freno_crece_con_el_tamano(self):
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=0, ticket=1, volume=24.0, price_open=1, sl=0, tp=0, time=0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        self.assertEqual(bot_nasdaq.colchon_freno('USTEC'), 30 * 24)       # 24 lotes de $1/pt → $720 (> $400)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        self.assertEqual(bot_nasdaq.colchon_freno('USTEC'), bot_nasdaq.FTMO_FRENO * bot_nasdaq.FTMO_INICIAL)

    def test_limite_diario_desde_el_balance_de_medianoche(self):
        bot_nasdaq.FTMO_INICIAL = 100000.0
        e = {'ftmo': {'fase': 1, 'base': 100000.0, 'listo': False}}
        d = bot_nasdaq.ftmo_dia(e, 98000.0, dt.date(2026, 11, 23), ref=100000.0)   # flotante −2,000 al arrancar
        self.assertEqual(d['piso'], 95000.0)

    def test_balance_medianoche_resta_lo_realizado_hoy(self):
        bot_nasdaq.DESFASE = 7 * 3600
        ahora_srv = (dt.datetime.now(bot_nasdaq.NY).replace(tzinfo=None) - dt.datetime(1970, 1, 1)).total_seconds() + 7 * 3600
        hoy = types.SimpleNamespace(time=ahora_srv - 60, type=0, profit=-1500.0, commission=-10.0, swap=0.0, fee=0.0)
        viejo = types.SimpleNamespace(time=ahora_srv - 3 * 86400, type=0, profit=800.0, commission=0.0, swap=0.0, fee=0.0)
        retiro = types.SimpleNamespace(time=ahora_srv - 60, type=2, profit=-5000.0, commission=0.0, swap=0.0, fee=0.0)
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[hoy, viejo, retiro])
        acc = types.SimpleNamespace(balance=98490.0, equity=98490.0)
        self.assertAlmostEqual(bot_nasdaq.balance_medianoche(acc), 100000.0)
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=None)
        orig_sleep = bot_nasdaq.time.sleep; bot_nasdaq.time.sleep = lambda *_: None
        self.addCleanup(setattr, bot_nasdaq.time, 'sleep', orig_sleep)
        # sin historial: lo MÁS ALTO (piso más estricto), también contra el cierre de ayer
        self.assertEqual(bot_nasdaq.balance_medianoche(types.SimpleNamespace(balance=100000.0, equity=98000.0)), 100000.0)
        self.assertEqual(bot_nasdaq.balance_medianoche(types.SimpleNamespace(balance=99000.0, equity=98000.0), 100500.0), 100500.0)

    def test_fondeada_agotada_deja_de_operar(self):
        bot_nasdaq.FTMO_INICIAL = 100000.0
        orig = bot_nasdaq.ETAPA; bot_nasdaq.ETAPA = 'fondeada'; self.addCleanup(setattr, bot_nasdaq, 'ETAPA', orig)
        bot_nasdaq.guardar_estado({'ftmo': {'fase': 1, 'inicio': '2026-11-01', 'base': 100000.0, 'cierre_prev': 91000.0, 'dias': 9,
                                            'listo': False, 'login': 1, 'etapa': 'fondeada'}, 'dia': {}})
        bot_nasdaq.ftmo_cierre(90500.0, dt.date(2026, 11, 23), opero=True)
        self.assertEqual(bot_nasdaq.leer_estado()['ftmo'].get('aprobada'), 'agotado')

    # ===== AUDIT_006 =====
    def _ftmo(self, piso=95000.0):
        modo = bot_nasdaq.MODO; bot_nasdaq.MODO = 'ftmo'; self.addCleanup(setattr, bot_nasdaq, 'MODO', modo)
        bot_nasdaq.guardar_estado({'dia': {'piso': piso}})

    def test_mt5_none_no_es_plano(self):
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=None)
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        self.assertFalse(bot_nasdaq.plano('USTEC'))
        self.assertFalse(bot_nasdaq.cerrar_todo('USTEC', 'prueba'))
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=())
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=None)
        self.assertFalse(bot_nasdaq.plano('USTEC'))
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=())
        self.assertTrue(bot_nasdaq.plano('USTEC'))

    def test_asegurar_tope_cierra_y_cancela_sin_margen(self):
        self._con_tope(); self._ftmo()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=27000.0, ask=27000.5))
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=95700.0, balance=95700.0))  # $300 de margen
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['ruido'], type=0, ticket=3, volume=12.0, price_open=27000.0, sl=26730.0, tp=0.0, time=0)
        orden = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.ORDER_TYPE_BUY_STOP, ticket=4, volume_current=12.0,
                                      price_open=27100.0, sl=26800.0, tp=0.0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[orden])
        cerradas, enviadas = [], []
        orig = bot_nasdaq.cerrar; bot_nasdaq.cerrar = lambda sym, clave, motivo: cerradas.append(clave) or True
        self.addCleanup(setattr, bot_nasdaq, 'cerrar', orig)
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertEqual(cerradas, ['ruido'])
        self.assertEqual([r['action'] for r in enviadas], [bot_nasdaq.mt5.TRADE_ACTION_REMOVE])

    def test_asegurar_tope_acerca_el_stop_de_la_pendiente(self):
        self._con_tope(); self._ftmo()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=27000.0, ask=27000.5))
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=97400.0, balance=97400.0))  # $2,000 realizados de margen
        orden = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.ORDER_TYPE_SELL_STOP, ticket=5, volume_current=12.0,
                                      price_open=26900.0, sl=27300.0, tp=0.0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[orden])
        enviadas = []
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertEqual(enviadas[0]['action'], bot_nasdaq.mt5.TRADE_ACTION_MODIFY)
        self.assertAlmostEqual(enviadas[0]['sl'], 27066.66, places=2)       # 26,900 + 2,000/12

    def test_margen_ftmo_cuenta_el_colchon_con_lo_que_se_va_a_abrir(self):
        self._ftmo()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=0, ticket=1, volume=24.0, price_open=1, sl=0, tp=0, time=0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=96200.0, balance=96200.0))
        # colchón con 24 + 24 lotes = 30 × 48 = $1,440 → margen 96,200 − 96,440 = −240: no deja abrir
        self.assertAlmostEqual(bot_nasdaq.margen_ftmo('USTEC', 24.0), -240.0)
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=96000.0, balance=97000.0))
        self.assertAlmostEqual(bot_nasdaq.margen_ftmo('USTEC'), 96000.0 - 95720.0)                       # lo menor (equity)
        self.assertAlmostEqual(bot_nasdaq.margen_ftmo('USTEC', solo_realizado=True), 97000.0 - 95720.0)  # solo lo cerrado

    def test_poner_pendiente_rechaza_stop_invalido_o_sin_margen(self):
        self._con_tope()
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info(trade_stops_level=500))         # 5 pts mínimo
        bot_nasdaq.mt5.account_info = MagicMock(return_value=None)
        bot_nasdaq.mt5.order_send = MagicMock()
        self.assertFalse(bot_nasdaq.poner_pendiente('USTEC', 'orb', 1, 2.0, 100.0, None, 'x'))
        self.assertFalse(bot_nasdaq.poner_pendiente('USTEC', 'orb', 1, 2.0, 100.0, 97.0, 'x'))          # a 3 pts < 5
        orig = bot_nasdaq.tope_stop; bot_nasdaq.tope_stop = lambda *a, **k: (None, True)
        self.addCleanup(setattr, bot_nasdaq, 'tope_stop', orig)
        self.assertFalse(bot_nasdaq.poner_pendiente('USTEC', 'orb', 1, 2.0, 100.0, 90.0, 'x'))          # sin margen
        bot_nasdaq.mt5.order_send.assert_not_called()

    def test_precios_en_la_rejilla_de_ticks(self):
        info = self._info(trade_tick_size=0.25, trade_tick_value=0.25, bid=27000.0)
        self.assertEqual(bot_nasdaq.alinear(info, 27000.10, True), 27000.25)
        self.assertEqual(bot_nasdaq.alinear(self._info(trade_tick_size=1.0, trade_tick_value=1.0, bid=27000.37), 27000.10, True), 27000.10)
        self.assertEqual(bot_nasdaq.alinear(info, 27000.10, False), 27000.0)
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=info)
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=27000.0, ask=27000.25))
        bot_nasdaq.mt5.order_send = MagicMock(return_value=types.SimpleNamespace(retcode=10009, price=27000.25, order=11))
        bot_nasdaq.enviar('USTEC', 1, 2.0, 'ruido', sl=26730.10)
        self.assertEqual(bot_nasdaq.mt5.order_send.call_args[0][0]['sl'], 26730.25)   # hacia el precio

    def test_guardia_ip_falla_cerrado(self):
        cuenta = bot_nasdaq.CUENTA; bot_nasdaq.CUENTA = 'ftmo'; self.addCleanup(setattr, bot_nasdaq, 'CUENTA', cuenta)
        orig = bot_nasdaq.pais_ip; self.addCleanup(setattr, bot_nasdaq, 'pais_ip', orig)
        for pais in ('US', None):
            bot_nasdaq.pais_ip = lambda p=pais: p
            with self.assertRaises(SystemExit):
                bot_nasdaq.guardia_ip()
        bot_nasdaq.pais_ip = lambda: 'MX'
        bot_nasdaq.guardia_ip()

    # ===== AUDIT_007 =====
    def test_pendiente_se_cancela_con_perdida_flotante_o_colchon_proyectado(self):
        self._con_tope(); self._ftmo(piso=95000.0)
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=27000.0, ask=27000.5))
        ruido = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['ruido'], type=0, ticket=2, volume=24.0, price_open=27100.0, sl=26830.0, tp=0.0, time=0)
        orden = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.ORDER_TYPE_BUY_STOP, ticket=6, volume_current=24.0,
                                      price_open=27150.0, sl=26900.0, tp=0.0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[ruido])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[orden])
        # ruido −$3,800 flotante: balance 100,000, equity 96,200; con 48 lotes el colchón es $1,440 → no hay margen para llenar la pendiente
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=96200.0, balance=100000.0))
        enviadas = []
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertIn(bot_nasdaq.mt5.TRADE_ACTION_REMOVE, [r['action'] for r in enviadas])
        self.assertEqual([r.get('order') for r in enviadas if r['action'] == bot_nasdaq.mt5.TRADE_ACTION_REMOVE], [6])

    def test_pendiente_se_cancela_si_el_stop_no_cabe(self):
        self._con_tope(); self._ftmo(piso=95000.0)
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info(trade_stops_level=10000))     # 100 pts mínimo
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=27000.0, ask=27000.5))
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=96600.0, balance=96600.0))  # margen $1,200 → 50 pts con 24 lotes
        orden = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=bot_nasdaq.mt5.ORDER_TYPE_SELL_STOP, ticket=8, volume_current=24.0,
                                      price_open=26900.0, sl=27300.0, tp=0.0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[orden])
        enviadas = []
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertEqual([r['action'] for r in enviadas], [bot_nasdaq.mt5.TRADE_ACTION_REMOVE])

    def test_sincronizar_no_hace_nada_si_mt5_no_responde(self):
        bot_nasdaq.DESFASE = 7 * 3600
        bot_nasdaq.CONTEXTO = {}
        idx = pd.date_range('2026-11-20 09:30', periods=7, freq='5min')
        df = pd.DataFrame({'o': [105]*7, 'h': [110]*6 + [111], 'l': [100]*6 + [104], 'c': [105]*6 + [110.5], 'v': [100]*7}, index=idx)
        prev = pd.DataFrame({'o': [105]*78, 'h': [110]*78, 'l': [100]*78, 'c': [105]*78, 'v': [100]*78},
                            index=pd.date_range('2026-11-19 09:30', periods=78, freq='5min'))
        full_df = pd.concat([prev, df])
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        hechos = []
        orig = (bot_nasdaq.abrir, bot_nasdaq.poner_pendiente)
        bot_nasdaq.abrir = lambda *a, **k: hechos.append('abrir')
        bot_nasdaq.poner_pendiente = lambda *a, **k: hechos.append('pendiente')
        try:
            for pg, og in ((None, []), ([], None)):
                bot_nasdaq.mt5.positions_get = MagicMock(return_value=pg)
                bot_nasdaq.mt5.orders_get = MagicMock(return_value=og)
                bot_nasdaq.sincronizar('USTEC', full_df, dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 10, 6), {'orb': 2.0, 'ruido': 2.0})
            # con MT5 respondiendo vacío sí entra (control)
            bot_nasdaq.mt5.positions_get = MagicMock(return_value=())
            bot_nasdaq.mt5.orders_get = MagicMock(return_value=())
            bot_nasdaq.sincronizar('USTEC', full_df, dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 10, 6), {'orb': 2.0, 'ruido': 2.0})
        finally:
            bot_nasdaq.abrir, bot_nasdaq.poner_pendiente = orig
        self.assertEqual(hechos, ['abrir'])

    def test_ruido_no_gira_si_no_pudo_cerrar(self):
        bot_nasdaq.DESFASE = 7 * 3600
        bot_nasdaq.CONTEXTO = {}
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['ruido'], type=bot_nasdaq.mt5.POSITION_TYPE_BUY, ticket=5, volume=2.0,
                                    price_open=100.0, sl=99.0, tp=0.0, time=0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        orig = (bot_nasdaq.modelo_ruido, bot_nasdaq.cerrar, bot_nasdaq.abrir, bot_nasdaq.niveles_orb)
        abiertas = []
        bot_nasdaq.modelo_ruido = lambda *a, **k: (-1, 'gira a venta', dt.datetime(2026, 11, 20, 11, 0))
        cerradas = []
        bot_nasdaq.cerrar = lambda *a, **k: cerradas.append(a[1]) or False   # el cierre falla (requote)
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=100.0, ask=100.5))
        bot_nasdaq.abrir = lambda *a, **k: abiertas.append(a)
        bot_nasdaq.niveles_orb = lambda *a, **k: None
        idx = pd.date_range('2026-11-20 09:30', periods=19, freq='5min')
        df = pd.DataFrame({'o': [100]*19, 'h': [101]*19, 'l': [99]*19, 'c': [100]*19, 'v': [100]*19}, index=idx)
        prev = pd.DataFrame({'o': [100]*78, 'h': [101]*78, 'l': [99]*78, 'c': [100]*78, 'v': [100]*78},
                            index=pd.date_range('2026-11-19 09:30', periods=78, freq='5min'))
        try:
            bot_nasdaq.sincronizar('USTEC', pd.concat([prev, df]), dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 11, 1), {'orb': 2.0, 'ruido': 2.0})
        finally:
            bot_nasdaq.modelo_ruido, bot_nasdaq.cerrar, bot_nasdaq.abrir, bot_nasdaq.niveles_orb = orig
        self.assertEqual(abiertas, [])
        self.assertEqual(cerradas, ['ruido'])                          # intentó cerrar y, al fallar, no abrió el lado contrario

    # ===== Auditoría del proyecto (23-nov) =====
    def test_c1_la_segunda_posicion_recibe_lo_que_deja_la_primera(self):
        self._con_tope(); self._ftmo(piso=95000.0)
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=100000.0, balance=100000.0))
        orb = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=0, ticket=1, volume=12.0, price_open=27000.0, sl=26750.0, tp=0.0, time=100)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[orb])        # ORB arriesga 250 pts × 12 = $3,000
        # margen 100,000 − 95,000 − colchón (30 × 24 lotes = 720) = 4,280 → ruido recibe 4,280 − 3,000 = $1,280
        sl, top = bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26730.0)
        self.assertTrue(top); self.assertAlmostEqual((27000.0 - sl) * 12, 1280.0, delta=12)
        orb.sl = 27000.0                                                    # ORB en break even: ya no arriesga
        sl, top = bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26730.0)
        self.assertAlmostEqual((27000.0 - sl) * 12, 3240.0, delta=12)       # vuelve a su stop de 1% ($3,240)
        orb.sl = 26630.0                                                    # ORB arriesga $4,440: la segunda nunca baja de $500
        sl, top = bot_nasdaq.tope_stop('USTEC', 1, 12.0, 27000.0, 26730.0)
        self.assertAlmostEqual((27000.0 - sl) * 12, 500.0, delta=12)

    def test_c1_la_primera_no_se_aprieta_por_la_segunda(self):
        self._con_tope(); self._ftmo(piso=95000.0)
        bot_nasdaq.mt5.symbol_info = MagicMock(return_value=self._info())
        bot_nasdaq.mt5.symbol_info_tick = MagicMock(return_value=types.SimpleNamespace(bid=27000.0, ask=27000.5))
        bot_nasdaq.mt5.account_info = MagicMock(return_value=types.SimpleNamespace(equity=100000.0, balance=100000.0))
        orb = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=0, ticket=1, volume=12.0, price_open=27000.0, sl=26750.0, tp=0.0, time=100)
        ruido = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['ruido'], type=0, ticket=2, volume=12.0, price_open=27000.0, sl=26730.0, tp=0.0, time=200)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[orb, ruido])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[])
        enviadas = []
        bot_nasdaq.mt5.order_send = MagicMock(side_effect=lambda r: enviadas.append(r) or types.SimpleNamespace(retcode=10009))
        bot_nasdaq.asegurar_tope('USTEC')
        self.assertEqual([r['position'] for r in enviadas], [2])            # solo se acerca el stop de la que entró después

    def test_sacudida_revisa_las_velas_que_se_salto(self):
        bot_nasdaq.DESFASE = 7 * 3600
        hoy = dt.date(2026, 11, 20)
        idx = pd.date_range('2026-11-20 10:00', periods=8, freq='5min')
        c = [100, 100.1, 100.2, 99.3, 99.4, 99.5, 99.6, 99.7]                  # la vela de las 10:15 cayó 0.9% (venta en contra de una compra)
        df = pd.DataFrame({'o': c, 'h': c, 'l': c, 'c': c, 'v': [1] * 8}, index=idx)
        entrada = (dt.datetime(2026, 11, 20, 10, 2) - dt.datetime(1970, 1, 1)).total_seconds() + 7 * 3600
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=0, ticket=9, volume=2.0, price_open=100.0, sl=99.0, tp=0.0, time=entrada)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        cerradas = []
        orig = bot_nasdaq.cerrar; bot_nasdaq.cerrar = lambda sym, clave, motivo: cerradas.append(motivo) or True
        self.addCleanup(setattr, bot_nasdaq, 'cerrar', orig)
        bot_nasdaq.sacudida('USTEC', df, hoy)                                  # el bot «despierta» a las 10:40: la de 10:15 sí cuenta
        self.assertEqual(len(cerradas), 1); self.assertIn('10:15', cerradas[0])

    def test_salida_por_proteccion_espera_al_siguiente_chequeo(self):
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        desde = dt.datetime(2026, 11, 20, 11, 0)
        self.assertFalse(bot_nasdaq.salio_por_stop('ruido', desde))
        bot_nasdaq._SALIDA_PROT['ruido'] = dt.datetime(2026, 11, 20, 11, 7)
        self.assertTrue(bot_nasdaq.salio_por_stop('ruido', desde))
        self.assertFalse(bot_nasdaq.salio_por_stop('ruido', dt.datetime(2026, 11, 20, 11, 30)))   # el siguiente chequeo ya no espera

    def test_dias_en_la_rejilla_de_78_velas(self):
        idx = pd.date_range('2026-11-19 09:30', periods=78, freq='5min').delete([10, 11])   # faltan 10:20 y 10:25
        dia = pd.DataFrame({'o': np.arange(76.0), 'h': np.arange(76.0) + 1, 'l': np.arange(76.0) - 1, 'c': np.arange(76.0), 'v': [5] * 76}, index=idx)
        _, previos = bot_nasdaq.partir_dias(dia, dt.date(2026, 11, 20))
        self.assertEqual(len(previos[0]), 78)
        self.assertEqual(previos[0].c.iloc[10], 9.0); self.assertEqual(previos[0].v.iloc[10], 0)     # rellena con el último cierre
        self.assertEqual(previos[0].index[12], pd.Timestamp('2026-11-19 10:30'))

    def test_estado_danado_no_se_lee_como_vacio_en_modo_estricto(self):
        Path(bot_nasdaq.ESTADO).write_text('{roto', encoding='utf-8')
        self.assertEqual(bot_nasdaq.leer_estado(), {})
        with self.assertRaises(bot_nasdaq.EstadoDanado):
            bot_nasdaq.leer_estado(estricto=True)

    def test_login_no_queda_a_la_vista(self):
        self.assertNotIn('25396689', bot_nasdaq.id_cuenta(25396689))
        self.assertEqual(bot_nasdaq.id_cuenta(25396689), bot_nasdaq.id_cuenta('25396689'))
        self.assertEqual(bot_nasdaq.cuenta_txt(25396689), '…689')

    def test_cerrar_viejas_cancela_pendientes_de_ayer(self):
        bot_nasdaq.DESFASE = 7 * 3600
        ayer = (dt.datetime(2026, 11, 19, 15, 0) - dt.datetime(1970, 1, 1)).total_seconds() + 7 * 3600
        o = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['orb'], type=4, ticket=3, volume_current=2.0, price_open=1.0, sl=0.5, time_setup=ayer)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[o])
        canceladas = []
        orig = bot_nasdaq.cancelar_pendientes; bot_nasdaq.cancelar_pendientes = lambda sym, clave, motivo: canceladas.append(clave)
        self.addCleanup(setattr, bot_nasdaq, 'cancelar_pendientes', orig)
        bot_nasdaq.cerrar_viejas('USTEC', dt.date(2026, 11, 20))
        self.assertEqual(canceladas, ['orb'])

    def test_subida_en_vivo_apagada_fuera_de_github(self):
        self.assertFalse(bot_nasdaq.SUBIR_EN_VIVO)
        bot_nasdaq.marcar_subida()
        self.assertIsNone(bot_nasdaq._SUBIDA['hilo'])

    def test_vigia_decide(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import vigia
        NY = vigia.NY
        lun = dt.datetime(2026, 11, 23, 14, 40, tzinfo=NY)
        c = lambda st, con, ini, fin, t='Bot Nasdaq (demo)': dict(status=st, conclusion=con, created_at=ini, updated_at=fin, display_title=t)
        murio = c('completed', 'failure', '2026-11-23T17:40:09Z', '2026-11-23T19:36:02Z')
        self.assertTrue(vigia.decidir(lun, [murio], set(), set())[0])                                   # runner caído → relanza
        self.assertFalse(vigia.decidir(lun, [c('in_progress', None, '2026-11-23T17:40:09Z', '2026-11-23T19:36:02Z')], set(), set())[0])
        self.assertFalse(vigia.decidir(lun, [c('pending', None, '2026-11-23T17:40:09Z', '2026-11-23T17:40:09Z'), murio], set(), set())[0])
        self.assertFalse(vigia.decidir(dt.datetime(2026, 11, 23, 16, 10, tzinfo=NY), [murio], set(), set())[0])   # ya cerró
        self.assertFalse(vigia.decidir(dt.datetime(2026, 11, 26, 11, 0, tzinfo=NY), [], {'2026-11-26'}, set())[0])  # feriado
        self.assertFalse(vigia.decidir(dt.datetime(2026, 11, 27, 12, 50, tzinfo=NY), [], set(), {'2026-11-27'})[0])  # medio día ya cerró
        self.assertTrue(vigia.decidir(dt.datetime(2026, 11, 24, 10, 5, tzinfo=NY), [], set(), set())[0])            # cron-job no disparó
        v = [c('completed', 'failure', f'2026-11-23T1{k}:00:00Z', f'2026-11-23T1{k}:30:00Z', 'Bot Nasdaq (relanzado por el vigia)') for k in range(4)]
        self.assertFalse(vigia.decidir(lun, v, set(), set())[0])                                                   # tope de 4 por día
        rapida = c('completed', 'success', '2026-11-23T19:00:00Z', '2026-11-23T19:02:00Z')
        self.assertFalse(vigia.decidir(lun, [rapida], set(), set())[0])                                          # prueba o el bot decidió no operar

    def test_cero_mnq_no_abre_pero_administra(self):
        bot_nasdaq.DESFASE = 7 * 3600
        bot_nasdaq.CONTEXTO = {}
        pos = types.SimpleNamespace(magic=bot_nasdaq.MAGIC['ruido'], type=bot_nasdaq.mt5.POSITION_TYPE_BUY, ticket=5, volume=2.0,
                                    price_open=100.0, sl=99.0, tp=0.0, time=0)
        bot_nasdaq.mt5.positions_get = MagicMock(return_value=[pos])
        bot_nasdaq.mt5.orders_get = MagicMock(return_value=[])
        bot_nasdaq.mt5.history_deals_get = MagicMock(return_value=[])
        orig = (bot_nasdaq.modelo_ruido, bot_nasdaq.cerrar, bot_nasdaq.abrir, bot_nasdaq.niveles_orb)
        hechos = []
        bot_nasdaq.modelo_ruido = lambda *a, **k: (0, 'volvió a la zona', dt.datetime(2026, 11, 20, 13, 0))
        bot_nasdaq.cerrar = lambda *a, **k: hechos.append(('cerrar', a[1])) or True
        bot_nasdaq.abrir = lambda *a, **k: hechos.append(('abrir', a[1]))
        bot_nasdaq.niveles_orb = lambda *a, **k: None
        idx = pd.date_range('2026-11-20 09:30', periods=43, freq='5min')
        df = pd.DataFrame({'o': [100]*43, 'h': [101]*43, 'l': [99]*43, 'c': [100]*43, 'v': [100]*43}, index=idx)
        prev = pd.DataFrame({'o': [100]*78, 'h': [101]*78, 'l': [99]*78, 'c': [100]*78, 'v': [100]*78},
                            index=pd.date_range('2026-11-19 09:30', periods=78, freq='5min'))
        try:
            bot_nasdaq.sincronizar('USTEC', pd.concat([prev, df]), dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 13, 1), {'orb': 0, 'ruido': 0})
            self.assertEqual(hechos, [('cerrar', 'ruido')])          # con 0 MNQ sigue cerrando lo abierto
            hechos.clear(); bot_nasdaq.mt5.positions_get = MagicMock(return_value=[])
            bot_nasdaq.modelo_ruido = lambda *a, **k: (1, 'arriba de la zona', dt.datetime(2026, 11, 20, 13, 0))
            bot_nasdaq.sincronizar('USTEC', pd.concat([prev, df]), dt.date(2026, 11, 20), dt.datetime(2026, 11, 20, 13, 1), {'orb': 0, 'ruido': 0})
            self.assertEqual(hechos, [])                             # pero no abre
        finally:
            bot_nasdaq.modelo_ruido, bot_nasdaq.cerrar, bot_nasdaq.abrir, bot_nasdaq.niveles_orb = orig

    def test_estado_ftmo_sin_datos_mock(self):
        # Valida que los archivos JSON de estado del repo no tengan login=1 de prueba
        p = ROOT / 'estado_nasdaq_ftmo.json'
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            self.assertNotEqual((data.get('ftmo') or {}).get('login'), 1)


if __name__ == '__main__':
    unittest.main()
