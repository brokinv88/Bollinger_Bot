"""Causal, shared signal definitions for backtest and live screening."""
from __future__ import annotations
import numpy as np
import pandas as pd

HOUR = 3_600_000
DAY = 24 * HOUR

def resample_bars(bars: pd.DataFrame, hours: int) -> pd.DataFrame:
    """Only complete, contiguous UTC buckets; never invent missing OHLC."""
    b = bars.sort_values('open_time').copy()
    if b.empty:
        return b
    base = int((b.close_time - b.open_time + 1).median())
    width = hours * HOUR
    b['bucket'] = b.open_time // width * width
    g = b.groupby('bucket', sort=True)
    out = g.agg(open=('open','first'), high=('high','max'), low=('low','min'),
                close=('close','last'), volume=('volume','sum'), quote_vol=('quote_vol','sum'),
                count=('open_time','size'), first=('open_time','min'), last=('close_time','max'))
    out = out[(out['count'] == width // base) & (out['first'] == out.index) &
              (out['last'] == out.index + width - 1)].copy()
    out['open_time'] = out.index.astype('int64')
    out['close_time'] = out.open_time + width - 1
    return out[['open_time','open','high','low','close','volume','quote_vol','close_time']].reset_index(drop=True)

def rma(s: pd.Series, n: int) -> pd.Series:
    a = s.to_numpy(dtype=float)
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        out[n-1] = np.mean(a[:n])
        for i in range(n, len(a)):
            out[i] = (out[i-1] * (n-1) + a[i]) / n
    return pd.Series(out, index=s.index)

def indicators(b: pd.DataFrame) -> pd.DataFrame:
    d = b.sort_values('open_time').drop_duplicates('open_time').reset_index(drop=True).copy()
    for n in (20,50,200):
        d[f'ema{n}'] = d.close.ewm(span=n, adjust=False).mean()
    tr = pd.concat([d.high-d.low, (d.high-d.close.shift()).abs(),
                    (d.low-d.close.shift()).abs()],axis=1).max(axis=1)
    d['atr'] = rma(tr,14)
    d['n'] = np.arange(1,len(d)+1)
    return d

def _asof(b: pd.DataFrame, higher: pd.DataFrame, names: dict) -> pd.DataFrame:
    # Available only after higher close, sampled at lower candle OPEN.
    h = higher[['close_time']+list(names)].rename(columns=names).copy()
    h['available'] = h.pop('close_time').astype('int64') + 1
    return pd.merge_asof(b[['open_time']],h.sort_values('available'),
                         left_on='open_time',right_on='available',direction='backward')

def features(bars: pd.DataFrame, market: str, btc_bars: pd.DataFrame | None = None, *,
             higher_bars: pd.DataFrame | None = None, daily_bars: pd.DataFrame | None = None,
             btc_daily: pd.DataFrame | None = None, symbol: str = '', stop_atr: float=2.,
             reward_r: float=3.) -> pd.DataFrame:
    if market not in ('spot','futures'):
        raise ValueError('market must be spot or futures')
    b = indicators(bars)
    daily = daily_bars if daily_bars is not None else resample_bars(bars,24)
    higher = higher_bars if higher_bars is not None else (daily if market=='spot' else resample_bars(bars,4))
    h = indicators(higher)
    h['slope'] = h.ema50 - h.ema50.shift(3)
    hi = _asof(b,h,{'close':'htf_close','ema50':'htf_ema50','ema200':'htf_ema200','n':'htf_n','slope':'htf_slope'})
    for c in ('htf_close','htf_ema50','htf_ema200','htf_n','htf_slope'):
        b[c]=hi[c]
    b['htf_available']=hi.available
    d = indicators(daily)
    d['liq'] = d.quote_vol.rolling(30,min_periods=30).median()
    d['roc20'] = d.close.pct_change(20,fill_method=None)
    di = _asof(b,d,{'liq':'daily_liquidity','roc20':'daily_roc20','n':'daily_n'})
    for c in ('daily_liquidity','daily_roc20','daily_n'):
        b[c]=di[c]
    b['daily_available']=di.available
    max_h_age = DAY if market=='spot' else 4*HOUR
    fresh = ((b.open_time-b.htf_available)<max_h_age) & ((b.open_time-b.daily_available)<DAY)
    ready = (b.htf_n>=200) & (b.daily_n>=30) & b.atr.notna() & (b.atr>0) & fresh
    up=(b.htf_close>b.htf_ema50)&(b.htf_ema50>b.htf_ema200)
    dn=(b.htf_close<b.htf_ema50)&(b.htf_ema50<b.htf_ema200)
    b['btc_roc20']=np.nan
    if market=='spot':
        if btc_daily is None:
            if btc_bars is None:
                if symbol=='BTCUSDT':
                    btc_daily=daily
                else:
                    raise ValueError('spot requires BTC bars to evaluate regime and relative strength')
            else:
                btc_daily=resample_bars(btc_bars,24)
        btc=indicators(btc_daily)
        btc['roc20']=btc.close.pct_change(20,fill_method=None)
        bi=_asof(b,btc,{'close':'btc_close','ema200':'btc_ema200','roc20':'btc_roc20','n':'btc_n'})
        b['btc_roc20']=bi.btc_roc20
        btc_ok=(bi.btc_n>=200)&(bi.btc_close>bi.btc_ema200)&((b.open_time-bi.available)<DAY)
        rs=(b.daily_roc20>b.btc_roc20) if symbol!='BTCUSDT' else pd.Series(True,index=b.index)
        eligible=ready&up&btc_ok&rs&(b.daily_liquidity>=10_000_000)
        channel=b.high.shift(1).rolling(20,min_periods=20).max()
        cross=(b.close>channel)&(b.close.shift(1)<=channel.shift(1))
        b['signal']=np.where(eligible&cross&(b.close>b.ema20),1,0)
        b['trend']=np.where(up,1,np.where(dn,-1,0))
    else:
        up=up&(b.htf_slope>0)
        dn=dn&(b.htf_slope<0)
        eligible=ready&(b.daily_liquidity>=20_000_000)
        long=(b.low.shift(1)<=b.ema20.shift(1))&(b.close.shift(1)>b.ema50.shift(1))&(b.close>b.high.shift(1))&(b.ema20>b.ema50)
        short=(b.high.shift(1)>=b.ema20.shift(1))&(b.close.shift(1)<b.ema50.shift(1))&(b.close<b.low.shift(1))&(b.ema20<b.ema50)
        b['signal']=np.select([eligible&up&long,eligible&dn&short],[1,-1],default=0)
        b['trend']=np.where(up,1,np.where(dn,-1,0))
    b['eligible']=eligible.fillna(False)
    b['stop_distance']=b.atr*stop_atr
    b['reward_r']=reward_r
    return b
