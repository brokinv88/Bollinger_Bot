import unittest
import numpy as np
import pandas as pd
from strategy_lab.engine import Settings, simulate, metrics, ms, stop_target_fill
from strategy_lab.signals import HOUR, features, resample_bars, rma

def tape(market='futures', direction=1):
    width=HOUR if market=='futures' else 4*HOUR
    start=ms('2024-01-01')-width
    rows=[]
    for i in range(5):
        rows.append(dict(open_time=start+i*width,close_time=start+(i+1)*width-1,
                         open=100.,high=101.,low=99.,close=100.,atr=5.,signal=direction if i==0 else 0,
                         daily_liquidity=1e9,volume=1e6,quote_vol=1e8))
    return pd.DataFrame(rows)

class EngineTests(unittest.TestCase):
    def test_ambiguous_bar_stop_first(self):
        self.assertEqual(stop_target_fill(1,100,130,80,90,120),(90,'STOP'))
        self.assertEqual(stop_target_fill(-1,100,130,80,110,90),(110,'STOP'))
    def test_gap_stop(self):
        self.assertEqual(stop_target_fill(1,80,100,75,90,120),(80,'GAP_STOP'))
        self.assertEqual(stop_target_fill(-1,120,125,90,110,80),(120,'GAP_STOP'))
    def test_known_open_target_precedes_later_stop(self):
        self.assertEqual(stop_target_fill(1,125,130,80,90,120),(120,'GAP_TARGET'))
        self.assertEqual(stop_target_fill(-1,75,120,70,110,80),(80,'GAP_TARGET'))
    def test_strict_rejects_missing_funding(self):
        f=tape()
        with self.assertRaisesRegex(ValueError,'funding'):
            simulate({'BTCUSDT':f},{},Settings('futures',start='2024-01-01',end='2024-01-01T04:00'))
    def test_strict_rejects_nonfinite_funding(self):
        f=tape()
        fund=pd.DataFrame([dict(fundingTime=ms('2024-01-01'),fundingRate=float('nan'),markPrice=100)])
        with self.assertRaisesRegex(ValueError,'funding'):
            simulate({'BTCUSDT':f},{'BTCUSDT':fund},Settings('futures',start='2024-01-01',end='2024-01-01T04:00'))
    def test_next_open_and_adverse_slip(self):
        f=tape();f.loc[1,'open']=105
        t,e,m=simulate({'BTCUSDT':f},{},Settings('futures',start='2024-01-01',end='2024-01-02',strict_data=False))
        self.assertAlmostEqual(t.iloc[0].entry,105*1.0003)
        self.assertEqual(t.iloc[0].entry_time,ms('2024-01-01'))
    def test_reconciliation_both_markets(self):
        for market in ('spot','futures'):
            f=tape(market)
            t,e,m=simulate({'BTCUSDT':f},{},Settings(market,start='2024-01-01',end='2024-01-02',strict_data=False))
            self.assertAlmostEqual(metrics(t,e,3000 if market=='spot' else 1000)['reconciliation_error'],0,places=8)
    def test_funding_entry_boundary_and_sign(self):
        for direction in (1,-1):
            f=tape(direction=direction)
            funding=pd.DataFrame([dict(fundingTime=ms('2024-01-01'),fundingRate=.1,markPrice=100),
                                  dict(fundingTime=ms('2024-01-01')+HOUR,fundingRate=.001,markPrice=100)])
            t,e,m=simulate({'BTCUSDT':f},{'BTCUSDT':funding},Settings('futures',start='2024-01-01',end='2024-01-02',strict_data=False))
            self.assertAlmostEqual(t.iloc[0].funding,t.iloc[0].qty*.1*direction)
            self.assertAlmostEqual(metrics(t,e,1000)['reconciliation_error'],0,places=8)
    def test_cost_stress_reduces_flat_trade_pnl(self):
        f=tape()
        a=simulate({'BTCUSDT':f},{},Settings('futures',start='2024-01-01',end='2024-01-02',strict_data=False))[0]
        b=simulate({'BTCUSDT':f},{},Settings('futures',start='2024-01-01',end='2024-01-02',strict_data=False,costs=2))[0]
        self.assertLess(b.net_pnl.sum(),a.net_pnl.sum())
    def test_unrealized_drawdown_is_recorded(self):
        f=tape();f.loc[2,'close']=94.;f.loc[2,'low']=93.
        t,e,m=simulate({'BTCUSDT':f},{},Settings('futures',start='2024-01-01',end='2024-01-02',strict_data=False))
        self.assertGreater(metrics(t,e,1000)['max_drawdown_pct'],.1)
    def test_data_gap_disclosed(self):
        a=tape().drop(index=2);b=tape();b['signal']=0
        t,e,m=simulate({'BTCUSDT':a,'ETHUSDT':b},{},Settings('futures',start='2024-01-01',end='2024-01-02',strict_data=False))
        self.assertEqual(m['data_gap_exits'],1)
    def test_complete_resample_only(self):
        f=tape();self.assertEqual(len(resample_bars(f,4)),1)
        self.assertEqual(len(resample_bars(f.drop(index=2),4)),0)
    def test_rma_seed(self):
        result=rma(pd.Series([1.,2.,3.,4.]),3)
        self.assertTrue(np.isnan(result.iloc[1]));self.assertEqual(result.iloc[2],2)
        self.assertAlmostEqual(result.iloc[3],8/3)
    def test_higher_timeframe_no_future_leak(self):
        n=24*250;t=ms('2023-01-01')+np.arange(n)*HOUR
        rng=np.random.default_rng(42);prices=100*np.exp(np.cumsum(rng.normal(.0001,.003,n)))
        f=pd.DataFrame(dict(open_time=t,close_time=t+HOUR-1,open=prices,high=prices*1.01,
                            low=prices*.99,close=prices,volume=np.ones(n)*1e6,quote_vol=np.ones(n)*1e8))
        a=features(f,'futures',symbol='BTCUSDT')
        cut=n-100;changed=f.copy();changed.loc[cut:,['open','high','low','close']]*=2
        b=features(changed,'futures',symbol='BTCUSDT')
        pd.testing.assert_frame_equal(a.iloc[:cut],b.iloc[:cut])
        self.assertTrue((a.htf_available.dropna()<=a.loc[a.htf_available.notna(),'open_time']).all())

if __name__=='__main__': unittest.main()
