"""Persistent, closed-H1 PAPER ledger. No network or exchange order capabilities.

Signals, old-stop-first fills, signed breakeven, and risk arithmetic are shared
with the corrected research engine. Manual approval schedules a FUTURE H1 open;
this delayed-entry protocol is deliberately distinct from next-H4-open research.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import math
from .signals import HOUR
from .existing_signals import STRATEGIES
from .existing_engine import next_future_stop, planned_unit_risk
from .engine import stop_target_fill

DEFAULTS=dict(capital=1000.,risk=.0025,total_risk=.0075,max_positions=3,leverage=3.,
              max_margin=.4,daily_loss=.01,weekly_loss=.03,max_dd=.05,
              fee=.0005,slip=.0003,max_drift_atr=.25)

def new_state(now,config=None):
    c={**DEFAULTS,**(config or {})}
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in c.values()):
        raise ValueError('All configuration values must be finite and positive')
    if c['risk']>.0075 or c['total_risk']>.03 or not 1<=c['max_positions']<=3 or not 1<=c['leverage']<=3:
        raise ValueError('Paper limits: risk <=0.75%, total risk <=3%, positions <=3, leverage <=3')
    if not isinstance(c['max_positions'],int) or c['max_margin']>.4 or c['fee']>=.01 or c['slip']>=.01:
        raise ValueError('Invalid margin/position/cost configuration')
    return dict(version=1,mode='PAPER_ONLY',protocol='DON55_APPROVAL_NEXT_H1',config=c,
                created=now,cursor=now//HOUR*HOUR,cash=c['capital'],peak=c['capital'],
                positions={},tickets={},trades=[],events=[],curve=[],paused=False,halt=None,
                day=None,week=None,day_equity=c['capital'],week_equity=c['capital'],
                day_block=False,week_block=False,last_refresh=None)

def equity(s,prices=None):
    prices=prices or {}
    return s['cash']+sum(p['direction']*p['qty']*(prices.get(sym,p['last'])-p['entry']) for sym,p in s['positions'].items())

def event(s,t,kind,**data):
    s['events'].append(dict(time=int(t),kind=kind,**data))

def round_step(value,step,up=False):
    v,st=Decimal(str(value)),Decimal(str(step))
    if st<=0:raise ValueError('Missing/invalid exchange step')
    return float((v/st).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*st)

def order_size(entry,atr,direction,budget,rules,c):
    if direction not in (-1,1) or not all(math.isfinite(x) and x>0 for x in [entry,atr,budget]):
        raise ValueError('Invalid entry, ATR or risk budget')
    # Round both barriers towards entry; never enlarge the initial stop distance.
    stop=round_step(entry-direction*2*atr,rules['tick'],up=direction==1)
    target=round_step(entry+direction*7*atr,rules['tick'],up=direction==-1)
    if direction*(entry-stop)<=0 or direction*(target-entry)<=0 or stop<=0 or target<=0:
        raise ValueError('Invalid rounded SL/TP')
    if min(stop,target)<rules.get('min_price',0) or max(stop,target)>rules.get('max_price',float('inf')):
        raise ValueError('SL/TP outside exchange price bounds')
    unit=planned_unit_risk(direction,entry,stop,c['fee'],c['slip'])
    qty=round_step(min(budget/unit,rules['max_qty']),rules['step'])
    if qty<rules['min_qty'] or qty*entry<rules['min_notional']:
        raise ValueError('MINIMUM_ORDER: risk budget too small; do not increase size to force entry')
    return dict(entry=entry,stop=stop,target=target,qty=qty,initial_risk=qty*unit,
                notional=qty*entry,margin=qty*entry/c['leverage'])

def blockers(s,now):
    result=[]
    if s['paused']:result.append('MANUAL_PAUSE')
    if s['halt']:result.append(s['halt'])
    if s['day_block']:result.append('DAILY_LOSS_LIMIT')
    if s['week_block']:result.append('WEEKLY_LOSS_LIMIT')
    if s['cursor']<now//HOUR*HOUR:result.append('REFRESH_REQUIRED')
    return result

def approve(s,ticket_id,now):
    """Queue only an unexpired, previously observed signal for a future hour."""
    q=s['tickets'].get(ticket_id)
    if q is None:raise ValueError('Unknown ticket')
    if q['status']!='READY':raise ValueError('Ticket already handled or expired')
    if now<q['available']:raise ValueError('Cannot approve before the signal exists')
    entry_at=(now//HOUR+1)*HOUR
    if entry_at>=q['expires']:raise ValueError('No future H1 entry remains before next H4 close; wait for a new signal')
    problems=blockers(s,now)
    if problems:raise ValueError(', '.join(problems))
    if s['last_refresh'] is None or now-s['last_refresh']>120_000:raise ValueError('Refresh within 2 minutes before approval')
    pending=[x for x in s['tickets'].values() if x['status']=='QUEUED']
    if q['symbol'] in s['positions'] or any(x['symbol']==q['symbol'] for x in pending):raise ValueError('Symbol already open/queued')
    c=s['config'];eq=equity(s);budget=eq*c['risk']
    if len(s['positions'])+len(pending)>=c['max_positions']:raise ValueError('Position slots full')
    risk=sum(x['initial_risk'] for x in s['positions'].values())+sum(x['reserved_risk'] for x in pending)
    if risk+budget>eq*c['total_risk']+1e-9:raise ValueError('Total planned risk limit')
    preview=order_size(q['reference']*(1+q['direction']*c['slip']),q['atr'],q['direction'],budget,q['rules'],c)
    margin=sum(p['qty']*p['last']/c['leverage'] for p in s['positions'].values())+sum(x['reserved_margin'] for x in pending)
    if margin+preview['margin']>eq*c['max_margin']:raise ValueError('Margin limit')
    q.update(status='QUEUED',approved_at=now,entry_at=entry_at,reserved_risk=budget,reserved_margin=preview['margin'])
    event(s,now,'APPROVED',ticket=ticket_id,entry_at=entry_at)
    return q

def cancel(s,ticket_id,now,reason='USER_SKIP'):
    q=s['tickets'].get(ticket_id)
    if q is None or q['status'] not in ('READY','QUEUED'):raise ValueError('Ticket is not cancellable')
    if q['status']=='QUEUED' and now>=q['entry_at']:
        raise ValueError('Scheduled open has passed: refresh first; cannot cancel retrospectively')
    q.update(status='CANCELLED',reason=reason)
    event(s,now,'CANCELLED',ticket=ticket_id,reason=reason)

def guard(s,t,eq):
    dt=datetime.fromtimestamp(t/1000,timezone.utc);day=dt.date().isoformat();week=str(dt.isocalendar()[:2])
    if s['day']!=day:s.update(day=day,day_equity=eq,day_block=False)
    if s['week']!=week:s.update(week=week,week_equity=eq,week_block=False)
    s['peak']=max(s['peak'],eq)
    if eq<=s['day_equity']*(1-s['config']['daily_loss']):s['day_block']=True
    if eq<=s['week_equity']*(1-s['config']['weekly_loss']):s['week_block']=True
    if eq<=s['peak']*(1-s['config']['max_dd']):s['halt']='DRAWDOWN_REVIEW_REQUIRED'

def reconcile(s):
    expected=s['config']['capital']+sum(t['net_pnl'] for t in s['trades'])-sum(p['entry_fee']+p['funding'] for p in s['positions'].values())
    if abs(expected-s['cash'])>1e-7:raise AssertionError('Paper cash does not reconcile with trade ledger')
    return expected-s['cash']

def advance(state,bars,funding,marks,cut):
    """Transaction-style catch-up on CLOSED H1 bars; caller atomically persists result.

    bars/marks: symbol -> {open_ms: OHLC}; funding: symbol -> event list.
    Failure leaves caller's state unchanged. Funding at hour-open applies only to
    carried positions; later events precede the approximate bar-end exit.
    """
    s=deepcopy(state);c=s['config']
    if cut%HOUR or cut<s['cursor']:raise ValueError('Invalid closed-hour watermark')
    pending=[q for q in s['tickets'].values() if q['status']=='QUEUED']
    needed=set(s['positions'])|{q['symbol'] for q in pending if q['entry_at']<cut}
    for sym in needed:
        for t in range(s['cursor'],cut,HOUR):
            if t not in bars.get(sym,{}) or t not in marks.get(sym,{}):raise ValueError(f'{sym}: H1/mark gap; no state committed')
        if sym not in funding:raise ValueError(f'{sym}: funding missing')
        # Require a complete enough causal funding envelope, including prior event.
        fs=sorted(funding[sym],key=lambda x:x['fundingTime'])
        if not fs or fs[0]['fundingTime']>s['cursor'] or fs[-1]['fundingTime']<cut-9*HOUR:
            raise ValueError(f'{sym}: funding boundary incomplete')
        if any(b['fundingTime']-a['fundingTime']>9*HOUR for a,b in zip(fs,fs[1:])):
            raise ValueError(f'{sym}: funding gap')
        if len({x['fundingTime'] for x in fs})!=len(fs):raise ValueError('Duplicate funding event')
        if any(not math.isfinite(x['fundingRate']) for x in fs):raise ValueError('Invalid funding rate')

    def close(sym,t,raw,reason):
        p=s['positions'].pop(sym);px=raw*(1-p['direction']*c['slip']);fee=p['qty']*px*c['fee']
        gross=p['direction']*p['qty']*(px-p['entry']);s['cash']+=gross-fee
        net=gross-p['entry_fee']-fee-p['funding']
        tr=dict(ticket=p['ticket'],symbol=sym,direction=p['direction'],entry_time=p['entry_time'],exit_time=t,
                entry=p['entry'],exit=px,qty=p['qty'],fees=p['entry_fee']+fee,funding=p['funding'],
                gross_pnl=gross,net_pnl=net,initial_risk=p['initial_risk'],r=net/p['initial_risk'],reason=reason)
        s['trades'].append(tr);s['tickets'][p['ticket']]['status']='CLOSED'
        event(s,t,'EXIT',**tr)

    def charge(sym,f,t):
        if sym not in s['positions']:return
        p=s['positions'][sym];price=f.get('markPrice',0)
        proxy=not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0
        if proxy:price=marks[sym][t]['open']
        amount=p['direction']*p['qty']*price*f['fundingRate']
        s['cash']-=amount;p['funding']+=amount
        event(s,f['fundingTime'],'FUNDING',symbol=sym,cost=amount,mark_proxy=proxy)

    for t in range(s['cursor'],cut,HOUR):
        opening={sym:bars[sym][t]['open'] for sym in s['positions']}
        guard(s,t,equity(s,opening))
        for sym in needed:
            for f in funding[sym]:
                if f['fundingTime']==t:charge(sym,f,t)
        exited=set()
        for sym,p in list(s['positions'].items()):
            o=bars[sym][t]['open'];d=p['direction']
            if d*(o-p['stop'])<=0:close(sym,t,o,'GAP_STOP');exited.add(sym)
            elif d*(o-p['target'])>=0:close(sym,t,p['target'],'GAP_TARGET');exited.add(sym)
        guard(s,t,equity(s,{sym:bars[sym][t]['open'] for sym in s['positions']}))
        for q in sorted(pending,key=lambda x:(x['entry_at'],x['symbol'])):
            if q['status']!='QUEUED' or q['entry_at']!=t:continue
            sym=q['symbol'];why=None
            eq=equity(s,{sym:bars[sym][t]['open'] for sym in s['positions']})
            try:
                if s['paused'] or s['halt'] or s['day_block'] or s['week_block']:raise ValueError('ACCOUNT_GUARD')
                if sym in s['positions'] or sym in exited:raise ValueError('SYMBOL_BUSY')
                if len(s['positions'])>=c['max_positions']:raise ValueError('SLOTS_FULL')
                if not q['rules'].get('tradable',True):raise ValueError('CONTRACT_NOT_TRADING')
                o=bars[sym][t]['open']
                if abs(o-q['reference'])>q['atr']*c['max_drift_atr']:raise ValueError('PRICE_DRIFT')
                # Do not consume funding published after the scheduled open.
                latest=max((f for f in funding[sym] if f['fundingTime']<=t),key=lambda x:x['fundingTime'])
                if t-latest['fundingTime']>=9*HOUR or q['direction']*latest['fundingRate']>.0005:raise ValueError('ENTRY_FUNDING_FILTER')
                budget=min(eq*c['risk'],q['reserved_risk'])
                p=order_size(o*(1+q['direction']*c['slip']),q['atr'],q['direction'],budget,q['rules'],c)
                risk=sum(x['initial_risk'] for x in s['positions'].values())
                if risk+p['initial_risk']>eq*c['total_risk']+1e-9:raise ValueError('TOTAL_RISK_CAP')
                margin=sum(x['qty']*bars[a][t]['open']/c['leverage'] for a,x in s['positions'].items())
                if margin+p['margin']>eq*c['max_margin']:raise ValueError('MARGIN_CAP')
                fee=p['qty']*p['entry']*c['fee'];s['cash']-=fee
                p.update(ticket=q['id'],direction=q['direction'],entry_time=t,entry_fee=fee,funding=0.,atr=q['atr'],be=False,last=o,rules=q['rules'])
                s['positions'][sym]=p;q['status']='OPEN'
                event(s,t,'ENTRY',ticket=q['id'],symbol=sym,entry=p['entry'],qty=p['qty'],stop=p['stop'],target=p['target'],risk=p['initial_risk'])
            except ValueError as e:why=str(e)
            if why:q.update(status='SKIPPED',reason=why);event(s,t,'SKIPPED',ticket=q['id'],reason=why)
        for sym in needed:
            for f in funding[sym]:
                if t<f['fundingTime']<t+HOUR:charge(sym,f,t)
        for sym,p in list(s['positions'].items()):
            b=bars[sym][t];d=p['direction'];mark=marks[sym][t]
            adverse=mark['low'] if d==1 else mark['high']
            if d*(p['entry']-adverse)/p['entry']>=1/c['leverage']-.01:
                s['halt']='LIQUIDATION_MODEL_REVIEW';event(s,t,'LIQUIDATION_PROXY_FLAG',symbol=sym)
            raw,why=stop_target_fill(d,b['open'],b['high'],b['low'],p['stop'],p['target'])
            if raw is not None:close(sym,t+HOUR,raw,why);continue
            p['last']=b['close']
            if (t+HOUR)%(4*HOUR)==0:
                # Delayed entries cannot trail from highs/lows that predate holding.
                begin=max(p['entry_time'],t-3*HOUR)
                held=[bars[sym][k] for k in range(begin,t+HOUR,HOUR)]
                completed=dict(close=b['close'],high=max(x['high'] for x in held),low=min(x['low'] for x in held))
                old=p['stop'];stop,be=next_future_stop(p,completed,STRATEGIES['DON55'],c['fee'],c['slip'])
                stop=round_step(stop,p['rules']['tick'],up=d==1)
                p['stop']=max(old,stop) if d==1 else min(old,stop);p['be']=be
                if p['stop']!=old:event(s,t+HOUR,'STOP_UPDATED',symbol=sym,old=old,stop=p['stop'],be=be,effective_from=t+HOUR)
        eq=equity(s);guard(s,t,eq)
        s['curve'].append(dict(time=t+HOUR,equity=eq,cash=s['cash'],positions=len(s['positions'])))
        s['cursor']=t+HOUR;reconcile(s)
    for q in s['tickets'].values():
        if q['status']=='READY' and q['expires']<=cut:q['status']='EXPIRED'
    return s
