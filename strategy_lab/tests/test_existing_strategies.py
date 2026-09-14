import unittest
import ast
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import numpy as np
from unittest.mock import patch
from strategy_lab.existing_signals import source_indicators,spot_signals,future_signals,STRATEGIES
from strategy_lab.existing_engine import Run,simulate,next_future_stop
from strategy_lab.engine import ms
from strategy_lab.signals import HOUR

class ExistingTests(unittest.TestCase):
    def test_source_spot_indicator_and_signal_parity(self):
        rng=np.random.default_rng(77);n=250*6;t=ms('2021-01-01')+np.arange(n)*4*HOUR
        c=100*np.exp(np.cumsum(rng.normal(.0005,.01,n)))
        raw=pd.DataFrame(dict(open_time=t,close_time=t+4*HOUR-1,open=c,high=c*1.01,low=c*.99,close=c,volume=1e6,quote_vol=1e8))
        ours=spot_signals(raw,raw,STRATEGIES['B'])
        current=ours.iloc[[-1]].copy();current['open_time']+=24*HOUR
        source_input=pd.concat([ours,current],ignore_index=True)
        source_input['datetime']=pd.to_datetime(source_input.open_time,unit='ms')
        tree=ast.parse(Path('daily_scanner.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate_signals')
        ns={'pd':pd,'np':np,'config':SimpleNamespace(BB_LEN=20,BB_MULT=1.5,STRATEGY_B_MAX_ROC5=20,STRATEGY_B_MAX_ROC20=40,STRATEGY_B_MAX_ATR_PCT=6)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'source_pure_function','exec'),ns)
        actual=ns['evaluate_signals'](source_input)
        self.assertAlmostEqual(actual['upper_band'],ours.upper.iloc[-1])
        self.assertAlmostEqual(actual['hard_stop_price'],ours.stop_ref.iloc[-1])
        self.assertEqual(bool(actual['entry_b']),bool(ours.signal.iloc[-1]))
        self.assertEqual(bool(actual['exit']),bool(ours.exit_signal.iloc[-1]))
    def test_adverse_move_cannot_activate_breakeven(self):
        p=dict(direction=1,entry=100,atr=5,stop=90,be=False)
        stop,be=next_future_stop(p,dict(close=85,high=90,low=80),STRATEGIES['DON55'],.0005,.0003)
        self.assertFalse(be);self.assertEqual(stop,90)
    def test_2atr_is_1r_and_new_2r_is_4atr(self):
        p=dict(direction=1,entry=100,atr=5,stop=90,be=False)
        bar=dict(close=111,high=112,low=100)
        self.assertTrue(next_future_stop(p,bar,STRATEGIES['DON55'],.0005,.0003)[1])
        self.assertFalse(next_future_stop(p,bar,STRATEGIES['DON55_TREND'],.0005,.0003)[1])
    def test_fee_adjusted_be_short_is_below_entry(self):
        p=dict(direction=-1,entry=100,atr=5,stop=110,be=False)
        stop,be=next_future_stop(p,dict(close=79,high=90,low=79),STRATEGIES['DON55_TREND'],.0005,.0003)
        self.assertTrue(be);self.assertLess(stop,100)
    def test_new_trail_cannot_hit_previous_bar(self):
        start=ms('2024-01-01');t=start+np.arange(8)*HOUR
        raw=pd.DataFrame(dict(open_time=t,open=100.,high=102.,low=99.,close=100.))
        raw.loc[3,['open','high','low','close']]=[100,120,95,110]
        raw.loc[4,['open','high','low','close']]=[110,111,99,101]
        sig=pd.DataFrame([dict(available=start,open_time=start-4*HOUR,close=100,high=102,low=99,atr=5,signal=1,exit_signal=False),
                          dict(available=start+4*HOUR,open_time=start,close=110,high=120,low=95,atr=5,signal=0,exit_signal=False)])
        fund=pd.DataFrame([dict(fundingTime=start,fundingRate=0.,markPrice=100.)])
        tr,eq,meta,_=simulate({'BTCUSDT':raw},{'DON55':{'BTCUSDT':sig}},{'BTCUSDT':fund},{'BTCUSDT':raw},Run(('DON55',),'2024-01-01','2024-01-01T08:00'))
        self.assertEqual(len(tr),1);self.assertGreaterEqual(tr.exit_time.iloc[0],start+5*HOUR)
        self.assertAlmostEqual(meta['metrics']['reconciliation_error'],0,places=8)
    def test_spot_safe_stop_never_loosens(self):
        start=ms('2024-01-01');t=start+np.arange(12)*4*HOUR
        raw=pd.DataFrame(dict(open_time=t,open=100.,high=102.,low=96.,close=100.))
        raw.loc[6,['open','high','low','close']]=[95,96,85,92]
        base=dict(atr=5,close=100,high=102,low=96,roc20=10,exit_signal=False)
        sig=pd.DataFrame([dict(**base,available=start,open_time=start-24*HOUR,signal=1,stop_ref=90),
                          dict(**base,available=start+24*HOUR,open_time=start,signal=0,stop_ref=80)])
        for name,expected in [('B',1),('B_SAFE',0)]:
            tr,eq,meta,_=simulate({'BTCUSDT':raw},{name:{'BTCUSDT':sig}},{},{},Run((name,),'2024-01-01','2024-01-03'))
            self.assertEqual(meta['audit']['loosened_stop_updates'],expected)
            self.assertAlmostEqual(meta['metrics']['reconciliation_error'],0,places=8)
    def test_future_signals_do_not_read_later_funding(self):
        start=ms('2021-01-01');n=1000;t=start+np.arange(n)*HOUR
        c=100+np.sin(np.arange(n)/20)*10+np.arange(n)*.1
        raw=pd.DataFrame(dict(open_time=t,close_time=t+HOUR-1,open=c,high=c+1,low=c-1,close=c,volume=1e6,quote_vol=1e8))
        fund=pd.DataFrame(dict(fundingTime=t[::8],fundingRate=.0001,markPrice=c[::8]))
        before=future_signals(raw,fund,STRATEGIES['DON55']);cut=t[-50]
        changed=fund.copy();changed.loc[changed.fundingTime>=cut,'fundingRate']=.9
        after=future_signals(raw,changed,STRATEGIES['DON55'])
        pd.testing.assert_frame_equal(before[before.open_time<cut],after[after.open_time<cut])

    def test_daily_trend_uses_only_day_known_at_h4_open(self):
        from strategy_lab.signals import resample_bars
        n=230*24;t=ms('2021-01-01')+np.arange(n)*HOUR
        c=100+np.arange(n)*.01
        raw=pd.DataFrame(dict(open_time=t,close_time=t+HOUR-1,open=c,high=c+1,low=c-1,close=c,volume=1e6,quote_vol=1e8))
        fund=pd.DataFrame(dict(fundingTime=t[::8],fundingRate=.0001))
        daily=resample_bars(raw,24)
        before=future_signals(raw,fund,STRATEGIES['DON55_TREND'],daily_bars=daily)
        cut=int(daily.open_time.iloc[-2]);changed=daily.copy()
        changed.loc[changed.open_time>=cut,'close']=10000
        after=future_signals(raw,fund,STRATEGIES['DON55_TREND'],daily_bars=changed)
        pd.testing.assert_frame_equal(before[before.open_time<cut+24*HOUR],after[after.open_time<cut+24*HOUR])

    def test_scanner_insufficient_history_is_not_a_signal(self):
        from strategy_lab.scan_existing import scan_one
        client=SimpleNamespace(bars=lambda *args:pd.DataFrame({'close':[100.]*10}))
        rows=scan_one(client,{'symbol':'NEWUSDT'},'spot',ms('2026-09-07'),None)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['status']=='INSUFFICIENT_HISTORY' and r['signal']==0 for r in rows))

    def test_scanner_does_not_assume_zero_for_missing_funding(self):
        from strategy_lab.scan_existing import scan_one
        client=SimpleNamespace(bars=lambda *args:pd.DataFrame({'close':[100.]*250}))
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:[])
        with patch('strategy_lab.scan_existing.requests.get',return_value=response):
            rows=scan_one(client,{'symbol':'BTCUSDT'},'futures',ms('2026-09-07'),None)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['status']=='DATA_ERROR' and r['signal']==0 for r in rows))

if __name__=='__main__':unittest.main()
