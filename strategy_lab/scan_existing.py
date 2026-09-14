"""Read-only screener for the eight existing-strategy research profiles."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import time
import pandas as pd
import requests
from .scanner import PublicBinance,pick_universe,utc_iso,InsufficientHistory
from .existing_signals import STRATEGIES,spot_signals,future_signals

OUT=Path(__file__).resolve().parent/'reports'/'existing_strategies'/'daily_latest'


def scan_one(client,item,market,now,btc):
    symbol=item['symbol'];rows=[]
    names=[n for n,s in STRATEGIES.items() if s.market==market]
    try:
        daily=client.bars(market,symbol,'1d',999,now)
        bars=daily if market=='spot' else client.bars(market,symbol,'4h',999,now)
        if len(bars)<200:raise InsufficientHistory('Need 200 complete signal candles')
        fund=pd.DataFrame()
        if market=='futures':
            response=requests.get('https://fapi.binance.com/fapi/v1/fundingRate',params={'symbol':symbol,'limit':100,'endTime':now},timeout=25)
            response.raise_for_status();fund=pd.DataFrame(response.json())
            if fund.empty or not {'fundingTime','fundingRate'}.issubset(fund):raise ValueError('Missing actual funding')
            fund['fundingTime']=pd.to_numeric(fund.fundingTime).astype('int64');fund['fundingRate']=pd.to_numeric(fund.fundingRate)
        for name in names:
            strategy=STRATEGIES[name]
            if strategy.regime and len(daily)<200:raise InsufficientHistory('Trend variant needs 200 complete D1 bars')
            f=spot_signals(daily,btc,strategy) if market=='spot' else future_signals(bars,fund,strategy,daily_bars=daily)
            r=f.iloc[-1];signal=int(r.signal);entry=int(r.available)
            age=max(0,(now-entry)/1000)
            status='EXPIRED_SIGNAL' if signal and age>60 else 'SETUP' if signal else 'WATCH' if bool(r.eligible) else 'FILTERED_OUT'
            rows.append({'strategy':name,'symbol':symbol,'market':market,'status':status,'signal':signal,
                         'direction':'LONG' if signal>0 else 'SHORT' if signal<0 else 'NONE',
                         'quote_volume_24h':item['quote_volume_24h'],'model_entry_utc':utc_iso(entry),'signal_age_seconds':age,
                         'reference_close':float(r.close),'atr_sma14':float(r.atr),'atr_pct':float(r.atr_pct),
                         'funding_known_at_signal_open':float(r.funding_rate) if market=='futures' and pd.notna(r.funding_rate) else None,
                         'reference_stop':float(r.stop_ref) if market=='spot' else None,
                         'reference_stop_distance':2*float(r.atr) if market=='futures' else float(r.close-r.stop_ref),
                         'scope':'EXPANDED_UNVALIDATED','note':'Entry filters only; account position, pyramid profit and portfolio capacity must be checked separately.'})
    except Exception as e:
        existing={r['strategy'] for r in rows}
        status='INSUFFICIENT_HISTORY' if isinstance(e,InsufficientHistory) else 'DATA_ERROR'
        rows.extend({'strategy':name,'symbol':symbol,'market':market,'status':status,'signal':0,'scope':'EXPANDED_UNVALIDATED','reason':str(e)} for name in names if name not in existing)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,default=100)
    p.add_argument('--workers',type=int,default=3);p.add_argument('--output-dir',type=Path,default=OUT)
    args=p.parse_args()
    if not 1<=args.limit<=200 or not 1<=args.workers<=4:p.error('limit 1..200, workers 1..4')
    client=PublicBinance(minimum_request_gap=.2);rows=[];errors=[];clocks={}
    for market in ['spot','futures']:
        try:
            now=int(client.get(market,'time')['serverTime'])
            if abs(now-int(time.time()*1000))>30_000:raise ValueError('Server clock differs >30 seconds')
            clocks[market]=utc_iso(now)
            universe=pick_universe(client.get(market,'exchangeInfo'),client.get(market,'ticker/24hr'),market,args.limit)
            if not universe:raise ValueError('No valid instruments')
            btc=client.bars('spot','BTCUSDT','1d',999,now) if market=='spot' else None
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures=[pool.submit(scan_one,client,item,market,now,btc) for item in universe]
                for f in as_completed(futures):rows.extend(f.result())
            print('Scanned',market,len(universe),flush=True)
        except Exception as e:errors.append(f'{market}: {e}')
    finish=int(time.time()*1000)
    results_path=OUT.parent/'results.json';gates=json.loads(results_path.read_text())['gate'] if results_path.exists() else {}
    for row in rows:
        row['research_gate']=gates.get(row['strategy'],{}).get('status','NOT_EVALUATED')
        if 'model_entry_utc' in row:
            entry=int(pd.Timestamp(row['model_entry_utc']).timestamp()*1000)
            width=(24 if row['market']=='spot' else 4)*3600_000
            row['signal_age_seconds']=max(row['signal_age_seconds'],(finish-entry)/1000)
            if row['status']=='SETUP' and row['signal_age_seconds']>60:row['status']='EXPIRED_SIGNAL'
            if finish//width>entry//width:row.update(status='DATA_ERROR',signal=0,reason='Next signal candle closed during scan; refresh')
    rows.sort(key=lambda r:(r['market'],r['strategy'],-r.get('quote_volume_24h',0),r['symbol']))
    status='FAILED' if not rows else 'PARTIAL' if errors or any(r['status']=='DATA_ERROR' for r in rows) else 'OK'
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    report={'generated_utc':utc_iso(finish),'server_clocks':clocks,'status':status,'errors':errors,'rows':rows}
    (out/'scan.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
    pd.DataFrame(rows).to_csv(out/'scan.csv',index=False,encoding='utf-8-sig')
    lines=['# Bộ lọc BASE/B và Donchian/Keltner','',f"Thời điểm: {report['generated_utc']} UTC. Dữ liệu: **{status}**.",'',
           'Quét top thanh khoản hiện tại, không phải universe lịch sử đã được kiểm chứng. WATCH chỉ đạt một phần điều kiện nền; SETUP/EXPIRED_SIGNAL là bộ lọc entry trên nến hoàn tất, chưa kiểm tra vị thế, điều kiện nhồi lệnh hay vốn còn lại.',
           '', 'PAPER_CANDIDATE chỉ đủ để theo dõi mô phỏng. EXPIRED_SIGNAL đã qua thời điểm mở nến theo backtest, không dùng để đuổi giá. Chưa đặt lệnh và không tự chạy theo lịch.', '',
           '| Chiến lược | Coin | Trạng thái | Hướng | Giờ vào mô hình UTC | Kiểm định |','|---|---|---|---|---|---|']
    valid=[r for r in rows if r['status'] in ['WATCH','SETUP','EXPIRED_SIGNAL']]
    for r in valid:lines.append(f"| {r['strategy']} | {r['symbol']} | {r['status']} | {r['direction']} | {r['model_entry_utc']} | {r['research_gate']} |")
    if not valid:lines.append('| — | Không có ứng viên | — | — | — | — |')
    lines+=['','## Lỗi hoặc chưa đủ lịch sử','']+['- '+str(e) for e in errors]
    for r in rows:
        if r['status'] in ['DATA_ERROR','INSUFFICIENT_HISTORY']:lines.append(f"- {r['strategy']} {r['symbol']}: {r.get('reason',r['status'])}")
    (out/'SCAN_VI.md').write_text('\n'.join(lines)+'\n')
    for name,strategy in STRATEGIES.items():
        symbols=[f"BINANCE:{r['symbol']}{'.P' if strategy.market=='futures' else ''}" for r in valid if r['strategy']==name]
        (out/f'tradingview_{name}.txt').write_text(','.join(symbols)+'\n')
    print(json.dumps({'status':status,'rows':len(rows),'errors':errors,'report':str(out/'SCAN_VI.md')}),flush=True)
    return 0 if status=='OK' else 2

if __name__=='__main__':raise SystemExit(main())
