import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch
import pandas as pd
from strategy_lab.donchian_paper_core import new_state,approve,cancel,advance,order_size,reconcile,equity
from strategy_lab.donchian_paper import exchange_rules,atomic_json,load,source_hash,PublicData,locked,apply_snapshot,export,record_error
from strategy_lab.existing_engine import simulate,Run
from strategy_lab.engine import ms
from strategy_lab.signals import HOUR

BASE=ms('2024-01-01')
RULES=dict(tick=1e-10,step=1e-10,min_qty=1e-10,max_qty=1e9,min_notional=1.)

def fixture(direction=1):
    s=new_state(BASE+1000)
    q=dict(id='test',symbol='BTCUSDT',direction=direction,available=BASE,expires=BASE+4*HOUR,
           reference=100.,atr=5.,rules=RULES,status='READY')
    s['tickets']['test']=q;s['last_refresh']=BASE+1000
    approve(s,'test',BASE+1000)
    bars={'BTCUSDT':{BASE+i*HOUR:dict(open_time=BASE+i*HOUR,open=100.,high=102.,low=98.,close=100.) for i in range(12)}}
    funding={'BTCUSDT':[dict(fundingTime=BASE+i*HOUR,fundingRate=.0001,markPrice=100.) for i in [0,8]]}
    return s,bars,funding,deepcopy(bars)

class DonchianPaperTests(unittest.TestCase):
    def test_full_snapshot_ticket_approval_and_exports(self):
        s=new_state(BASE+1000)
        h4=[]
        for i in range(250):
            t=BASE-(250-i)*4*HOUR;c=100+i*.1 if i<249 else 136.
            h4.append(dict(open_time=t,close_time=t+4*HOUR-1,open=c,high=c+1,low=c-1,close=c,volume=1000,quote_vol=100000))
        data=dict(now=BASE+1000,cut=BASE,scan_errors={},symbols={'BTCUSDT':dict(rules=RULES,h4=h4,funding=[dict(fundingTime=BASE-8*HOUR,fundingRate=.0001,markPrice=100)])})
        a=apply_snapshot(s,data)
        self.assertEqual(len(a['tickets']),1);q=next(iter(a['tickets'].values()))
        self.assertEqual(q['status'],'READY');self.assertEqual(q['direction'],1)
        approve(a,q['id'],BASE+2000)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);a['source_hash']=source_hash();atomic_json(path/'state.json',a)
            export(path,a)
            self.assertIn('QUEUED',(path/'PAPER_DESK_VI.md').read_text())
            self.assertEqual(len(pd.read_csv(path/'tickets.csv')),1)
            record_error(path,ValueError('network failed'))
            self.assertIn('LẦN CẬP NHẬT GẦN NHẤT LỖI',(path/'PAPER_DESK_VI.md').read_text())
            self.assertEqual(load(path),a)

    def test_no_backdated_entry_and_ticket_expiry(self):
        s,_,_,_=fixture();self.assertEqual(s['tickets']['test']['entry_at'],BASE+HOUR)
        s['tickets']['test']['status']='READY';s['cursor']=BASE+3*HOUR;s['last_refresh']=BASE+3*HOUR
        with self.assertRaisesRegex(ValueError,'No future H1'):approve(s,'test',BASE+3*HOUR)
        s['tickets']['test']['status']='QUEUED'
        with self.assertRaisesRegex(ValueError,'retrospectively'):cancel(s,'test',BASE+2*HOUR)

    def test_idempotent_replay_and_open_position_not_force_closed(self):
        s,b,f,m=fixture();a=advance(s,b,f,m,BASE+3*HOUR)
        self.assertIn('BTCUSDT',a['positions']);self.assertEqual(a['positions']['BTCUSDT']['entry_time'],BASE+HOUR)
        self.assertEqual(a,advance(a,b,f,m,BASE+3*HOUR));self.assertEqual(len(s['positions']),0)
        self.assertAlmostEqual(reconcile(a),0,places=8)

    def test_funding_once_only_after_entry(self):
        s,b,f,m=fixture();f['BTCUSDT']=[dict(fundingTime=BASE,fundingRate=.02,markPrice=100),dict(fundingTime=BASE+1000,fundingRate=.0001,markPrice=100),dict(fundingTime=BASE+2*HOUR,fundingRate=.001,markPrice=100)]
        a=advance(s,b,f,m,BASE+3*HOUR);p=a['positions']['BTCUSDT']
        self.assertAlmostEqual(p['funding'],p['qty']*100*.001)
        self.assertEqual(sum(x['kind']=='FUNDING' for x in a['events']),1)
        self.assertEqual(a,advance(a,b,f,m,BASE+3*HOUR))

    def test_missing_hour_fails_without_mutating_ledger(self):
        s,b,f,m=fixture();original=deepcopy(s);del b['BTCUSDT'][BASE+2*HOUR]
        with self.assertRaisesRegex(ValueError,'gap'):advance(s,b,f,m,BASE+3*HOUR)
        self.assertEqual(s,original)

    def test_missing_funding_cannot_be_assumed_zero(self):
        s,b,f,m=fixture();f['BTCUSDT']=[]
        with self.assertRaisesRegex(ValueError,'funding boundary'):advance(s,b,f,m,BASE+3*HOUR)

    def test_price_drift_skips_without_debit(self):
        s,b,f,m=fixture();b['BTCUSDT'][BASE+HOUR].update(open=110,high=111,low=109,close=110)
        a=advance(s,b,f,m,BASE+2*HOUR)
        self.assertEqual(a['tickets']['test']['reason'],'PRICE_DRIFT');self.assertEqual(a['cash'],1000)

    def test_gap_exit_at_open_not_old_stop(self):
        s,b,f,m=fixture();b['BTCUSDT'][BASE+2*HOUR].update(open=80,high=85,low=75,close=82)
        a=advance(s,b,f,m,BASE+3*HOUR);tr=a['trades'][0]
        self.assertEqual(tr['reason'],'GAP_STOP');self.assertAlmostEqual(tr['exit'],80*(1-s['config']['slip']))
        self.assertEqual(tr['exit_time'],BASE+2*HOUR);self.assertAlmostEqual(reconcile(a),0,places=8)

    def test_trail_waits_until_next_bar_and_never_uses_preentry_extreme(self):
        s,b,f,m=fixture();b['BTCUSDT'][BASE].update(high=130)
        b['BTCUSDT'][BASE+3*HOUR].update(high=120,low=95,close=110)
        a=advance(s,b,f,m,BASE+4*HOUR)
        self.assertEqual(len(a['trades']),0);p=a['positions']['BTCUSDT']
        self.assertAlmostEqual(p['stop'],100,places=8)
        b['BTCUSDT'][BASE+4*HOUR].update(open=105,low=99,high=106,close=104)
        z=advance(a,b,f,m,BASE+5*HOUR);self.assertEqual(z['trades'][0]['reason'],'STOP')

    def test_shared_engine_lifecycle_parity_both_directions(self):
        for d in (1,-1):
            s,b,f,m=fixture(d)
            s['config'].update(risk=.0075,total_risk=.03,daily_loss=.5,weekly_loss=.5,max_dd=.5)
            s['tickets']['test']['reserved_risk']=7.5
            # Both engines open at same synthetic timestamp and freeze entry ATR.
            b['BTCUSDT'][BASE+3*HOUR].update(high=120 if d==1 else 105,low=95 if d==1 else 80,close=110 if d==1 else 90)
            b['BTCUSDT'][BASE+4*HOUR].update(open=105 if d==1 else 95,high=106 if d==1 else 101,low=99 if d==1 else 94,close=104 if d==1 else 96)
            raw=pd.DataFrame(list(b['BTCUSDT'].values()))
            signal=pd.DataFrame([dict(available=BASE+HOUR,open_time=BASE-4*HOUR,close=100,high=102,low=98,atr=5,signal=d,exit_signal=False),
                                 dict(available=BASE+4*HOUR,open_time=BASE,close=110 if d==1 else 90,high=120 if d==1 else 105,low=95 if d==1 else 80,atr=5,signal=0,exit_signal=False)])
            tr,_,_,_=simulate({'BTCUSDT':raw},{'DON55':{'BTCUSDT':signal}}, {'BTCUSDT':pd.DataFrame(f['BTCUSDT'])},{'BTCUSDT':pd.DataFrame(list(m['BTCUSDT'].values()))},Run(('DON55',),'2024-01-01','2024-01-01T06:00'))
            a=advance(s,b,f,m,BASE+6*HOUR)
            self.assertEqual(len(a['trades']),1);self.assertEqual(len(tr),1)
            for k in ['entry','exit','qty','net_pnl','funding','fees','initial_risk']:
                self.assertAlmostEqual(a['trades'][0][k],tr.iloc[0][k],places=7,msg=f'{d}: {k}')

    def test_minimum_size_does_not_force_up_risk(self):
        with self.assertRaisesRegex(ValueError,'MINIMUM_ORDER'):
            order_size(100,5,1,2.5,{**RULES,'min_notional':10000},new_state(BASE)['config'])

    def test_risk_guard_survives_manual_resume(self):
        s,b,f,m=fixture();s['halt']='DRAWDOWN_REVIEW_REQUIRED';s['paused']=False
        a=advance(s,b,f,m,BASE+2*HOUR)
        self.assertEqual(a['tickets']['test']['reason'],'ACCOUNT_GUARD')

    def test_exchange_rounding_uses_both_lot_filters(self):
        item=dict(status='TRADING',contractType='PERPETUAL',marginAsset='USDT',filters=[
            dict(filterType='PRICE_FILTER',tickSize='.01',minPrice='.01',maxPrice='1000000'),
            dict(filterType='LOT_SIZE',stepSize='.002',minQty='.002',maxQty='100'),
            dict(filterType='MARKET_LOT_SIZE',stepSize='.003',minQty='.003',maxQty='50'),
            dict(filterType='MIN_NOTIONAL',notional='5')])
        r=exchange_rules(item);self.assertEqual(r['step'],.006);self.assertEqual(r['max_qty'],50)

    def test_network_client_has_no_order_endpoint(self):
        with self.assertRaisesRegex(ValueError,'whitelisted'):PublicData().get('order',symbol='BTCUSDT')

    def test_atomic_persistence_and_source_version_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            book=Path(tmp);s=new_state(BASE);s['source_hash']=source_hash();atomic_json(book/'state.json',s)
            self.assertEqual(load(book),s)
            s['source_hash']='changed';atomic_json(book/'state.json',s)
            with self.assertRaisesRegex(ValueError,'Mã đã thay đổi'):load(book)
            with locked(book):
                with self.assertRaisesRegex(ValueError,'Another paper'):
                    with locked(book):pass

if __name__=='__main__':unittest.main()
