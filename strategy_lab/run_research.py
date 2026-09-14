"""Run fixed rules, disjoint evaluations, cost stress, sensitivity, portfolio audit."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .data import load_bars, load_funding, load_mark, verify_cache
from .signals import features
from .engine import Settings, simulate, metrics, ms

ROOT=Path(__file__).resolve().parent
SYMBOLS=['BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','LINKUSDT','LTCUSDT','BCHUSDT','DOTUSDT','UNIUSDT','SOLUSDT']
PERIODS={'development':('2022-01-01','2024-01-01'),'validation':('2024-01-01','2025-01-01'),
         'holdout':('2025-01-01','2026-09-01'),'full':('2022-01-01','2026-09-01')}

def block_interval(curve, capital, samples=2000):
    daily=curve.assign(date=pd.to_datetime(curve.time,unit='ms',utc=True)).set_index('date').equity.resample('1D').last().ffill()
    returns=daily.pct_change()
    returns.iloc[0]=daily.iloc[0]/capital-1
    x=returns.dropna().to_numpy()
    if len(x)<14:return None
    rng=np.random.default_rng(20260906);out=[];n=len(x)
    for _ in range(samples):
        starts=rng.integers(0,n,size=int(np.ceil(n/7)))
        idx=np.concatenate([(s+np.arange(7))%n for s in starts])[:n]
        out.append((np.prod(1+x[idx])-1)*100)
    return dict(block_days=7,samples=samples,return_pct_p05=float(np.percentile(out,5)),
                return_pct_p95=float(np.percentile(out,95)),note='Descriptive resampling, not forecast or independent evidence')

def combined(spot,futures):
    a=spot.set_index('time').equity.rename('spot');b=futures.set_index('time').equity.rename('futures')
    c=pd.concat([a,b],axis=1).sort_index().ffill().fillna({'spot':3000.,'futures':1000.})
    c['equity']=c.spot+c.futures+1000.
    peak=np.maximum.accumulate(np.r_[5000.,c.equity.to_numpy()])[1:]
    return c.reset_index(),dict(end_equity=float(c.equity.iloc[-1]),return_pct=float((c.equity.iloc[-1]/5000-1)*100),
                               max_drawdown_pct=float((1-c.equity/peak).max()*100))

def benchmark(bars,start,end):
    b=bars[(bars.open_time>=ms(start))&(bars.open_time<ms(end))]
    buy=b.open.iloc[0]*1.0005;qty=3000/(buy*1.001)
    e=b.close*qty+2000
    e.iloc[-1]=b.close.iloc[-1]*(1-.0005)*qty*(1-.001)+2000
    peak=np.maximum.accumulate(np.r_[5000,e.to_numpy()])[1:]
    return dict(return_pct=float((e.iloc[-1]/5000-1)*100),end_equity=float(e.iloc[-1]),max_drawdown_pct=float((1-e/peak).max()*100))

def table(rows,cols):
    lines=['| '+' | '.join(cols)+' |','|'+'|'.join(['---']*len(cols))+'|']
    for r in rows:
        values=[]
        for k in cols:
            v=r.get(k,'')
            values.append(f'{v:.2f}' if isinstance(v,float) else str(v))
        lines.append('| '+' | '.join(values)+' |')
    return '\n'.join(lines)

def render(report,out):
    lines=['# Hai setup Binance — kết quả kiểm thử và kế hoạch sử dụng',
    '',f"Tạo lúc {report['created_utc']}. Vốn mô phỏng 5.000 USD = spot 3.000 + futures 1.000 + dự phòng 1.000.",
    '', '**Kết luận kiểm định:** '+ '; '.join(f"{m}: **{report['acceptance'][m]['status']}**" for m in ('spot','futures'))+'.',
    '', 'PASS chỉ đủ điều kiện forward test vốn nhỏ, không đồng nghĩa bảo đảm có lợi nhuận. FAILED nghĩa là không đề xuất dùng setup đó để giao dịch tiền thật theo cấu hình này.',
    '', '## Quy tắc đã chốt trước kết quả',
    '', '**Spot D1/H4 breakout:** D1 giá > EMA50 > EMA200, BTC D1 trên EMA200; altcoin ROC20 ngày mạnh hơn BTC. Trung vị turnover30 ngày ≥10 triệu USDT. H4 đóng vượt đỉnh20 nến trước với điều kiện lần đầu vượt; giá trên EMA20. Mua tại mở H4 kế tiếp. Stop2ATR14, target3R, tối đa90 nến H4. BTC được miễn điều kiện tự so sánh ROC.',
    '', '**Futures H4/H1 pullback:** H4 giá > EMA50 > EMA200 và EMA50 đang tăng so với3 nến trước để long; short đảo ngược. H1 trước chạm EMA20 nhưng đóng phía thuận của EMA50, H1 hiện tại đóng vượt đỉnh/đáy nến trước và EMA20/50 thuận hướng. Trung vị turnover30 ngày ≥20 triệu USDT. Vào mở H1 kế tiếp. Stop2ATR14, target3R, tối đa72 nến H1.',
    '', 'Cả hai dùng HTF đã đóng và đã biết tại **mở nến tín hiệu**. Không trailing, không nhồi lệnh, không đổi stop sau vào. Thoát thời gian tại mở nến sau khi đủ thời hạn. Đây là hai giả thuyết giao dịch, không phải kết quả backtest của SMC/ICT tùy ý.',
    '', '## Kết quả ngoài mẫu 01/01/2025–31/08/2026',
    '', table([dict(setup=m,**report['runs'][m]['holdout']['metrics']) for m in ('spot','futures')],['setup','trades','return_pct','net_pnl','profit_factor','win_rate_pct','mean_r','max_drawdown_pct','fees','funding']),
    '', 'Return và drawdown của từng setup tính trên **vốn riêng của setup**; không tính trên tổng5.000 USD. R dùng số tiền lỗ dự kiến tại stop có phí, có thể khác giữa các lệnh do trần vị thế. Funding dương là chi phí, âm là thu nhập.',
    '', '## Tài khoản kết hợp và đối chứng',
    '', table([dict(period=p,**report['combined'][p]) for p in PERIODS],['period','end_equity','return_pct','max_drawdown_pct']),
    '', 'Đối chứng 60% vốn mua giữ BTC spot +40% tiền mặt, có chi phí mua/bán:',
    '', table([dict(period=p,**report['benchmarks'][p]) for p in PERIODS],['period','end_equity','return_pct','max_drawdown_pct']),
    '', 'Các giai đoạn độc lập đều khởi đầu5.000 USD và không có vị thế. Dòng full là một mô phỏng liên tục riêng. Đường equity spot chỉ cập nhật H4, futures H1; equity kết hợp không phản ánh biến động spot bên trong H4.',
    '', '## Phân tách thời gian và chi phí tăng gấp đôi',
    '', table([dict(setup=m,period=p,**r['metrics']) for m in ('spot','futures') for p,r in report['runs'][m].items()],['setup','period','trades','return_pct','profit_factor','max_drawdown_pct','max_losing_streak','longest_underwater_days']),
    '', 'development=2022–2023; validation=2024; holdout=2025–08/2026. stress_holdout tăng gấp đôi cả phí và trượt giá, funding giữ thực tế. guarded_full bật giảm nửa rủi ro khi drawdown vốn setup8%, dừng mở mới từ12%; sau dừng không tự hồi phục. Bản raw vẫn chạy để nhìn thấy rủi ro nguyên gốc.',
    '', '## Tiêu chí chấp nhận đã định trước',
    '', 'Ngoài mẫu: lãi ròng>0, profit factor≥1,15, ít nhất100 lệnh, drawdown equity≤15%, stress chi phí vẫn lãi; thêm không có lỗi đối soát, thiếu dữ liệu vị thế hoặc cảnh báo thanh lý chưa mô hình được.',
    '', *[f"- **{m}: {report['acceptance'][m]['status']}** — "+', '.join(report['acceptance'][m]['failed_checks'] or ['đạt toàn bộ điều kiện định lượng']) for m in ('spot','futures')],
    '', '## Kiểm tra độ bền',
    '', 'Đã chạy lưới stop ATR1,5/2/2,5 × target2R/3R/4R **chỉ trên development và validation**; không chọn lại thông số mặc định từ ngoài mẫu. Xem sensitivity.csv. Yearly.csv kiểm tra từng năm độc lập với quy tắc giữ nguyên, không phải walk-forward có tối ưu tham số.',
    '', table([dict(setup=m,**(report['bootstrap'][m] or {})) for m in ('spot','futures')],['setup','block_days','samples','return_pct_p05','return_pct_p95']),
    '', 'Khoảng trên lấy mẫu lại lợi nhuận ngày theo khối7 ngày,2.000 lần với seed cố định; chỉ mô tả bất định trong mẫu đã quan sát. Không thể coi là xác suất thắng trong tương lai hoặc loại bỏ thiên lệch chọn coin.',
    '', '## Vốn và giới hạn vị thế',
    '', 'Spot rủi ro cơ sở20 USD/lệnh trên vốn3.000; futures12,50 USD/lệnh trên vốn1.000, tăng/giảm theo equity từng phần. Trần rủi ro ban đầu các vị thế của mỗi phần2% equity. Spot tối đa4 vị thế, mỗi vị thế≤25% vốn spot; futures tối đa2, mỗi vị thế≤100% vốn futures, tổng notional≤2×, ký quỹ giả định3×. Do trần2%, futures thường chỉ có1 vị thế với mức risk đầy đủ. Không chuyển tiền dự phòng để bù lỗ.',
    '', 'Không thể diễn giải ngưỡng drawdown40% của bạn là lý do tăng đòn bẩy hoặc tăng rủi ro trước khi có lợi thế được kiểm chứng.',
    '', '## Giả định khớp lệnh và giới hạn dữ liệu',
    '', '- 12 cặp cố định: '+', '.join(SYMBOLS)+'. Đây là **survivor cohort**, chưa kiểm thử đầy đủ các coin đã hủy niêm yết hoặc top200/top100 tại từng ngày lịch sử.',
    '- Binance có5 nến spot H4 với close_time rút ngắn trong2021 trên mỗi cặp, được giữ nguyên và ghi cảnh báo trong manifest. Chúng chỉ thuộc giai đoạn khởi tạo chỉ báo; giai đoạn giao dịch2022 trở đi phải đủ nến tiêu chuẩn.\n- Dữ liệu spot H4, futures H1, funding và mark H1 từ API công khai Binance; thời gian yêu cầu2021-01-01 đến2026-09-01 exclusive. manifest.json lưu thời gian tải, số dòng, thiếu nến, SHA256. Dữ liệu có thể được sàn sửa về sau.',
    '- Phí giả định mỗi chiều: spot10bps, futures5bps; trượt giá mỗi chiều: spot5bps, futures3bps. Không khẳng định đây là bậc phí tài khoản bạn; không giả định được khớp maker.',
    '- Khi nến chạm cả stop và target: stop trước. Gap qua stop: lấy giá mở bất lợi. Target áp dụng trượt giá như lệnh thị trường. Chưa dùng tick/orderbook hoặc Bar Magnifier, có thể sai lệch so với đường giá thực.',
    '- Funding theo từng sự kiện thực. Có markPrice sự kiện thì dùng; nếu thiếu dùng mark OPEN H1 chứa sự kiện, cuối cùng contract open. Funding trong giờ được gán cho vị thế có khả năng chịu sự kiện; việc thoát bên trong giờ không xác định chính xác. Funding credit vẫn được ghi đúng dấu, đây là xấp xỉ thời điểm.',
    '- Mark H1 được dùng rà soát vùng nguy cơ thanh lý với maintenance buffer1%; chưa mô phỏng chính xác historical risk tier, liquidation fee hay insurance engine. Nếu có cảnh báo, kết quả không được thông qua tự động.',
    '- Historical LOT_SIZE/tick size/minNotional không có lịch sử đầy đủ. Backtest dùng lượng liên tục và ngưỡng notional10 USDT; scanner làm tròn theo filter hiện tại. Khoản vốn thực nhỏ có thể gặp sai khác rounding.',
    '- Equity được đánh dấu theo nến, có cả drawdown bất lợi theo cực trị nến trong metrics.json; cực trị nhiều coin có thể không đồng thời, và chưa cắt theo thời điểm stop nên chỉ là stress upper estimate.',
    '- Narrative do người dùng gắn nhãn trong cấu hình; không giả định đã có dữ liệu narrative point-in-time. Danh sách live mở rộng ngoài12 cặp phải forward test riêng.',
    '', '## Sử dụng bộ lọc và TradingView',
    '', 'Đọc ../SCANNER_VI.md để quét top100 thanh khoản hiện tại và xuất watchlist. Báo cáo ngày là danh sách quan sát; tín hiệu đã qua giá mở nến kế tiếp được đánh dấu hết thời điểm vào theo backtest. Dùng Pine theo từng nến đóng để theo dõi trigger H1/H4.',
    '', 'Mã Pine nằm ở ../tradingview/. Python là nguồn kiểm thử danh mục. Pine không tái tạo được funding thực, turnover chính xác, xếp hạng toàn thị trường, giới hạn vốn giữa các chart hay toàn bộ giả định khớp lệnh. Trạng thái kiểm tra compiler ghi trong README TradingView.',
    '', '## Tệp kiểm toán',
    '', 'metrics.json: toàn bộ metrics + audit. trades_*.csv: mọi lệnh. equity_*.csv: equity theo nến. by_symbol.csv, by_direction.csv, yearly.csv: phân rã. sensitivity.csv: lưới ngoài holdout. data/manifest.json: nguồn và tính toàn vẹn dữ liệu. SPEC.md: quy tắc đóng băng trước chạy.',
    '', '## Nguồn chính thức',
    '', '- [Binance market data và funding](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)',
    '- [Binance public data](https://github.com/binance/binance-public-data)',
    '- [TradingView: mô hình strategy và broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/)',
    '- [TradingView: dữ liệu đa khung và tránh dùng tương lai](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)',
    ]
    text='\n'.join(lines)+'\n'
    text=text.replace('## Quy tắc đã chốt trước kết quả', '![Đường vốn và drawdown](equity_drawdown.png)\n\n## Quy tắc đã chốt trước kết quả')
    # Readability edits only; preserve computed values and frozen rules.
    replacements={'5.000 USD = spot':'5.000 USD = spot','tổng5.000':'tổng 5.000','đầu5.000':'đầu 5.000',
      'từ12%':'từ 12%','setup8%':'setup 8%','ATR1,5':'ATR 1,5','target2R':'target 2R','khối7':'khối 7',
      'ngày,2.000':'ngày, 2.000','cơ sở20':'cơ sở 20','vốn3.000':'vốn 3.000','futures12,50':'futures 12,50',
      'vốn1.000':'vốn 1.000','phần2%':'phần 2%','đa4':'đa 4','đa2':'đa 2','equity.40%':'equity. 40%',
      'drawdown40%':'drawdown 40%','đó có5':'đó có 5','có5 nến':'có 5 nến','trong2021':'trong 2021',
      'dịch2022':'dịch 2022','yêu cầu2021':'yêu cầu 2021','spot10bps':'spot 10 bps','futures5bps':'futures 5 bps',
      'spot5bps':'spot 5 bps','futures3bps':'futures 3 bps','buffer1%':'buffer 1%','notional10':'notional 10',
      'ngoài12':'ngoài 12','≥1,15':'≥ 1,15','≥15%':'≥ 15%','≥1':'≥ 1','≥20':'≥ 20','≥10':'≥ 10',
      '≥100':'≥ 100','≤15%':'≤ 15%','ít nhất100':'ít nhất 100','tháng8':'tháng 8'}
    for before,after in replacements.items(): text=text.replace(before,after)
    (out/'REPORT_VI.md').write_text(text)


def main():
    p=argparse.ArgumentParser();p.add_argument('--skip-sensitivity',action='store_true');args=p.parse_args()
    out=ROOT/'reports';out.mkdir(exist_ok=True)
    audit=verify_cache()
    (out/'data_verification.json').write_text(json.dumps(audit,indent=2))
    if audit['status']!='verified':raise RuntimeError('Historical data verification failed; inspect data_verification.json')
    raw={m:{s:load_bars(m,s) for s in SYMBOLS} for m in ('spot','futures')}
    funding={s:load_funding(s) for s in SYMBOLS};marks={s:load_mark(s) for s in SYMBOLS}
    if any(d.empty for d in funding.values()):raise RuntimeError('Missing funding, cannot silently assume zero')
    report=dict(created_utc=pd.Timestamp.now('UTC').isoformat(),spec_sha256=hashlib.sha256((ROOT/'SPEC.md').read_bytes()).hexdigest(),runs={},combined={},benchmarks={},acceptance={},bootstrap={})
    curves={};by_symbol=[];by_dir=[];yearly=[];sensitivity=[]
    for market in ('spot','futures'):
        print(f'Build causal features: {market}',flush=True)
        frames={s:features(raw[market][s],market,raw['spot']['BTCUSDT'],symbol=s) for s in SYMBOLS}
        report['runs'][market]={};curves[market]={}
        scenarios={**{k:(*v,1.,False) for k,v in PERIODS.items()},'stress_holdout':(*PERIODS['holdout'],2.,False),'guarded_full':(*PERIODS['full'],1.,True)}
        for label,(start,end,cost,guard) in scenarios.items():
            cfg=Settings(market,start,end,costs=cost,guardrails=guard)
            t,e,meta=simulate(frames,funding,cfg,marks)
            met=metrics(t,e,cfg.capital)
            if abs(met['reconciliation_error'])>1e-6:raise RuntimeError('Cash / trade accounting mismatch')
            report['runs'][market][label]=dict(metrics=met,audit=meta)
            curves[market][label]=e
            t.to_csv(out/f'trades_{market}_{label}.csv',index=False);e.to_csv(out/f'equity_{market}_{label}.csv',index=False)
            print(market,label,json.dumps(met),flush=True)
            if label=='holdout':
                report['bootstrap'][market]=block_interval(e,cfg.capital)
                for name,g in t.groupby('symbol'):
                    by_symbol.append(dict(market=market,symbol=name,trades=len(g),net_pnl=float(g.net_pnl.sum()),mean_r=float(g.r.mean())))
                for name,g in t.groupby('direction'):
                    by_dir.append(dict(market=market,direction=int(name),trades=len(g),net_pnl=float(g.net_pnl.sum()),mean_r=float(g.r.mean())))
        hold=report['runs'][market]['holdout'];stress=report['runs'][market]['stress_holdout'];h=hold['metrics']
        checks={'net_profit':h['net_pnl']>0,'profit_factor':(h['profit_factor'] or 0)>=1.15,'sample_100':h['trades']>=100,
                'drawdown_15':h['max_drawdown_pct']<=15,'double_cost_profit':stress['metrics']['net_pnl']>0,
                'data_gap':hold['audit']['data_gap_exits']==0,'liquidation_model':hold['audit']['liquidation_risk_bars']==0}
        failed=[k for k,v in checks.items() if not v]
        report['acceptance'][market]=dict(status='PASS_FORWARD_TEST_ONLY' if not failed else 'FAILED',failed_checks=failed)
        for year in range(2022,2027):
            cfg=Settings(market,f'{year}-01-01',f'{year+1}-01-01' if year<2026 else '2026-09-01')
            t,e,_=simulate(frames,funding,cfg,marks);yearly.append(dict(market=market,year=year,**metrics(t,e,cfg.capital)))
        if not args.skip_sensitivity:
            for label in ('development','validation'):
                for stop in (1.5,2.,2.5):
                    for reward in (2.,3.,4.):
                        cfg=Settings(market,*PERIODS[label],stop_atr=stop,reward_r=reward)
                        t,e,_=simulate(frames,funding,cfg,marks)
                        sensitivity.append(dict(market=market,period=label,stop_atr=stop,reward_r=reward,**metrics(t,e,cfg.capital)))
            print(f'{market}: sensitivity completed; defaults unchanged',flush=True)
    for label in PERIODS:
        c,m=combined(curves['spot'][label],curves['futures'][label]);report['combined'][label]=m
        spot_only=curves['spot'][label].equity+2000
        peak=np.maximum.accumulate(np.r_[5000.,spot_only.to_numpy()])[1:]
        report.setdefault('spot_plus_cash',{})[label]=dict(end_equity=float(spot_only.iloc[-1]),return_pct=float((spot_only.iloc[-1]/5000-1)*100),max_drawdown_pct=float((1-spot_only/peak).max()*100))
        c.to_csv(out/f'equity_combined_{label}.csv',index=False)
        report['benchmarks'][label]=benchmark(raw['spot']['BTCUSDT'],*PERIODS[label])
    for name,records in [('by_symbol',by_symbol),('by_direction',by_dir),('yearly',yearly),('sensitivity',sensitivity)]:
        pd.DataFrame(records).to_csv(out/f'{name}.csv',index=False)
    (out/'metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    render(report,out)
    print('COMPLETE',json.dumps(report['acceptance']),flush=True)

if __name__=='__main__':main()
