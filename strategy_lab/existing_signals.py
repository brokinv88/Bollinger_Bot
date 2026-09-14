"""Pure definitions recovered from the existing BASE/B/DON/KELT source."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .signals import resample_bars, _asof

@dataclass(frozen=True)
class Strategy:
    name: str
    market: str
    family: str
    safe: bool=False
    regime: bool=False
    risk_sized: bool=False
    fresh_cross: bool=False
    be_atr: float=2.
    trail_atr: float=4.
    target_atr: float=7.
    risk: float=.0075

STRATEGIES={s.name:s for s in [
    Strategy('BASE','spot','BASE'), Strategy('B','spot','B'),
    Strategy('B_SAFE','spot','B',safe=True),
    Strategy('B_REGIME','spot','B',safe=True,regime=True,risk_sized=True),
    Strategy('DON55','futures','DON'),
    Strategy('KELTNER','futures','KELT',trail_atr=3.5,target_atr=6.,risk=.006),
    Strategy('DON55_TREND','futures','DON',safe=True,regime=True,fresh_cross=True,be_atr=4.),
    Strategy('KELTNER_TREND','futures','KELT',safe=True,regime=True,fresh_cross=True,be_atr=4.,trail_atr=3.5,target_atr=6.,risk=.006),
]}

def source_indicators(raw):
    b=raw.sort_values('open_time').reset_index(drop=True).copy()
    c=b.close
    tr=pd.concat([b.high-b.low,(b.high-c.shift()).abs(),(b.low-c.shift()).abs()],axis=1).max(axis=1)
    b['atr']=tr.rolling(14).mean()  # SAME SMA ATR as original, intentionally not ta.atr/Wilder.
    b['atr_pct']=b.atr/c*100
    for n in [20,50,200]:b[f'ema{n}']=c.ewm(span=n,adjust=False).mean()
    for n in [50,100,150,200]:b[f'sma{n}']=c.rolling(n).mean()
    hl2=(b.high+b.low)/2.0
    b['upper']=hl2.rolling(20).mean()+2.0*hl2.rolling(20).std(ddof=0)
    b['lower']=hl2.rolling(20).mean()-2.0*hl2.rolling(20).std(ddof=0)
    b['roc5']=c.pct_change(5,fill_method=None)*100
    b['roc20']=c.pct_change(20,fill_method=None)*100
    up=b.high.diff();down=-b.low.diff()
    plus=pd.Series(np.where((up>down)&(up>0),up,0.),index=b.index)
    minus=pd.Series(np.where((down>up)&(down>0),down,0.),index=b.index)
    trn=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*plus.ewm(alpha=1/14,adjust=False).mean()/trn
    mdi=100*minus.ewm(alpha=1/14,adjust=False).mean()/trn
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    b['adx']=dx.ewm(alpha=1/14,adjust=False).mean()
    b['don_high']=b.high.rolling(55).max().shift(1)
    b['don_low']=b.low.rolling(55).min().shift(1)
    b['k_upper']=b.ema20+1.5*b.atr;b['k_lower']=b.ema20-1.5*b.atr
    b['atr_avg50']=b.atr_pct.rolling(50).mean()
    b['bars']=np.arange(1,len(b)+1)
    return b

def spot_signals(raw,btc_raw,strategy):
    b=source_indicators(resample_bars(raw,24))
    btc=source_indicators(resample_bars(btc_raw,24)).set_index('open_time')
    eligible=b[['sma50','sma100','sma150','sma200']].lt(b.close,axis=0).all(axis=1)&(b.bars>=200)
    cross=(b.close>b.upper)&(b.close.shift()<=b.upper.shift())
    if strategy.family=='B':eligible &= (b.roc5<20)&(b.roc20<40)&(b.atr_pct<6)
    if strategy.regime:
        btc_up=(btc.close>btc.sma200).reindex(b.open_time).fillna(False).to_numpy()
        eligible &= btc_up
    exit_sig=(b.close<b.lower)&(b.close.shift()>=b.lower.shift())
    levels=[]
    for n in [50,100,150,200]:
        level=b[f'sma{n}'];exit_sig |= (b.close<level)&(b.close.shift()>=level.shift())
        levels.append(level.where(level<b.close))
    levels.append(b.lower)
    b['stop_ref']=pd.concat(levels,axis=1).max(axis=1)*.99
    b['signal']=(eligible&cross).astype(int)
    b['exit_signal']=exit_sig
    b['eligible']=eligible
    b['available']=b.close_time+1
    return b

def future_signals(raw,funding,strategy,*,daily_bars=None):
    b=source_indicators(resample_bars(raw,4))
    if funding.empty or not np.isfinite(funding.fundingRate).all():raise ValueError('Actual funding history required')
    f=funding[['fundingTime','fundingRate']].sort_values('fundingTime')
    merged=pd.merge_asof(b[['open_time']],f,left_on='open_time',right_on='fundingTime',direction='backward')
    b['funding_rate']=merged.fundingRate
    fresh=(b.open_time-merged.fundingTime<9*3600_000)&merged.fundingTime.notna()
    if strategy.family=='DON':
        long=(b.close>b.don_high)&(b.close>b.ema50)
        short=(b.close<b.don_low)&(b.close<b.ema50)
        eligible=(b.adx>=20)&(b.atr_pct>b.atr_avg50)
        fdmax=.0005
        if strategy.fresh_cross:
            long &= b.close.shift()<=b.don_high.shift()
            short &= b.close.shift()>=b.don_low.shift()
    else:
        long=b.close>b.k_upper;short=b.close<b.k_lower
        eligible=b.adx>=18;fdmax=.0006
        if strategy.fresh_cross:
            long &= b.close.shift()<=b.k_upper.shift()
            short &= b.close.shift()>=b.k_lower.shift()
    long &= b.funding_rate<=fdmax;short &= b.funding_rate>=-fdmax
    if strategy.regime:
        daily=source_indicators(daily_bars if daily_bars is not None else resample_bars(raw,24))
        h=_asof(b,daily,{'close':'d_close','ema200':'d_ema200','bars':'d_bars'})
        long &= (h.d_close>h.d_ema200)&(h.d_bars>=200)
        short &= (h.d_close<h.d_ema200)&(h.d_bars>=200)
        b['daily_close']=h.d_close;b['daily_ema200']=h.d_ema200
    eligible &= (b.bars>=200)&fresh&b.atr.gt(0)
    b['signal']=np.select([eligible&long,eligible&short],[1,-1],default=0)
    b['eligible']=eligible
    b['exit_signal']=False
    b['available']=b.close_time+1
    return b
