from pathlib import Path
import pandas as pd
from bollinger_baseline.run import simulate
p=Path(__file__).resolve().parent
sample=pd.read_csv(p/'tv_visible_sample.csv')
for c in ['entry','exit']:sample[c+'_time']=pd.to_datetime(sample[c+'_utc'],utc=True).map(lambda x:int(x.timestamp()*1000))
b=pd.read_csv(p.parent/'results/spot_4h_BTCUSDT_signals.csv')
_,t,_=simulate(b,qty_step=.00001)
old=pd.read_csv(p.parent/'results/spot_4h_BTCUSDT_trades.csv')
m=sample.merge(t,on='entry_time',how='left',suffixes=('_tv','_py'),validate='one_to_one')
assert m.entry_price_py.notna().all()
m['times_match']=m.exit_time_tv==m.exit_time_py
m['prices_match']=(m.entry_price_tv-m.entry_price_py).abs().lt(1e-8)&(m.exit_price_tv-m.exit_price_py).abs().lt(1e-8)
m['qty_match']=(m.qty_tv-m.qty_py).abs()<1e-12
m['net_matches_display_cent']=(m.tv_net_pnl-m.net_pnl).abs()<=.00500001
m=m.merge(old[['entry_time','net_pnl']],on='entry_time',suffixes=('','_old'))
m.to_csv(p/'comparison.csv',index=False)
assert m[['times_match','prices_match','qty_match','net_matches_display_cent']].all().all()
print(m[['trade_id','tv_net_pnl','net_pnl_old','net_pnl','times_match','prices_match','qty_match','net_matches_display_cent']].to_string(index=False))
