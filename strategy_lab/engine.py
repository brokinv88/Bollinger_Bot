"""Event-driven shared-capital simulation. No connectivity or live order code."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd
from .signals import HOUR

@dataclass(frozen=True)
class Settings:
    market: str
    start: str = '2022-01-01'
    end: str = '2026-09-01'
    stop_atr: float = 2.0
    reward_r: float = 3.0
    costs: float = 1.0
    guardrails: bool = False
    strict_data: bool = True
    @property
    def capital(self): return 3000. if self.market=='spot' else 1000.
    @property
    def fee(self): return (.001 if self.market=='spot' else .0005)*self.costs
    @property
    def slip(self): return (.0005 if self.market=='spot' else .0003)*self.costs
    @property
    def risk(self): return 20/3000 if self.market=='spot' else 12.5/1000
    @property
    def width(self): return 4*HOUR if self.market=='spot' else HOUR
    @property
    def maxhold(self): return 90 if self.market=='spot' else 72


def ms(date): return int(pd.Timestamp(date,tz='UTC').timestamp()*1000)

def stop_target_fill(direction, opening, high, low, stop, target):
    """Adverse opening gap, then stop-first for ambiguous OHLC bars."""
    if (direction==1 and opening<=stop) or (direction==-1 and opening>=stop):
        return opening,'GAP_STOP'
    if (direction==1 and opening>=target) or (direction==-1 and opening<=target):
        return target,'GAP_TARGET'
    if (direction==1 and low<=stop) or (direction==-1 and high>=stop):
        return stop,'STOP'
    if (direction==1 and high>=target) or (direction==-1 and low<=target):
        return target,'TARGET'
    return None,None


def simulate(frames:dict, funding:dict, settings:Settings, marks:dict|None=None):
    cfg=settings
    lo,hi=ms(cfg.start),ms(cfg.end)
    if cfg.strict_data:
        for sym,frame in frames.items():
            part=frame[(frame.open_time>=lo)&(frame.open_time<hi)]
            if part.empty or int(part.open_time.iloc[0])!=lo or int(part.open_time.iloc[-1])+cfg.width!=hi:
                raise ValueError(f'{sym}: incomplete test interval')
            if part.open_time.duplicated().any() or not part.open_time.diff().iloc[1:].eq(cfg.width).all():
                raise ValueError(f'{sym}: missing or duplicate test bars')
            if not np.isfinite(part[['open','high','low','close']].to_numpy()).all():
                raise ValueError(f'{sym}: invalid prices')
            if not (part.close_time==part.open_time+cfg.width-1).all():
                raise ValueError(f'{sym}: shortened/nonstandard test candle (warm-up warnings are separate)')
            if cfg.market=='futures':
                fund=funding.get(sym,pd.DataFrame())
                if fund.empty or not np.isfinite(fund.fundingRate).all():
                    raise ValueError(f'{sym}: missing or invalid funding rates')
                relevant=fund[(fund.fundingTime>=lo)&(fund.fundingTime<hi)]
                if (relevant.empty or relevant.fundingTime.min()>=lo+9*HOUR or
                    relevant.fundingTime.max()<hi-9*HOUR or relevant.fundingTime.duplicated().any() or
                    (relevant.fundingTime.diff()>9*HOUR).any()):
                    raise ValueError(f'{sym}: incomplete funding coverage')
                mark=(marks or {}).get(sym,pd.DataFrame())
                if mark.empty:
                    raise ValueError(f'{sym}: missing actual mark-price series')
                mark=mark[(mark.open_time>=lo)&(mark.open_time<hi)]
                if not np.array_equal(mark.open_time.to_numpy(),part.open_time.to_numpy()):
                    raise ValueError(f'{sym}: incomplete mark-price coverage')
                if not np.isfinite(mark[['open','high','low','close']].to_numpy()).all():
                    raise ValueError(f'{sym}: invalid mark prices')
    tapes={}; candidates={}; fund_events={}; mark_tapes={}
    for sym,frame in frames.items():
        f=frame.loc[(frame.open_time>=lo-cfg.width)&(frame.open_time<hi), ['open_time','close_time','open','high','low','close','atr','signal','daily_liquidity']].copy()
        tapes[sym]={int(r['open_time']):r for r in f.to_dict('records')}
        for r in f.to_dict('records'):
            t=int(r['open_time'])+cfg.width
            if r['signal'] and lo<=t<hi:
                candidates.setdefault(t,[]).append((float(r['daily_liquidity']),sym,r))
        if cfg.market=='futures':
            fund=funding.get(sym,pd.DataFrame())
            if not fund.empty:
                for r in fund[(fund.fundingTime>=lo)&(fund.fundingTime<hi)].to_dict('records'):
                    bucket=int(r['fundingTime'])//cfg.width*cfg.width
                    fund_events.setdefault(bucket,[]).append((sym,r))
            mark=(marks or {}).get(sym,pd.DataFrame())
            if not mark.empty:
                mark_tapes[sym]={int(r['open_time']):r for r in mark[(mark.open_time>=lo)&(mark.open_time<hi)].to_dict('records')}
    clock=sorted(set(t for tape in tapes.values() for t in tape if lo<=t<hi))
    cash=cfg.capital; positions={}; trades=[]; curve=[]; peak=cfg.capital
    halted=False; skips={}; stale=0; liquidation_flags=0; funding_proxy=0; ambiguous=0
    def reject(key): skips[key]=skips.get(key,0)+1
    def equity_at(t,field='open'):
        value=cash
        for sym,p in positions.items():
            row=tapes[sym].get(t)
            price=row[field] if row else p['last']
            value+=p['qty']*price if cfg.market=='spot' else p['qty']*p['direction']*(price-p['entry'])
        return value
    def close(sym,t,raw,reason):
        nonlocal cash
        p=positions.pop(sym); exit_px=raw*(1-p['direction']*cfg.slip)
        fee=exit_px*p['qty']*cfg.fee
        gross=p['direction']*(exit_px-p['entry'])*p['qty']
        if cfg.market=='spot': cash+=exit_px*p['qty']-fee
        else: cash+=gross-fee
        net=gross-p['entry_fee']-fee-p['funding']
        trades.append(dict(symbol=sym,market=cfg.market,direction=p['direction'],signal_time=p['signal_time'],
                           entry_time=p['entry_time'],exit_time=t,entry=p['entry'],exit=exit_px,qty=p['qty'],
                           initial_risk=p['initial_risk'],gross_pnl=gross,fees=p['entry_fee']+fee,
                           funding=p['funding'],net_pnl=net,r=net/p['initial_risk'],reason=reason,
                           holding_hours=(t-p['entry_time'])/HOUR))
    for t in clock:
        exited=set()
        # Funding accrued to carried positions; same-time new entries do not pay.
        for sym,event in fund_events.get(t,[]):
            if sym not in positions: continue
            p=positions[sym]
            price=event.get('markPrice',float('nan'))
            if not pd.notna(price) or price<=0:
                mr=mark_tapes.get(sym,{}).get(t)
                price=mr['open'] if mr else tapes[sym].get(t,{}).get('open',p['last'])
                funding_proxy+=1
            paid=p['qty']*price*float(event['fundingRate'])*p['direction']
            cash-=paid; p['funding']+=paid
        # Time exit at open, after previously scheduled funding settlement.
        for sym,p in list(positions.items()):
            row=tapes[sym].get(t)
            if row is None:
                stale+=1
                # Data end/gap: force exit at last observed close; flagged invalid research.
                close(sym,t,p['last'],'DATA_GAP');exited.add(sym);continue
            if t-p['entry_time']>=cfg.maxhold*cfg.width:
                close(sym,t,row['open'],'TIME');exited.add(sym)
        eq=equity_at(t);peak=max(peak,eq)
        dd=1-eq/peak
        if cfg.guardrails and dd>=.12: halted=True
        scale=.5 if cfg.guardrails and dd>=.08 else 1.
        if not halted:
            for _,sym,sig in sorted(candidates.get(t,[]),key=lambda x:(-x[0],x[1])):
                if sym in positions or sym in exited: continue
                row=tapes[sym].get(t)
                if row is None: reject('missing_entry_bar');continue
                eq=equity_at(t)
                if eq<=0: reject('insolvent');continue
                if len(positions)>=(4 if cfg.market=='spot' else 2):reject('position_limit');continue
                budget=eq*cfg.risk*scale
                active=sum(p['initial_risk'] for p in positions.values())
                if active+budget>eq*.02*scale+1e-8:reject('aggregate_risk');continue
                direction=int(sig['signal']);entry=row['open']*(1+direction*cfg.slip)
                dist=cfg.stop_atr*float(sig['atr'])
                stop=entry-direction*dist;target=entry+direction*cfg.reward_r*dist
                if stop<=0 or target<=0 or not math.isfinite(dist):reject('invalid_stop');continue
                stop_fill=stop*(1-direction*cfg.slip)
                unit_loss=direction*(entry-stop_fill)+cfg.fee*(entry+stop_fill)
                qty=budget/unit_loss
                per_notional=eq*(.25 if cfg.market=='spot' else 1.)*scale
                qty=min(qty,per_notional/entry)
                if cfg.market=='spot':qty=min(qty,max(0,cash)/(entry*(1+cfg.fee)))
                else:
                    margin=sum(p['entry']*p['qty']/3 for p in positions.values())
                    gross=sum(p['qty']*tapes[s].get(t,{}).get('open',p['last']) for s,p in positions.items())
                    qty=min(qty,max(0,eq-margin)/(entry/3+entry*cfg.fee),max(0,2*eq-gross)/entry)
                if qty*entry<10:reject('notional_under_10_proxy');continue
                fee=entry*qty*cfg.fee
                cash-=fee+(entry*qty if cfg.market=='spot' else 0)
                positions[sym]=dict(direction=direction,entry=entry,qty=qty,stop=stop,target=target,
                                    entry_fee=fee,initial_risk=unit_loss*qty,funding=0.,entry_time=t,
                                    signal_time=int(sig['close_time'])+1,last=entry)
                # Intrabar funding after entry: charge conservatively when event occurs within bar.
                for fs,event in fund_events.get(t,[]):
                    if fs==sym and int(event['fundingTime'])>t:
                        price=event.get('markPrice',float('nan'))
                        if not pd.notna(price) or price<=0:
                            price=mark_tapes.get(sym,{}).get(t,{}).get('open',row['open']);funding_proxy+=1
                        paid=qty*price*float(event['fundingRate'])*direction
                        cash-=paid;positions[sym]['funding']+=paid
        else:
            for _ in candidates.get(t,[]):reject('drawdown_halt')
        adverse=equity_at(t)
        for sym,p in positions.items():
            row=tapes[sym].get(t)
            if row:
                adverse+=p['qty']*p['direction']*((row['low'] if p['direction']==1 else row['high'])-row['open'])
        for sym,p in list(positions.items()):
            row=tapes[sym][t]
            stop_hit=(row['low']<=p['stop']) if p['direction']==1 else (row['high']>=p['stop'])
            tp_hit=(row['high']>=p['target']) if p['direction']==1 else (row['low']<=p['target'])
            if stop_hit and tp_hit:ambiguous+=1
            # Audit proxy only: exact historical maintenance tiers not available.
            if cfg.market=='futures':
                mark=mark_tapes.get(sym,{}).get(t,row)
                worst=mark['low'] if p['direction']==1 else mark['high']
                loss=p['direction']*(p['entry']-worst)/p['entry']
                if loss>=(1/3-.01):liquidation_flags+=1
            raw,why=stop_target_fill(p['direction'],row['open'],row['high'],row['low'],p['stop'],p['target'])
            if raw is not None:close(sym,t+cfg.width,raw,why)
            else:p['last']=row['close']
        eq=equity_at(t,'close');peak=max(peak,eq)
        curve.append(dict(time=t+cfg.width,equity=eq,adverse_equity=adverse,positions=len(positions),cash=cash))
    if clock:
        t=clock[-1]
        for sym,p in list(positions.items()):close(sym,t+cfg.width,p['last'],'END_OF_TEST')
        curve[-1]['equity']=cash;curve[-1]['positions']=0;curve[-1]['cash']=cash
    td=pd.DataFrame(trades)
    ec=pd.DataFrame(curve)
    meta=dict(settings=asdict(cfg),skips=skips,halted=halted,data_gap_exits=stale,
              liquidation_risk_bars=liquidation_flags,funding_price_proxy_events=funding_proxy,
              ambiguous_bars=ambiguous)
    return td,ec,meta


def metrics(trades,curve,capital):
    if curve.empty:return {'trades':0,'error':'no equity observations'}
    eq=pd.concat([pd.Series([capital]),curve.equity],ignore_index=True)
    draw=1-eq/eq.cummax()
    positive=trades.net_pnl[trades.net_pnl>0].sum() if len(trades) else 0
    negative=-trades.net_pnl[trades.net_pnl<0].sum() if len(trades) else 0
    losers=(trades.net_pnl<0).tolist() if len(trades) else []
    streak=best=0
    for x in losers:
        streak=streak+1 if x else 0;best=max(best,streak)
    daily=curve.assign(date=pd.to_datetime(curve.time,unit='ms',utc=True)).set_index('date').equity.resample('1D').last().ffill()
    rets=daily.pct_change()
    if len(rets): rets.iloc[0]=daily.iloc[0]/capital-1
    rets=rets.dropna()
    sharpe=float(rets.mean()/rets.std()*np.sqrt(365)) if len(rets)>1 and rets.std()>0 else None
    peak_prior=np.maximum.accumulate(np.r_[capital,curve.equity.to_numpy()[:-1]])
    adv=float(np.max(1-curve.adverse_equity.to_numpy()/peak_prior))
    underwater=eq<eq.cummax();run=longest=0
    for flag in underwater:
        run=run+1 if flag else 0;longest=max(longest,run)
    bar_hours=float(np.median(np.diff(curve.time)))/HOUR if len(curve)>1 else 0
    return dict(trades=len(trades),net_pnl=float(eq.iloc[-1]-capital),end_equity=float(eq.iloc[-1]),
                return_pct=float((eq.iloc[-1]/capital-1)*100),max_drawdown_pct=float(draw.max()*100),
                adverse_bar_drawdown_pct=max(0,adv*100),profit_factor=float(positive/negative) if negative>0 else None,
                win_rate_pct=float((trades.net_pnl>0).mean()*100) if len(trades) else 0.,
                mean_r=float(trades.r.mean()) if len(trades) else 0.,fees=float(trades.fees.sum()) if len(trades) else 0.,
                funding=float(trades.funding.sum()) if len(trades) else 0.,max_losing_streak=best,
                longest_underwater_days=longest*bar_hours/24,sharpe_daily=sharpe,
                exposure_pct=float((curve.positions>0).mean()*100),
                reconciliation_error=float(eq.iloc[-1]-capital-(trades.net_pnl.sum() if len(trades) else 0)))
