"""Build the Vietnamese review from saved measured results, without rerunning trades."""
import json
import os
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'strategy-lab-matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'strategy-lab-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from .run_research import combined, PERIODS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports'/'existing_strategies'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def main():
    r=json.loads((OUT/'results.json').read_text())
    def m(n,p='holdout'):return r['runs'][n][p]['metrics']
    names=list(r['runs']);spot=names[:4];futures=names[4:]
    later=table(['Setup','Lợi nhuận','Max DD','PF','Lệnh','Chi phí ×2: lợi nhuận'],[
        [n,f"{m(n)['return_pct']:+.2f}%",f"{m(n)['max_drawdown_pct']:.2f}%",f"{m(n)['profit_factor']:.2f}",m(n)['trades'],f"{m(n,'stress_later')['return_pct']:+.2f}%"] for n in names])
    periods=table(['Setup','2022–23','2024','2025–08/2026','Toàn kỳ: lợi nhuận / DD'],[
        [n,*[f"{m(n,p)['return_pct']:+.2f}%" for p in ['development','validation','holdout']],f"{m(n,'full')['return_pct']:+.2f}% / {m(n,'full')['max_drawdown_pct']:.2f}%"] for n in names])
    yearly=pd.read_csv(OUT/'yearly.csv')
    annual=table(['Setup','2022','2023','2024','2025','2026 đến hết T8'],[
        [n,*[f"{yearly[(yearly.strategy==n)&(yearly.year==y)].iloc[0].return_pct:+.2f}%" for y in range(2022,2027)]] for n in names])
    account={}
    for p in PERIODS:
        s=pd.read_csv(OUT/f'equity_B_SAFE_{p}.csv');f=pd.read_csv(OUT/f'equity_DON55_{p}.csv')
        c,met=combined(s,f);account[p]=met;c.to_csv(OUT/f'equity_account_B_SAFE_AND_DON55_{p}.csv',index=False)
    (OUT/'recommended_account.json').write_text(json.dumps({'note':'Post-review descriptive combination; no independent validation or new sizing test','runs':account},indent=2))
    accountrows=[]
    for label,ps in {**r['account_comparisons'],'B_SAFE + DON55 (chọn sau đánh giá)':account,'60% BTC + 40% tiền mặt':r['benchmarks']}.items():
        accountrows.append([label,f"{ps['holdout']['end_equity']:.2f}",f"{ps['holdout']['return_pct']:+.2f}%",f"{ps['holdout']['max_drawdown_pct']:.2f}%",f"{ps['full']['return_pct']:+.2f}%",f"{ps['full']['max_drawdown_pct']:.2f}%"])
    accounts=table(['Danh mục $5.000','Cuối kỳ gần đây ($)','Lợi nhuận gần đây','DD gần đây','Lợi nhuận toàn kỳ','DD toàn kỳ'],accountrows)
    uncertainty=table(['Setup','Win rate','Chuỗi thua dài nhất','PnL bỏ 5 lệnh tốt nhất ($)','Bootstrap P5…P95 lợi nhuận'],[
        [n,f"{m(n)['win_rate_pct']:.1f}%",m(n)['max_losing_streak'],f"{m(n)['net_without_best_5_trades']:+.2f}",f"{r['bootstrap'][n]['return_pct_p05']:+.1f}% … {r['bootstrap'][n]['return_pct_p95']:+.1f}%"] for n in names])
    decomp=pd.read_csv(OUT/'by_symbol_direction.csv')
    detail=table(['Setup','PnL long ($)','PnL short ($)','Coin tốt nhất: PnL ($)','Coin kém nhất: PnL ($)'],[
        [n,f"{decomp[(decomp.strategy==n)&(decomp.direction==1)].net_pnl.sum():+.2f}",f"{decomp[(decomp.strategy==n)&(decomp.direction==-1)].net_pnl.sum():+.2f}",
         (lambda x:f'{x.idxmax()}: {x.max():+.2f}')(decomp[decomp.strategy==n].groupby('symbol').net_pnl.sum()),
         (lambda x:f'{x.idxmin()}: {x.min():+.2f}')(decomp[decomp.strategy==n].groupby('symbol').net_pnl.sum())] for n in names])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axes=plt.subplots(2,2,figsize=(15,9),layout='constrained')
    colors=['#247ba0','#f09d34','#7d5ba6','#119c78']
    for ax,group,title in [(axes[0,0],spot,'SPOT | sleeve $3,000'),(axes[0,1],futures,'FUTURES | sleeve $1,000')]:
        cap=3000 if group==spot else 1000
        for n,color in zip(group,colors):
            c=pd.read_csv(OUT/f'equity_{n}_holdout.csv');dates=pd.to_datetime(c.time,unit='ms')
            ax.plot(dates,(c.equity/cap-1)*100,label=n,color=color,lw=1.5)
        ax.set(title=title,ylabel='Cumulative return (%)');ax.axhline(0,color='#777777',lw=.5);ax.legend(fontsize=8);ax.grid(alpha=.15)
    ax=axes[1,0]
    for n,label,color in [('B_AND_DON_KELT','B + original futures','#247ba0'),('B_REGIME_AND_TREND','B_REGIME + trend futures','#7d5ba6'),('B_SAFE_AND_DON55','B_SAFE + DON55','#119c78')]:
        c=pd.read_csv(OUT/f'equity_account_{n}_holdout.csv');ax.plot(pd.to_datetime(c.time,unit='ms'),c.equity,label=label,color=color,lw=1.5)
    ax.set(title='TOTAL ACCOUNT | initial $5,000',ylabel='Equity ($)');ax.legend(fontsize=8);ax.grid(alpha=.15)
    ax=axes[1,1];y=np.arange(len(names));ax.barh(y-.18,[m(n)['return_pct'] for n in names],height=.34,label='Base costs',color='#247ba0');ax.barh(y+.18,[m(n,'stress_later')['return_pct'] for n in names],height=.34,label='Fees + slippage doubled',color='#f09d34');ax.set_yticks(y,names);ax.invert_yaxis();ax.set(title='COST STRESS | own-sleeve returns',xlabel='Cumulative return (%)');ax.legend(fontsize=8);ax.axvline(0,color='#777777',lw=.5);ax.grid(axis='x',alpha=.15)
    for ax in [axes[0,0],axes[0,1],axes[1,0]]:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    fig.suptitle('Existing strategy review | 2025-01-01 through 2026-08-31\n12 surviving Binance symbols; retrospective sample, not pristine holdout',fontsize=14)
    fig.savefig(OUT/'comparison.png',dpi=160);plt.close(fig)
    scan=json.loads((OUT/'daily_latest'/'scan.json').read_text())
    counts=pd.Series([x['status'] for x in scan['rows']]).value_counts().to_dict()
    text=f'''# Đánh giá BASE, B, Donchian 55 và Keltner H4

Ngày nghiên cứu: 07/09/2026. Dữ liệu kết thúc 31/08/2026. Đây là bản nghiên cứu mới dựa trên mã trong thư mục, đã sửa cách mô phỏng và hạch toán. Mã và cơ sở dữ liệu vận hành cũ giữ nguyên.

## Quyết định đề xuất

**Ưu tiên DON55 đã sửa thực thi để forward paper futures. Spot chọn B_SAFE làm nền quản trị để tiếp tục nghiên cứu; chưa đủ bằng chứng để tăng vốn.** DON55_TREND không cải thiện rõ trên DON55; KELTNER_TREND đáng theo dõi phụ vì giảm drawdown và số lệnh, nhưng biên lợi thế còn mỏng. Chưa chọn B_REGIME chỉ vì lợi nhuận cao hơn: kết quả phần lớn bị tác động bởi cách chia vốn và chỉ có 16 lệnh gần đây.

## 1. Những vấn đề tìm thấy trong thư mục

- [research_futures_strategy.py](../../../research_futures_strategy.py) và [futures_paper.py](../../../futures_paper.py) dùng `abs(close-entry)` để kích hoạt hòa vốn, kể cả khi giá đi ngược. Sau đó dùng cực trị nến vừa đóng để sửa trailing trước khi kiểm tra chính nến đó. TP được ưu tiên khi đồng thời chạm stop. Đây là lỗi mô phỏng, không phải một lợi thế giao dịch.
- Kiểm thử trực tiếp hàm Keltner cũ tái hiện: vào long 120, nến sau O100/H105/L95/C100 nhưng hàm trả giá thoát 120, cao hơn cả đỉnh 105. Bản mới kiểm tra stop cũ, xử lý gap, rồi mới cập nhật stop cho nến tiếp theo.
- Tham số futures `be=2` là **2 ATR = 1R** vì SL bằng 2 ATR; TP Donchian 7 ATR = 3,5R, Keltner 6 ATR = 3R. Không diễn giải chúng thành 2R/7R/6R.
- [auto_trade.py](../../../auto_trade.py) giả định khớp midpoint giữa band và close, chưa chứng minh có thể khớp limit. Stop spot được đặt lại và có thể nới xuống. [research_improvements.py](../../../research_improvements.py) lại không dùng hard stop mặc định, lọc B chỉ ở lần mua đầu và không có sổ tiền mặt thực.
- PF 6,63 trong [config.py](../../../config.py) là kết quả nghiên cứu cũ trên universe/thời đoạn khác và sau chọn tham số. Tổng lợi nhuận phần trăm từng coin của báo cáo futures không phải lợi nhuận tài khoản; DD theo chênh lệch tuyệt đối và Sharpe theo sự kiện lệnh cũng không tương đương DD theo đỉnh vốn và Sharpe theo ngày.
- Snapshot dữ liệu giấy: bốn sổ spot có tổng 1 giao dịch đã đóng; hai file futures có 0 giao dịch đã đóng. Chưa có mẫu forward paper để xác nhận thống kê. Bằng chứng và hash nguồn lưu trong `results.json`.

## 2. Quy tắc được kiểm tra

**BASE D1:** Close cắt lên SMA20(high) + 1,5 độ lệch chuẩn mẫu của high và ở trên SMA50/100/150/200. Lower band = SMA20(low) − 1,5 độ lệch chuẩn mẫu của low. Thoát khi close cắt xuống lower hoặc một SMA, thực hiện tại open kế tiếp. Hard stop = 99% mức cao nhất của lower và các SMA nằm dưới close. Mỗi lớp $50 gồm phí, tối đa 3 lớp/coin, 10 coin, tổng vốn mua $1.500 trên ví spot $3.000.

**B D1:** BASE thêm ROC5 < 20%, ROC20 < 40%, ATR14/close < 6%; áp dụng cho mọi lần thêm vị thế. ATR ở đây là SMA của true range, giữ đúng mã gốc.

**DON55 H4:** Long khi close vượt đỉnh 55 nến trước và trên EMA50; short đối xứng. ADX ≥ 20, ATR% cao hơn trung bình 50 nến của ATR%. Funding gần nhất đã biết tại đầu nến tín hiệu ≤ +0,05% cho long hoặc ≥ −0,05% cho short. SL 2 ATR, TP 7 ATR, trailing 4 ATR, BE sau close đi thuận 2 ATR. Đây là điều kiện giá nằm ngoài kênh; bản gốc không bắt buộc một giao cắt mới.

**KELTNER H4:** Long trên EMA20 + 1,5 ATR, short dưới EMA20 − 1,5 ATR, ADX ≥ 18, funding một phía ±0,06%. SL 2 ATR, TP 6 ATR, trailing 3,5 ATR, BE sau close đi thuận 2 ATR. Không tự thêm EMA50 hay D1 vào bản nền.

**Bốn phần phát triển:** B_SAFE cấm nới stop và chỉ nhồi khi vị thế đã lãi ít nhất 1R theo close D1; B_REGIME thêm BTC D1 > SMA200 và chia khối lượng theo rủi ro. DON55_TREND/KELTNER_TREND thêm xu hướng coin D1 so với EMA200 đã biết tại đầu nến H4, bắt buộc giao cắt mới, BE sau 4 ATR = 2R và bù phí/trượt giá thoát. Funding tương lai vẫn không được bảo đảm bởi mức BE này. Quy tắc được ghi trước khi chạy kết quả mới trong [EXISTING_SPEC.md](../../EXISTING_SPEC.md).

## 3. Phương pháp và giới hạn

12 coin BTC, ETH, BNB, XRP, ADA, DOGE, LINK, LTC, BCH, DOT, UNI, SOL trên Binance, dữ liệu từ 2021 để khởi tạo chỉ báo, giao dịch 2022–08/2026. Đây là **cohort các coin còn tồn tại**, không phải top100 thanh khoản được tái lập tại từng thời điểm. Chưa có dữ liệu vốn hóa/narrative lịch sử hoặc coin hủy niêm yết; không suy rộng kết quả sang new coin/DEX.

Mỗi ví có sổ vốn và vị thế đồng thời. Spot signal D1, stop trên H4; futures signal H4, stop trên H1. Lệnh ở open sau khi nến tín hiệu hoàn tất, stop trước TP nếu không rõ thứ tự trong nến, trailing chỉ hiệu lực sau khi nến tạo nó đóng. Phí giả định spot 0,10%/chiều + trượt 0,05%; futures 0,05%/chiều + trượt 0,03%, cộng funding từng sự kiện thực. Đây là giả định chi phí, không xác nhận biểu phí tài khoản Binance của bạn. Test stress nhân đôi phí và trượt giá, giữ funding thực.

Funding cũ thiếu markPrice dùng mark OPEN H1 đã biết, có đếm trong audit; giai đoạn gần đây không cần proxy ở các giao dịch này. Đối soát vốn và tổng PnL sai lệch dưới $0,000001. Dữ liệu gốc được kiểm hash 48 file; một số nến spot có close_time rút ngắn trong 2021 chỉ nằm ở warmup, không sửa dữ liệu để che vấn đề.

Các sửa đổi cũng gồm yêu cầu đủ 200 nến chỉ báo, áp dụng đầy đủ filter khi nhồi và khớp open thay midpoint/close. Vì thế đây là kiểm tra phiên bản quy tắc có thể thực thi, **không phải tái tạo nguyên xi các con số cũ**. Diagnostic bỏ hard stop gần đây: BASE {m('BASE','no_hard_stop_later')['return_pct']:+.2f}%, B {m('B','no_hard_stop_later')['return_pct']:+.2f}%.

Kỳ 2025–08/2026 là mẫu thời gian sau nhưng đã được xem trong nghiên cứu trước: **không gọi là holdout độc lập** dù tên file dùng `holdout`. Các lần chạy theo kỳ/năm đều khởi đầu lại với tiền mặt; toàn kỳ là đường vốn liên tục, không cộng số từng năm. Đã kiểm tra chi phí, chia vốn, năm, long/short và độ tập trung; chưa chạy walk-forward tối ưu tham số hoặc quét toàn bộ tham số lân cận.

Chưa mô hình hóa tick, order book, bước lượng/min-notional của từng hợp đồng, maintenance tier và thanh lý chính xác. Audit thanh lý chỉ là ngưỡng cảnh báo, không thay mô hình thanh lý. Chưa áp dụng công tắc dừng lỗ ngày/tuần của cấu hình vận hành vào nghiên cứu này; số liệu đo setup với giới hạn vị thế/margin, chưa phải kết quả hệ thống vận hành hoàn chỉnh. Do những giới hạn này chưa thể gọi là backtest đầy đủ cho triển khai tiền thật.

## 4. Kết quả sau chi phí: 01/2025–08/2026

{later}

Lợi nhuận là lũy kế khoảng 20 tháng; spot tính trên $3.000, futures trên $1.000. DD tính từ đỉnh equity có lãi/lỗ chưa thực hiện, không phải từ tổng vốn từng lệnh. Không cộng các phần trăm này.

{periods}

### Hiệu quả qua từng năm, khởi đầu lại với tiền mặt

{annual}

### Phát triển thêm có thật sự tốt hơn?

- B_SAFE giảm stop nới xuống từ 77 lần ở B xuống 0, DD từ 3,75% xuống 3,57%, lợi nhuận giảm nhẹ từ 1,67% xuống 1,45%. Đây là thay đổi quản trị dễ kiểm soát, chưa chứng minh tăng lợi nhuận.
- B_REGIME native đạt 6,29% nhưng fixed $50 chỉ đạt {m('B_REGIME','equal_size_later')['return_pct']:+.2f}%/{m('B_REGIME','equal_size_later')['trades']} lệnh. Không quy toàn bộ chênh lệch cho bộ lọc BTC. Native thay cả vốn/lệnh và khả năng đủ chỗ nhận lệnh, mẫu còn 16.
- DON55_TREND giảm lợi nhuận gần đây 39,31% → 15,40% trong khi DD gần như ngang nhau. Toàn kỳ, bản TREND có ưu điểm giảm DD 25,23% → 15,69%, đổi lại lợi nhuận 95,16% → 53,28%. Giữ DON55 đơn giản làm ứng viên chính trong phân bổ ví futures nhỏ; bản TREND là lựa chọn để thử nếu ưu tiên giảm DD qua nhiều năm.
- KELTNER_TREND giảm DD 24,73% → 13,19%, số lệnh 442 → 259; PF 1,108 → 1,158. Đổi lại lợi nhuận 17,42% → 13,70%. Đây là ứng viên phụ để thử forward, chưa phải bằng chứng chắc chắn về lợi thế ổn định.
- Khi đồng nhất risk futures về 0,75%, KELTNER_TREND đạt {m('KELTNER_TREND','equal_size_later')['return_pct']:+.2f}%, DD {m('KELTNER_TREND','equal_size_later')['max_drawdown_pct']:.2f}%. So sánh native của nó với KELTNER vẫn cùng 0,60%/lệnh.
- Diagnostic không phí/trượt giá vẫn tính funding. Thay chi phí làm thay khối lượng, vị thế được nhận và dòng lệnh; không lấy chênh lệch return hai lần chạy để gọi là số phí đã trả.

## 5. Độ chắc chắn và sự phụ thuộc vài lệnh lớn

{uncertainty}

Bootstrap lấy lại các block 7 ngày, 1.000 mẫu, chỉ mô tả độ nhạy của đường vốn. Tất cả khoảng P5–P95 đều chứa lợi nhuận âm; không phải khoảng dự báo hay xác nhận độc lập. Spot mất lợi nhuận nếu loại năm lệnh tốt nhất. DON55 còn +$233,81 trong cùng phép thử; lợi thế đo được phân tán hơn nhưng vẫn có chuỗi 11 lệnh thua.

{detail}

Không dùng bảng này để loại coin thua trong quá khứ rồi gọi đó là một kiểm định mới. Chi tiết từng lệnh, phí, funding và coin/hướng đã xuất cùng báo cáo.

## 6. Ghép vào tài khoản $5.000

Giả định spot $3.000 + futures $1.000 + dự phòng $1.000, các ví độc lập. Hai setup futures chạy chung một sổ có giới hạn vị thế/margin, không cộng equity của hai ví $1.000 riêng.

{accounts}

Danh mục B_SAFE + DON55 là phép ghép mô tả sau khi đọc kết quả, không phải một lần kiểm định độc lập. DD thấp một phần do spot $50/lớp và nhiều tiền mặt chưa sử dụng; tăng quy mô sẽ thay đổi rủi ro. Benchmark BTC có mức phơi nhiễm khác nên không dùng để khẳng định alpha đã điều chỉnh rủi ro.

Cho giai đoạn paper, giữ reference $50/lớp của B_SAFE và risk DON55 0,75% ví futures (ban đầu $7,50), 3x, tối đa 3 vị thế DON55, margin toàn ví ≤40%. Đây là cấu hình đã mô phỏng. Nếu triển khai tiền thật sau kiểm chứng, có thể bắt đầu 0,25–0,50% ví futures/lệnh; đây là đề xuất thận trọng, chưa phải một kết quả backtest trong bảng. Max DD 40% của bạn là giới hạn chịu đựng toàn tài khoản, không phải mục tiêu vận hành.

Tiêu chí PAPER_CANDIDATE đặt trước: lãi năm 2024 và kỳ gần đây, PF gần đây ≥1,15, ≥100 lệnh, DD ví ≤20%, stress vẫn lãi, không có cờ thanh lý. DON55, DON55_TREND và KELTNER_TREND qua cổng này. Các bản spot chưa đủ 100 lệnh gần đây; KELTNER gốc không đạt PF và DD. Không có nhãn “được phép chạy live”. Forward paper cần log tín hiệu/giá khớp/chi phí và ít nhất 100 lệnh đóng; mốc 100 là điều kiện cần, không đảm bảo đủ độ tin cậy.

## 7. Bộ lọc và TradingView đã bổ sung

Quét công khai Binance lúc {scan['generated_utc']}: {scan['status']}, {len(scan['rows'])} kết quả profile–coin; phân bố {counts}. Universe hiện tại top100 thanh khoản USDT riêng spot và USD-M perpetual, bỏ stable/pegged và token đòn bẩy. BASE/B cần ≥200 D1; futures gốc ≥200 H4, bản TREND thêm ≥200 D1. Bộ lọc dùng nến đóng, funding thực và đánh dấu tín hiệu đã quá thời điểm open. Kết quả top100 là universe mở rộng **chưa được kiểm định lịch sử**. Chưa có bộ lọc top200 vốn hóa hoặc narrative tự động.

[Mở danh mục quét](daily_latest/SCAN_VI.md). WATCH chỉ đạt một phần điều kiện nền; SETUP vẫn cần kiểm tra vị thế và giới hạn vốn; EXPIRED_SIGNAL không phải điểm vào để đuổi giá. Scanner chưa đọc vị thế thật, chưa quyết định nhồi hoặc khối lượng. Chạy lại thủ công bằng `run_existing_daily.command`; chưa tạo lịch tự động.

Hai Pine v6 monitor cho spot D1 và futures H4 có chọn profile, band và alert khi nến đóng. Futures Pine chỉ kiểm tra điều kiện giá, không có funding Binance tương đương; phải đối chiếu scanner. Spot Pine không quản lý lãi vị thế/nhồi/cash. Chưa biên dịch được trong TradingView do chưa có phiên đăng nhập Pine Editor; chưa xác nhận parity runtime. Không dùng Strategy Tester của một biểu đồ để thay cho backtest danh mục ở đây.

[Hướng dẫn sử dụng và tái chạy](../../EXISTING_README_VI.md). [Kết quả máy đọc](results.json). [Biểu đồ](comparison.png).

## Tài liệu đối chiếu

Giả định mô phỏng lệnh, thứ tự khớp và intrabar cần được phân biệt với kết quả biểu đồ: [TradingView Strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/). Lấy D1 đã xác nhận tại đầu H4 theo mẫu offset `[1]` cùng lookahead: [TradingView Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/). Nguồn endpoint nến/funding/mark: [Binance USD-M Market Data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).
'''
    (OUT/'REPORT_VI.md').write_text(text)
    print(json.dumps({'report':str(OUT/'REPORT_VI.md'),'recommended_account':account['holdout']},ensure_ascii=False))

if __name__=='__main__':main()
