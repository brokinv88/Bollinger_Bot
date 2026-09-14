"""Shared-wallet causal re-evaluation of the four existing strategy families."""
from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd
from .engine import ms, stop_target_fill, metrics
from .signals import HOUR
from .existing_signals import STRATEGIES


def planned_unit_risk(direction, entry, stop, fee, slip):
    """Planned stop loss per contract unit, including both fees and exit slippage."""
    stopfill=stop*(1-direction*slip)
    return direction*(entry-stopfill)+fee*(entry+stopfill)

@dataclass(frozen=True)
class Run:
    names: tuple
    start: str='2022-01-01'
    end: str='2026-09-01'
    costs: float=1.
    equal_size: bool=False
    hard_stop: bool=True
    fixed_cash: float=50.
    @property
    def market(self):return STRATEGIES[self.names[0]].market
    @property
    def capital(self):return 3000. if self.market=='spot' else 1000.
    @property
    def width(self):return 4*HOUR if self.market=='spot' else HOUR
    @property
    def fee(self):return (.001 if self.market=='spot' else .0005)*self.costs
    @property
    def slip(self):return (.0005 if self.market=='spot' else .0003)*self.costs


def next_future_stop(position, completed, strategy, fee, slip):
    """Only called AFTER checking the just-completed bar against its OLD stop."""
    direction=position['direction'];entry=position['entry'];a=position['atr']
    stop=position['stop'];be=position['be']
    if not be and direction*(completed['close']-entry)>=strategy.be_atr*a:
        if strategy.safe:
            # Exit slippage + both-side fee break-even; excludes future unknown funding.
            threshold=(entry*(1+fee)/(1-fee)/(1-slip) if direction==1
                       else entry*(1-fee)/(1+fee)/(1+slip))
        else:threshold=entry
        stop=max(stop,threshold) if direction==1 else min(stop,threshold)
        be=True
    extreme=completed['high'] if direction==1 else completed['low']
    candidate=extreme-direction*strategy.trail_atr*a
    stop=max(stop,candidate) if direction==1 else min(stop,candidate)
    return stop,be


def simulate(raw,signals,funding,marks,cfg):
    names=cfg.names;market=cfg.market
    if any(STRATEGIES[n].market!=market for n in names):raise ValueError('Each simulation has one wallet/market')
    lo,hi=ms(cfg.start),ms(cfg.end)
    tapes={};events={};updates={};funds={};mark_tapes={}
    cols=['open_time','open','high','low','close']
    for sym,b in raw.items():
        part=b[(b.open_time>=lo)&(b.open_time<hi)]
        if part.empty or int(part.open_time.iloc[0])!=lo or int(part.open_time.iloc[-1])+cfg.width!=hi:
            raise ValueError(f'{sym}: incomplete execution interval')
        if not part.open_time.diff().iloc[1:].eq(cfg.width).all():raise ValueError(f'{sym}: execution gap')
        tapes[sym]={int(r['open_time']):r for r in part[cols].to_dict('records')}
        for name in names:
            sg=signals[name][sym]
            keep=sg[(sg.available>=lo)&(sg.available<=hi)]
            needed=['available','open_time','close','high','low','atr','signal','exit_signal']
            needed+=['stop_ref','roc20'] if market=='spot' else []
            for r in keep[needed].to_dict('records'):
                r['name']=name;r['symbol']=sym;t=int(r['available'])
                updates.setdefault(t,{})[(name,sym)]=r
                if r['signal'] and t<hi:events.setdefault(t,[]).append(r)
        if market=='futures':
            fund=funding[sym];f=fund[(fund.fundingTime>=lo)&(fund.fundingTime<hi)]
            if f.empty or not np.isfinite(f.fundingRate).all() or (f.fundingTime.diff()>9*HOUR).any():
                raise ValueError(f'{sym}: incomplete/invalid funding')
            if f.fundingTime.min()>=lo+9*HOUR or f.fundingTime.max()<hi-9*HOUR:raise ValueError('Funding boundary missing')
            for r in f.to_dict('records'):funds.setdefault(int(r['fundingTime'])//cfg.width*cfg.width,[]).append((sym,r))
            mark=marks[sym];mark=mark[(mark.open_time>=lo)&(mark.open_time<hi)]
            if not np.array_equal(mark.open_time.to_numpy(),part.open_time.to_numpy()):raise ValueError('Mark history missing')
            mark_tapes[sym]={int(r['open_time']):r for r in mark[cols].to_dict('records')}
    clock=sorted(set(t for tape in tapes.values() for t in tape))
    cash=cfg.capital;positions={};trades=[];curve=[];skips={};fills=[]
    audit=dict(ambiguous_bars=0,shortened_stop_updates=0,loosened_stop_updates=0,
               be_activations=0,funding_proxy_events=0,liquidation_risk_bars=0,lookahead_errors=0)
    def reject(k):skips[k]=skips.get(k,0)+1
    def equity(t,field='open'):
        value=cash
        for sym,p in positions.items():
            price=tapes[sym][t][field]
            value+=p['qty']*price if market=='spot' else p['direction']*p['qty']*(price-p['entry'])
        return value
    def close(sym,t,price,reason):
        nonlocal cash
        p=positions.pop(sym);px=price*(1-p['direction']*cfg.slip);fee=p['qty']*px*cfg.fee
        gross=p['direction']*p['qty']*(px-p['entry'])
        cash+=p['qty']*px-fee if market=='spot' else gross-fee
        net=gross-p['entry_fee']-fee-p['funding']
        trades.append(dict(strategy=p['name'],symbol=sym,direction=p['direction'],entry_time=p['entry_time'],
                           exit_time=t,entry=p['entry'],exit=px,qty=p['qty'],entries=p['layers'],
                           gross_pnl=gross,fees=p['entry_fee']+fee,funding=p['funding'],net_pnl=net,
                           initial_risk=p['initial_risk'],r=net/p['initial_risk'] if p['initial_risk']>0 else 0,
                           holding_hours=(t-p['entry_time'])/HOUR,reason=reason))
    def funding_event(sym,event,t):
        nonlocal cash
        if sym not in positions:return
        p=positions[sym];price=event.get('markPrice',np.nan)
        if not math.isfinite(price) or price<=0:
            price=mark_tapes[sym][t]['open'];audit['funding_proxy_events']+=1
        cost=p['direction']*p['qty']*price*event['fundingRate']
        cash-=cost;p['funding']+=cost
    for t in clock:
        exited=set()
        # Exact opening funding belongs to carried positions, not entries after event.
        for sym,event in funds.get(t,[]):
            if int(event['fundingTime'])==t:funding_event(sym,event,t)
        # Known opening gaps are resolved before daily signal exits or new entries.
        for sym,p in list(positions.items()):
            opening=tapes[sym][t]['open'];d=p['direction']
            stop_hit=cfg.hard_stop and (opening<=p['stop'] if d==1 else opening>=p['stop'])
            target_hit=market=='futures' and (opening>=p['target'] if d==1 else opening<=p['target'])
            if stop_hit:close(sym,t,opening,'GAP_STOP');exited.add(sym)
            elif target_hit:close(sym,t,p['target'],'GAP_TARGET');exited.add(sym)
        if market=='spot':
            for sym,p in list(positions.items()):
                update=updates.get(t,{}).get((p['name'],sym))
                if update and update['exit_signal']:
                    close(sym,t,tapes[sym][t]['open'],'DAILY_EXIT');exited.add(sym)
        candidates=events.get(t,[])
        candidates=sorted(candidates,key=lambda r:(-r['roc20'],r['symbol'])) if market=='spot' else sorted(candidates,key=lambda r:(r['symbol'],names.index(r['name'])))
        for sig in candidates:
            sym,name=sig['symbol'],sig['name'];strategy=STRATEGIES[name]
            if sym in exited:reject('same_open_reentry');continue
            old=positions.get(sym)
            if old and (market=='futures' or old['name']!=name):continue
            if old and old['layers']>=3:reject('pyramid_limit');continue
            if not old and len(positions)>=(10 if market=='spot' else 6):reject('position_limit');continue
            if market=='futures' and sum(p['name']==name for p in positions.values())>=3:reject('strategy_slots');continue
            if old and strategy.safe and sig['close']<=old['entry']+old['price_risk_sum']/old['qty']:
                reject('pyramid_not_profitable_1R');continue
            eq=equity(t)
            if eq<=0:raise ValueError('Wallet insolvent')
            d=int(sig['signal']);entry=tapes[sym][t]['open']*(1+d*cfg.slip)
            stop=(sig['stop_ref'] if market=='spot' else entry-d*2*sig['atr'])
            if old and strategy.safe:stop=max(stop,old['stop'])
            if market=='spot' and (stop>=entry or stop<=0):reject('invalid_entry_stop');continue
            dist=d*(entry-stop)
            if not math.isfinite(dist) or dist<=0:reject('invalid_entry_risk');continue
            unitrisk=planned_unit_risk(d,entry,stop,cfg.fee,cfg.slip)
            if market=='spot':
                invested=sum(p['invested'] for p in positions.values())
                available=min(cash,max(0.,1500.-invested))
                use_risk=strategy.risk_sized and not cfg.equal_size
                if use_risk:
                    budget=eq*(20/3000)
                    planned=sum(max(0.,tapes[s][t]['open']-p['stop'])*p['qty']+p['qty']*p['stop']*cfg.fee for s,p in positions.items())
                    if planned+budget>eq*.02:reject('risk_cap');continue
                    coin_room=max(0.,eq*.25-(old['qty']*tapes[sym][t]['open'] if old else 0.))
                    qty=min(budget/unitrisk,available/(entry*(1+cfg.fee)),coin_room/entry)
                else:qty=min(cfg.fixed_cash,available)/(entry*(1+cfg.fee))
            else:
                risk=.0075 if cfg.equal_size else strategy.risk
                qty=eq*risk/unitrisk
                margin=sum(p['invested']/3 for p in positions.values())
                if margin+qty*entry/3>eq*.4:reject('margin_cap');continue
            if qty*entry<10:reject('notional_floor_10');continue
            fee=qty*entry*cfg.fee
            cash-=fee+(qty*entry if market=='spot' else 0)
            if old:
                prev_qty=old['qty'];old['qty']+=qty
                old['entry']=(old['entry']*prev_qty+entry*qty)/old['qty']
                old['entry_fee']+=fee;old['invested']+=qty*entry+fee
                old['initial_risk']+=qty*unitrisk;old['price_risk_sum']+=qty*dist
                old['layers']+=1;old['stop']=stop
            else:
                positions[sym]=dict(name=name,direction=d,qty=qty,entry=entry,entry_time=t,
                                    entry_fee=fee,invested=qty*entry+(fee if market=='spot' else 0),
                                    initial_risk=qty*unitrisk,price_risk_sum=qty*dist,layers=1,
                                    stop=stop,target=entry+d*strategy.target_atr*sig['atr'],atr=sig['atr'],
                                    funding=0.,be=False)
            fills.append(dict(strategy=name,symbol=sym,time=t,entry=entry,qty=qty,fee=fee,stop=stop,risk=qty*unitrisk,pyramid=bool(old)))
        # Intra-hour events after opening actions; intrabar stop exit assumed at bar end.
        for sym,event in funds.get(t,[]):
            if int(event['fundingTime'])>t:funding_event(sym,event,t)
        adverse=equity(t)
        for sym,p in positions.items():
            row=tapes[sym][t];d=p['direction'];adverse+=d*p['qty']*((row['low'] if d==1 else row['high'])-row['open'])
        for sym,p in list(positions.items()):
            row=tapes[sym][t];d=p['direction']
            if market=='futures':
                mark=mark_tapes[sym][t];worst=mark['low'] if d==1 else mark['high']
                if d*(p['entry']-worst)/p['entry']>=1/3-.01:audit['liquidation_risk_bars']+=1
                stop_hit=row['low']<=p['stop'] if d==1 else row['high']>=p['stop']
                tp_hit=row['high']>=p['target'] if d==1 else row['low']<=p['target']
                if stop_hit and tp_hit:audit['ambiguous_bars']+=1
                rawexit,reason=stop_target_fill(d,row['open'],row['high'],row['low'],p['stop'],p['target'])
                if rawexit is not None:close(sym,t+cfg.width,rawexit,reason)
            elif cfg.hard_stop and row['low']<=p['stop']:
                close(sym,t+cfg.width,min(row['open'],p['stop']),'STOP')
        # End-of-signal-candle updates can only act from the NEXT execution bar.
        for sym,p in positions.items():
            sig=updates.get(t+cfg.width,{}).get((p['name'],sym))
            if sig is None:continue
            strategy=STRATEGIES[p['name']]
            oldstop=p['stop']
            if market=='spot':
                candidate=sig['stop_ref']
                p['stop']=max(oldstop,candidate) if strategy.safe else candidate
                if p['stop']<oldstop:audit['loosened_stop_updates']+=1
            else:
                stop,be=next_future_stop(p,sig,strategy,cfg.fee,cfg.slip)
                if be and not p['be']:audit['be_activations']+=1
                p['stop']=stop;p['be']=be
            if p['stop']!=oldstop:audit['shortened_stop_updates']+=1
        curve.append(dict(time=t+cfg.width,equity=equity(t,'close'),adverse_equity=adverse,positions=len(positions),cash=cash))
    if clock:
        last=clock[-1]
        for sym,p in list(positions.items()):close(sym,last+cfg.width,tapes[sym][last]['close'],'END_OF_TEST')
        curve[-1].update(equity=cash,cash=cash,positions=0)
    cols=['strategy','symbol','direction','entry_time','exit_time','entry','exit','qty','entries','gross_pnl','fees','funding','net_pnl','initial_risk','r','holding_hours','reason']
    tr=pd.DataFrame(trades,columns=cols);eq=pd.DataFrame(curve)
    stats=metrics(tr,eq,cfg.capital)
    if abs(stats['reconciliation_error'])>1e-6:raise AssertionError('Wallet and trade ledger fail reconciliation')
    return tr,eq,dict(config=asdict(cfg),metrics=stats,audit=audit,skips=skips),pd.DataFrame(fills)
