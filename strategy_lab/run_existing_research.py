"""Re-evaluate four existing systems and four declared extensions; never trade."""
import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from .data import load_bars,load_funding,load_mark,verify_cache
from .existing_signals import STRATEGIES,spot_signals,future_signals
from .existing_engine import Run,simulate
from .run_research import SYMBOLS,PERIODS,block_interval,combined,benchmark

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports'/'existing_strategies'
SOURCE_FILES=['config.py','daily_scanner.py','auto_trade.py','research_improvements.py','research_futures_framework.py',
              'research_futures_strategy.py','futures_paper.py','futures_sizing_validate.py','research_futures_report.md',
              'improvement_proposals_report.csv','futures_trading_plan.md']

def source_audit():
    result={'source_hashes':{},'paper_evidence':{}}
    for name in SOURCE_FILES:
        path=ROOT.parent/name;result['source_hashes'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ['database_volume.db','database_marketcap.db','database_volume_stratb.db','database_marketcap_stratb.db']:
        p=ROOT.parent/name
        with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
            result['paper_evidence'][name]={'open_positions':c.execute('SELECT COUNT(*) FROM positions').fetchone()[0],
                                          'closed_trades':c.execute('SELECT COUNT(*) FROM trade_history').fetchone()[0]}
    for name in ['paper_trades.csv','bridge_trades.csv']:
        result['paper_evidence'][name]={'closed_trades':len(pd.read_csv(ROOT.parent/name))}
    # Execute only a pure source function, not legacy modules / scripts / APIs.
    tree=ast.parse((ROOT.parent/'research_futures_strategy.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='strategy_keltner_h4')
    ns={'pd':pd,'np':np};exec(compile(ast.Module(body=[fn],type_ignores=[]),'isolated_original_function','exec'),ns)
    b=pd.DataFrame({'open':[100.]*202,'high':[101.]*202,'low':[99.]*202,'close':[100.]*202,'atr':[5.]*202,'adx14':[0.]*202,'funding_rate':[0.]*202})
    b.loc[200,['open','high','low','close','adx14']]=[100,121,99,120,25]
    b.loc[201,['open','high','low','close','adx14']]=[100,105,95,100,25]
    _,tr=ns['strategy_keltner_h4'](b)
    result['unreachable_fill_example']={'description':'Original Keltner BE uses abs(adverse close change). Entry120; next candle O100 H105 L95 C100; returns exit120, above bar high105.',
                                        'original_trade':tr[0] if tr else None,'next_bar':{'open':100,'high':105,'low':95,'close':100}}
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    audit=verify_cache()
    if audit['status']!='verified':raise RuntimeError('Raw data verification failed')
    raw={m:{s:load_bars(m,s) for s in SYMBOLS} for m in ['spot','futures']}
    funding={s:load_funding(s) for s in SYMBOLS};marks={s:load_mark(s) for s in SYMBOLS}
    signals={};records=[];curves={};details={};yearly=[];decomp=[]
    report={'created_utc':pd.Timestamp.now('UTC').isoformat(),'spec_sha256':hashlib.sha256((ROOT/'EXISTING_SPEC.md').read_bytes()).hexdigest(),
            'validation_note':'Retrospective reused later-time sample; no claim of pristine holdout.',
            'data_verification':audit,'source_audit':source_audit(),'strategies':{k:asdict(v) for k,v in STRATEGIES.items()},'runs':{},'gate':{},'bootstrap':{}}
    for name,strategy in STRATEGIES.items():
        print('Preparing',name,flush=True)
        signals[name]={s:(spot_signals(raw['spot'][s],raw['spot']['BTCUSDT'],strategy) if strategy.market=='spot'
                          else future_signals(raw['futures'][s],funding[s],strategy)) for s in SYMBOLS}
        report['runs'][name]={};curves[name]={}
        scenarios={**{label:Run((name,),*dates) for label,dates in PERIODS.items()},
                   'stress_later':Run((name,),*PERIODS['holdout'],costs=2),
                   'equal_size_later':Run((name,),*PERIODS['holdout'],equal_size=True),
                   'gross_later':Run((name,),*PERIODS['holdout'],costs=0)}
        if name in ['BASE','B']:scenarios['no_hard_stop_later']=Run((name,),*PERIODS['holdout'],hard_stop=False)
        for label,cfg in scenarios.items():
            tr,eq,meta,fills=simulate(raw[strategy.market],signals,funding,marks,cfg)
            report['runs'][name][label]=meta
            records.append(dict(strategy=name,market=strategy.market,period=label,**meta['metrics']))
            if label in PERIODS or label=='stress_later':
                tr.to_csv(OUT/f'trades_{name}_{label}.csv',index=False)
                eq.to_csv(OUT/f'equity_{name}_{label}.csv',index=False)
                fills.to_csv(OUT/f'fills_{name}_{label}.csv',index=False)
            if label in PERIODS:curves[name][label]=eq
            if label=='holdout':
                report['bootstrap'][name]=block_interval(eq,cfg.capital,1000)
                for (sym,direction),g in tr.groupby(['symbol','direction']):
                    decomp.append(dict(strategy=name,symbol=sym,direction=int(direction),trades=len(g),net_pnl=float(g.net_pnl.sum()),mean_r=float(g.r.mean())))
                meta['metrics']['net_without_best_5_trades']=float(tr.net_pnl.sum()-tr.net_pnl.nlargest(5).sum())
            print(name,label,round(meta['metrics']['return_pct'],2),round(meta['metrics']['max_drawdown_pct'],2),meta['metrics']['trades'],flush=True)
        for year in range(2022,2027):
            cfg=Run((name,),f'{year}-01-01',f'{year+1}-01-01' if year<2026 else '2026-09-01')
            _,_,meta,_=simulate(raw[strategy.market],signals,funding,marks,cfg)
            yearly.append(dict(strategy=name,year=year,**meta['metrics']))
        h=report['runs'][name]['holdout'];v=report['runs'][name]['validation']['metrics'];stress=report['runs'][name]['stress_later']['metrics']
        met=h['metrics'];checks={'validation_profit':v['net_pnl']>0,'later_profit':met['net_pnl']>0,
                               'profit_factor':(met['profit_factor'] or 0)>=1.15,'sample100':met['trades']>=100,
                               'sleeve_dd20':met['max_drawdown_pct']<=20,'cost_stress':stress['net_pnl']>0,
                               'liquidation_audit':h['audit']['liquidation_risk_bars']==0}
        failed=[k for k,value in checks.items() if not value]
        report['gate'][name]={'status':'PAPER_CANDIDATE' if not failed else 'RESEARCH_ONLY','failed':failed}
    report['shared_futures']={}
    for label,names in [('DON_KELT',('DON55','KELTNER')),('TREND_PAIR',('DON55_TREND','KELTNER_TREND'))]:
        curves[label]={};report['shared_futures'][label]={}
        for period,dates in PERIODS.items():
            tr,eq,meta,fills=simulate(raw['futures'],signals,funding,marks,Run(names,*dates))
            report['shared_futures'][label][period]=meta
            curves[label][period]=eq
            tr.to_csv(OUT/f'trades_{label}_{period}.csv',index=False);eq.to_csv(OUT/f'equity_{label}_{period}.csv',index=False)
    report['account_comparisons']={};report['benchmarks']={}
    for label,spot,future in [('BASE_AND_DON_KELT','BASE','DON_KELT'),('B_AND_DON_KELT','B','DON_KELT'),('B_REGIME_AND_TREND','B_REGIME','TREND_PAIR')]:
        report['account_comparisons'][label]={}
        for period in PERIODS:
            c,m=combined(curves[spot][period],curves[future][period]);report['account_comparisons'][label][period]=m
            c.to_csv(OUT/f'equity_account_{label}_{period}.csv',index=False)
    for p,d in PERIODS.items():report['benchmarks'][p]=benchmark(raw['spot']['BTCUSDT'],*d)
    pd.DataFrame(records).to_csv(OUT/'comparison.csv',index=False)
    pd.DataFrame(yearly).to_csv(OUT/'yearly.csv',index=False)
    pd.DataFrame(decomp).to_csv(OUT/'by_symbol_direction.csv',index=False)
    (OUT/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print('FINISHED',json.dumps(report['gate']),flush=True)

if __name__=='__main__':main()
