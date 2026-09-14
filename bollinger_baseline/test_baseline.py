import unittest
import numpy as np
import pandas as pd
from bollinger_baseline.run import signals,simulate
class BaselineTests(unittest.TestCase):
    def bars(self):
        return pd.DataFrame(dict(open_time=np.arange(7)*100,close_time=np.arange(7)*100+99,
            open=[100,110,120,130,140,150,160],high=[101,111,121,131,141,151,161],
            low=[99,109,119,129,139,149,159],close=[100,110,120,130,140,150,160],
            entry=[True,True,True,True,False,False,False],exit=[False,False,False,False,True,False,False]))
    def test_fills_pyramids_fees(self):
        r,t,e=simulate(self.bars())
        self.assertEqual(len(t),3);self.assertEqual(t.entry_price.tolist(),[110,120,130])
        self.assertEqual(t.exit_price.tolist(),[150]*3)
        expected=sum((50/p)*150*(1-.00075)-50*(1+.00075) for p in [110,120,130])
        self.assertAlmostEqual(r['net_pnl'],expected);self.assertEqual(r['max_layers'],3)
        self.assertAlmostEqual(e.cash.iloc[-1],10000+expected)
    def test_quantity_rounding_actual_notional_fees(self):
        r,t,e=simulate(self.bars(),qty_step=.01)
        self.assertEqual(t.qty.round(2).tolist(),[.45,.41,.38])
        for row in t.itertuples():
            self.assertAlmostEqual(row.entry_fee,row.qty*row.entry_price*.00075)
        self.assertAlmostEqual(r['net_pnl'],t.net_pnl.sum())

    def test_final_signal_no_fill(self):
        b=self.bars().iloc[:1];r,t,e=simulate(b)
        self.assertEqual(r['open_layers'],0);self.assertEqual(r['pending_unfilled'],'entry')
    def test_open_position_reconciliation(self):
        r,t,e=simulate(self.bars().iloc[:3]);self.assertEqual(r['open_layers'],2)
        self.assertAlmostEqual(r['net_pnl'],r['closed_net_pnl']+r['final_open_pnl_after_entry_fee'])
    def test_cross_requires_new_cross_and_exit(self):
        c=np.full(205,100.);c[200:]=[120,121,122,80,79]
        b=pd.DataFrame({'close':c,'high':c+1,'low':c-1})
        a=signals(b)
        self.assertTrue(a.entry.iloc[200])
        self.assertFalse(a.entry.iloc[201])
        self.assertTrue(a.exit.iloc[203])
        self.assertFalse(a.entry.iloc[:199].any())

    def test_population_std_and_causality(self):
        b=pd.DataFrame({'close':np.arange(250.)+10,'high':np.arange(250.)+11,'low':np.arange(250.)+9})
        a=signals(b)
        hl2=(b.high+b.low)/2.0
        self.assertAlmostEqual(a.upper.iloc[19],np.mean(hl2[:20])+2.0*np.std(hl2[:20],ddof=0))
        b.loc[220:,'high']=10000
        pd.testing.assert_frame_equal(a.iloc[:220],signals(b).iloc[:220])
if __name__=='__main__':unittest.main()
