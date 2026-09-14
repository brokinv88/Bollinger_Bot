"""Frozen default Pine signal baseline, independent per-chart ledgers."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from strategy_lab.signals import resample_bars
ROOT=Path(__file__).resolve().parent

def signals(b):
    b=b.copy()
    # HL2 source (research-validated): single series for both bands
    hl2=(b.high+b.low)/2.0
    b['upper']=hl2.rolling(20).mean()+2.0*hl2.rolling(20).std(ddof=0)
    b['lower']=hl2.rolling(20).mean()-2.0*hl2.rolling(20).std(ddof=0)
    above=pd.Series(True,index=b.index)
    out=(b.close<b.lower)&(b.close.shift()>=b.lower.shift())
    for n in (50,100,150,200):
        s=b.close.rolling(n).mean();b[f'sma{n}']=s
        above &= b.close>s
        out |= (b.close<s)&(b.close.shift()>=s.shift())
    b['entry']=above&(b.close>b.upper)&(b.close.shift()<=b.upper.shift())
    b['exit']=out
    return b

def simulate(b,capital=10000.,cash_order=50.,fee=.00075,qty_step=None):
    cash=capital;lots=[];trades=[];curve=[];pending=None;peak=capital;worst=0.;max_layers=0
    for r in b.itertuples(index=False):
        if pending=='exit':
            for lot in lots:
                proceeds=lot['qty']*r.open;ef=proceeds*fee
                cash+=proceeds-ef
                trades.append(dict(**lot,exit_time=r.open_time,exit_price=r.open,exit_fee=ef,
                                   net_pnl=proceeds-ef-lot['notional']-lot['entry_fee']))
            lots=[]
        elif pending=='entry':
            # Cash-sized order modeled at fill price; fractional units, no exchange rounding.
            qty=cash_order/r.open
            if qty_step is not None:
                if qty_step<=0:raise ValueError('qty_step must be positive')
                qty=np.floor(qty/qty_step)*qty_step
            notional=qty*r.open;entry_fee=notional*fee
            cash-=notional+entry_fee
            lots.append(dict(signal_time=previous_close,entry_time=r.open_time,entry_price=r.open,
                             qty=qty,notional=notional,entry_fee=entry_fee,layer=len(lots)+1))
        pending=None
        qty=sum(x['qty'] for x in lots)
        # Historical emulator OHLC path; diagnostic drawdown, not certified TV metric parity.
        path=[r.open,r.high,r.low,r.close] if abs(r.open-r.high)<abs(r.open-r.low) else [r.open,r.low,r.high,r.close]
        for price in path:
            eq=cash+qty*price;peak=max(peak,eq);worst=max(worst,1-eq/peak)
        equity=cash+qty*r.close;max_layers=max(max_layers,len(lots))
        curve.append(dict(time=r.close_time,cash=cash,equity=equity,quantity=qty,layers=len(lots),drawdown_close=1-equity/peak))
        if r.entry and r.exit:raise ValueError('Unexpected simultaneous default entry/exit')
        if r.exit and lots:pending='exit'
        elif r.entry and len(lots)<3:pending='entry'
        previous_close=r.close_time
    t=pd.DataFrame(trades);e=pd.DataFrame(curve)
    pnl=t.net_pnl if len(t) else pd.Series(dtype=float)
    gains=pnl[pnl>0].sum();loss=-pnl[pnl<0].sum()
    result=dict(initial_capital=capital,ending_equity=float(e.equity.iloc[-1]),net_pnl=float(e.equity.iloc[-1]-capital),
                return_pct=float((e.equity.iloc[-1]/capital-1)*100),closed_layers=len(t),
                closed_net_pnl=float(pnl.sum()),win_rate_pct=float((pnl>0).mean()*100) if len(t) else None,
                profit_factor=float(gains/loss) if loss else None,max_drawdown_path_pct=worst*100,
                max_layers=max_layers,open_layers=len(lots),pending_unfilled=pending,
                final_open_pnl_after_entry_fee=float(e.equity.iloc[-1]-capital-pnl.sum()))
    return result,t,e

def main():
    out=ROOT/'results';out.mkdir(exist_ok=True)
    rows=[];manifest=[]
    for market,hours in [('spot',4),('spot',24),('futures',1),('futures',4)]:
        for path in sorted((ROOT.parent/'strategy_lab/data'/market).glob('*USDT.csv')):
            raw=pd.read_csv(path)
            if raw.open_time.duplicated().any():raise ValueError(f'Duplicate {path}')
            cols=['open','high','low','close','volume','quote_vol']
            if not np.isfinite(raw[cols]).all().all() or (raw[['open','high','low','close']]<=0).any().any():raise ValueError(f'Invalid prices {path}')
            if ((raw.high<raw[['open','close','low']].max(axis=1)) | (raw.low>raw[['open','close','high']].min(axis=1))).any():raise ValueError(f'Invalid OHLC {path}')
            raw=raw.sort_values('open_time').reset_index(drop=True)
            width=3600000 if market=='futures' else 14400000
            if not raw.open_time.diff().dropna().eq(width).all():raise ValueError(f'Gap {path}')
            # Trim through last shortened source bar; never bridge incomplete history.
            irregular=raw.index[(raw.close_time-raw.open_time+1)!=width]
            clean=raw.iloc[int(irregular.max())+1:].copy() if len(irregular) else raw
            b=resample_bars(clean,hours)
            if not b.open_time.diff().dropna().eq(hours*3600000).all():raise ValueError(f'Resample gap {path}')
            b=signals(b);name=f'{market}_{hours}h_{path.stem}'
            b.to_csv(out/f'{name}_signals.csv',index=False)
            result,t,e=simulate(b)
            result.update(market=market,timeframe=f'{hours}h',symbol=path.stem,
                          first_bar=int(b.open_time.iloc[0]),last_bar=int(b.close_time.iloc[-1]))
            rows.append(result);t.to_csv(out/f'{name}_trades.csv',index=False);e.to_csv(out/f'{name}_equity.csv',index=False)
            manifest.append(dict(run=name,source=str(path.relative_to(ROOT.parent)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 raw_rows=len(raw),signal_rows=len(b),dropped_source_rows=len(raw)-len(b)*(hours*3600000//width)))
    summary=pd.DataFrame(rows);summary.to_csv(out/'summary.csv',index=False)
    (out/'manifest.json').write_text(json.dumps(dict(sources=manifest,engine_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
    lines=['# Backtest đối chứng Bollinger Envelopes v0','',
           'Rà soát Python; CHƯA đối chiếu giao dịch với TradingView. 48 backtest độc lập, mỗi chart vốn 10.000, mỗi entry cash 50, max 3 entry, phí 0,075% mỗi chiều. Không cộng thành danh mục vốn 5.000.',
           '', 'Nguồn 12 coin sống sót cố định, 2021–08/2026; không phải top 100 thanh khoản lịch sử. Chạy từ đầu dữ liệu, indicator warmup tự nhiên 200 nến. Không tối ưu tham số, không gọi khoảng này là holdout độc lập.',
           '', 'Không stop, target, funding, slippage, đòn bẩy/margin/thanh lý, làm tròn lot hay giới hạn Binance. Futures là tín hiệu trên giá futures theo kế toán nguyên bản, không phải mô phỏng futures thực tế. Cuối mẫu giữ vị thế mở và đánh giá theo close; lệnh chờ cuối mẫu không khớp giả.',
           '', 'Profit factor và win rate tính theo từng entry đã đóng (các lớp cùng vị thế không độc lập). DD tính theo đường OHLC giả định có lãi/lỗ đang mở, không khẳng định bằng số DD TradingView. Cash sizing dùng giá fill; cần xác nhận bằng export TradingView cùng Properties/symbol/khoảng dữ liệu. Không báo R vì không có stop/rủi ro ban đầu.',
           '', '| Nhóm | Coin | Lớp đóng | P&L equity USD | PF lớp đóng | DD % | Lớp mở |','|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        pf=f"{r['profit_factor']:.2f}" if r['profit_factor'] is not None else 'N/A'
        lines.append(f"| {r['market']} {r['timeframe']} | {r['symbol']} | {r['closed_layers']} | {r['net_pnl']:.2f} | {pf} | {r['max_drawdown_path_pct']:.3f} | {r['open_layers']} |")
    lines+=['','DD thấp phải được đọc cùng mức vốn triển khai chỉ khoảng 150 USD/chart; không suy ra an toàn khi tăng size.','',
            'Đối chiếu: chọn đúng Binance symbol spot/perpetual, nến thường, cùng ngày bắt đầu dữ liệu và Inputs/Properties gốc; so Upper/Lower, signal, entry/exit time, qty, phí từng lớp. Lưu sai lệch trước khi dùng kết quả để chọn hệ thống.',
            '', 'Tệp *_signals.csv, *_trades.csv, *_equity.csv cho từng chart; summary.csv tổng hợp; manifest.json giữ hash nguồn.']
    (ROOT/'REPORT_VI.md').write_text('\n'.join(lines))
    print(summary.groupby(['market','timeframe']).agg(runs=('symbol','count'),closed_layers=('closed_layers','sum'),median_pnl_usd=('net_pnl','median')).to_string())
if __name__=='__main__':main()
