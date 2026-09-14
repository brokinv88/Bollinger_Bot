"""Export standalone research figures from verified CSV outputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})

def main():
    report=json.loads((OUT/'metrics.json').read_text())
    colors={'spot':'#07856d','futures':'#cf4d4d','combined':'#4059bd'}
    fig,axes=plt.subplots(2,2,figsize=(13,7.5),sharex='col',gridspec_kw={'height_ratios':[2.5,1.3]})
    for col,period in enumerate(('full','holdout')):
        for market in ('spot','futures'):
            eq=pd.read_csv(OUT/f'equity_{market}_{period}.csv')
            capital=3000 if market=='spot' else 1000
            dates=pd.to_datetime(eq.time,unit='ms',utc=True)
            # Add the actual initial account value at the start boundary.
            first=dates.iloc[0]-pd.Timedelta(hours=4 if market=='spot' else 1)
            x=pd.DatetimeIndex([first]+dates.tolist())
            values=np.r_[capital,eq.equity.to_numpy()]
            peak=np.maximum.accumulate(values)
            axes[0,col].plot(x,(values/capital-1)*100,color=colors[market],lw=1.4,label=f'{market.capitalize()} ({capital:,} USD)')
            axes[1,col].plot(x,(values/peak-1)*100,color=colors[market],lw=1.1)
        comb=pd.read_csv(OUT/f'equity_combined_{period}.csv')
        x=pd.to_datetime(comb.time,unit='ms',utc=True)
        vals=comb.equity.to_numpy();peak=np.maximum.accumulate(np.r_[5000,vals])[1:]
        axes[0,col].plot(x,(vals/5000-1)*100,color=colors['combined'],lw=1.5,label='Kết hợp + dự phòng (5.000 USD)')
        axes[1,col].plot(x,(vals/peak-1)*100,color=colors['combined'],lw=1.2)
        axes[0,col].set_title('Toàn kỳ: 2022–08/2026' if period=='full' else 'Ngoài mẫu: 2025–08/2026',loc='left',fontweight='bold')
        axes[0,col].legend(loc='best',fontsize=8,frameon=False)
        axes[0,col].axhline(0,color='#999999',lw=.5)
        for ax in axes[:,col]:
            ax.grid(axis='y',alpha=.15)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4,maxticks=7))
        axes[1,col].tick_params(axis='x',rotation=20)
    axes[0,0].set_ylabel('Lợi nhuận sau chi phí (%)')
    axes[1,0].set_ylabel('Drawdown (%)')
    fig.suptitle('Hai setup Binance: spot có tín hiệu tích cực, futures không đạt',fontsize=16,fontweight='bold',x=.06,ha='left')
    fig.text(.06,.015,'Quy tắc cố định • 12 coin còn tồn tại • Phí + trượt giá + funding thực • Bản raw không dừng tại DD 12%\nTừng kỳ khởi tạo vốn riêng; đây là lịch sử mô phỏng, không phải dự báo. Spot ngoài mẫu chỉ có 85 lệnh, chưa đủ cổng 100 lệnh.',fontsize=9,color='#555555')
    fig.tight_layout(rect=[.02,.07,1,.94])
    fig.savefig(OUT/'equity_drawdown.png',dpi=180,bbox_inches='tight')
    fig.savefig(OUT/'equity_drawdown.svg',bbox_inches='tight')
    plt.close(fig)

if __name__=='__main__':main()
