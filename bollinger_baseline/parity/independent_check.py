"""Independent numpy indicators and event-pair accounting; not TV export parity."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from bollinger_baseline.run import simulate
P=Path(__file__).resolve().parent
b=pd.read_csv(P.parent/'results/spot_4h_BTCUSDT_signals.csv')
c=b.close.to_numpy();n=len(b)
def rolling(a,k,std=False):
    out=np.full(n,np.nan)
    windows=np.lib.stride_tricks.sliding_window_view(a,k)
    out[k-1:]=windows.std(axis=1,ddof=0) if std else windows.mean(axis=1)
    return out
upper=rolling(b.high.to_numpy(),20)+1.5*rolling(b.high.to_numpy(),20,True)
lower=rolling(b.low.to_numpy(),20)-1.5*rolling(b.low.to_numpy(),20,True)
mas=[rolling(c,k) for k in (50,100,150,200)]
entry=np.zeros(n,dtype=bool);ex=np.zeros(n,dtype=bool)
entry[1:]=(c[1:]>upper[1:])&(c[:-1]<=upper[:-1])
entry &= np.logical_and.reduce([c>s for s in mas])
for s in [lower]+mas:ex[1:] |= (c[1:]<s[1:])&(c[:-1]>=s[:-1])
assert np.array_equal(entry,b.entry.to_numpy())
assert np.array_equal(ex,b.exit.to_numpy())
assert np.allclose(upper,b.upper,equal_nan=True,atol=1e-6,rtol=1e-10)
# Partition candidate entries between exit events; first three fresh crosses accepted.
accepted=[];pairs=[];left=0
for exit_signal in np.flatnonzero(ex):
    candidates=np.flatnonzero(entry[left:exit_signal])+left
    chosen=candidates[:3]
    for i in chosen:
        if i+1<n:
            accepted.append(i+1)
            if exit_signal+1<n:pairs.append((i+1,exit_signal+1))
    left=exit_signal+1
for i in (np.flatnonzero(entry[left:])+left)[:3]:
    if i+1<n:accepted.append(i+1)
qty=lambda i:np.floor((50/b.open.iloc[i])/.00001)*.00001
ledger=[];flows=np.zeros(n);position_changes=np.zeros(n)
for i in accepted:
    q=qty(i);flows[i]-=q*b.open.iloc[i]*1.00075;position_changes[i]+=q
for i,j in pairs:
    q=qty(i);ep=b.open.iloc[i];xp=b.open.iloc[j]
    flows[j]+=q*xp*.99925;position_changes[j]-=q
    ledger.append(dict(entry_time=int(b.open_time.iloc[i]),exit_time=int(b.open_time.iloc[j]),qty=q,net_pnl=q*(xp-ep)-q*(ep+xp)*.00075))
reference=pd.DataFrame(ledger).sort_values(['entry_time','exit_time']).reset_index(drop=True)
r,t,e=simulate(b,qty_step=.00001)
t=t.sort_values(['entry_time','exit_time']).reset_index(drop=True)
assert len(t)==len(reference)
for col in reference:
    assert np.allclose(reference[col],t[col],atol=1e-8,rtol=0),col
independent_equity=10000+flows.cumsum()+position_changes.cumsum()*c
assert np.allclose(independent_equity,e.equity,atol=1e-7,rtol=0)
reference.to_csv(P/'independent_ledger.csv',index=False)
result=dict(status='PASS_INTERNAL_ONLY',bars=n,closed_entries=len(t),entry_signals=int(entry.sum()),exit_signals=int(ex.sum()),
    max_equity_difference=float(np.max(abs(independent_equity-e.equity))),
    limitations=['Same local OHLC input; does not validate feed against TradingView','BTCUSDT step .00001 inferred from 7 visible trades','No full TradingView trade export parity','Intrabar DD not independently validated'])
(P/'independent_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
