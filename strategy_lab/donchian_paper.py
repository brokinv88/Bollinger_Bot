"""Local Donchian order tickets and paper manager. Public Binance GET only."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError
import pandas as pd
from .scanner import closed_bars,FIXED_COHORT,utc_iso
from .signals import HOUR
from .existing_signals import future_signals,STRATEGIES
from .donchian_paper_core import new_state,equity,order_size,approve,cancel,advance,event,reconcile,blockers

ROOT=Path(__file__).resolve().parent
DEFAULT_BOOK=ROOT/'paper_donchian'
ALLOW={'time','exchangeInfo','klines','fundingRate','markPriceKlines'}

def source_hash():
    return hashlib.sha256(b''.join((ROOT/n).read_bytes() for n in ['donchian_paper.py','donchian_paper_core.py','existing_signals.py','existing_engine.py','engine.py','signals.py'])).hexdigest()

def atomic_json(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)
    fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

@contextmanager
def locked(book):
    book.mkdir(parents=True,exist_ok=True)
    with (book/'.lock').open('a+') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another paper command is running; wait for it to finish')
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)

def load(book,check_hash=True):
    path=book/'state.json'
    if not path.exists():raise ValueError('Chưa có sổ paper. Chạy init trước.')
    s=json.loads(path.read_text())
    if s.get('mode')!='PAPER_ONLY' or s.get('version')!=1:raise ValueError('Not a supported paper ledger')
    if check_hash and s.get('source_hash')!=source_hash():raise ValueError('Mã đã thay đổi từ lúc tạo sổ. Cần kiểm tra/migrate sổ, không tự chạy tiếp với quy tắc khác.')
    reconcile(s)
    return s

class PublicData:
    """No keys, signed requests, arbitrary URLs, or order endpoints."""
    def __init__(self):self.last=0.;self.stopped=False
    def get(self,endpoint,**params):
        if endpoint not in ALLOW:raise ValueError('Only whitelisted public market GET endpoints')
        if self.stopped:raise RuntimeError('Rate limit: remaining requests stopped')
        url='https://fapi.binance.com/fapi/v1/'+endpoint
        if params:url+='?'+urlencode(params)
        for attempt in range(3):
            time.sleep(max(0,.15-(time.monotonic()-self.last)));self.last=time.monotonic()
            try:
                with urlopen(Request(url,headers={'User-Agent':'donchian-paper-readonly/1'}),timeout=25) as response:
                    return json.load(response)
            except HTTPError as e:
                if e.code in (418,429):self.stopped=True;raise RuntimeError(f'Binance HTTP {e.code}; stop and retry later') from e
                if e.code<500 or attempt==2:raise
            except (URLError,TimeoutError,OSError):
                if attempt==2:raise
            time.sleep(.5*(attempt+1))
    def now(self):
        now=int(self.get('time')['serverTime'])
        if abs(now-int(time.time()*1000))>30_000:raise ValueError('Clock differs from Binance by >30 seconds')
        return now

def exchange_rules(item):
    if item.get('status')!='TRADING' or item.get('contractType')!='PERPETUAL' or item.get('marginAsset')!='USDT':
        raise ValueError('Contract unavailable / not USDT perpetual')
    fs={f['filterType']:f for f in item['filters']}
    lot=fs['LOT_SIZE'];market=fs['MARKET_LOT_SIZE'];price=fs['PRICE_FILTER']
    steps=[Decimal(str(f['stepSize'])) for f in [lot,market] if Decimal(str(f['stepSize']))>0]
    scale=10**max(0,*[-x.as_tuple().exponent for x in steps]);step=math.lcm(*[int(x*scale) for x in steps])/scale
    return dict(tradable=True,tick=float(price['tickSize']),min_price=float(price['minPrice']),max_price=float(price['maxPrice']),
                step=step,min_qty=max(float(lot['minQty']),float(market['minQty'])),
                max_qty=min(float(lot['maxQty']),float(market['maxQty'])),
                min_notional=float(fs['MIN_NOTIONAL']['notional']))

def funding_rows(raw):
    if not isinstance(raw,list) or not raw:raise ValueError('Missing actual funding')
    out=[dict(fundingTime=int(x['fundingTime']),fundingRate=float(x['fundingRate']),markPrice=float(x.get('markPrice') or 0)) for x in raw]
    if any(not math.isfinite(x['fundingRate']) for x in out):raise ValueError('Invalid funding')
    return sorted(out,key=lambda x:x['fundingTime'])

def fetch_snapshot(client,s):
    now=client.now();cut=now//HOUR*HOUR
    ex=client.get('exchangeInfo');items={x['symbol']:x for x in ex['symbols']}
    pending={q['symbol'] for q in s['tickets'].values() if q['status']=='QUEUED'}
    active=set(s['positions'])|pending
    if cut-s['cursor']>990*HOUR:raise ValueError('Offline >990 hours. Historical recovery needed; ledger unchanged.')
    data={'now':now,'cut':cut,'symbols':{},'scan_errors':{}}
    for sym in sorted(FIXED_COHORT|active):
        try:
            rules=exchange_rules(items[sym])
            raw4=client.get('klines',symbol=sym,interval='4h',limit=1000,endTime=now)
            h4=closed_bars(raw4,'4h',now,keep=999)
            if len(h4)<200:raise ValueError('Need 200 closed H4 bars')
            # Recent history covers all catch-up hours plus a prior funding event.
            fd=funding_rows(client.get('fundingRate',symbol=sym,limit=1000,endTime=now))
            item=dict(rules=rules,h4=h4.to_dict('records'),funding=fd)
            if sym in active:
                raw1=client.get('klines',symbol=sym,interval='1h',limit=1000,endTime=now)
                rawm=client.get('markPriceKlines',symbol=sym,interval='1h',limit=1000,endTime=now)
                item['h1']=closed_bars(raw1,'1h',now,keep=999).to_dict('records')
                item['mark']=closed_bars(rawm,'1h',now,keep=999).to_dict('records')
            data['symbols'][sym]=item
        except Exception as e:
            if sym in active:raise ValueError(f'{sym}: cannot update held/queued symbol: {e}') from e
            data['scan_errors'][sym]=str(e)
    if not data['symbols']:raise ValueError('All market reads failed: '+str(data['scan_errors']))
    return data

def apply_snapshot(s,data):
    now=data['now'];bars={};marks={};funding={}
    for sym,x in data['symbols'].items():
        funding[sym]=x['funding']
        if 'h1' in x:
            bars[sym]={int(b['open_time']):b for b in x['h1']};marks[sym]={int(b['open_time']):b for b in x['mark']}
    # Advance uses copies: no half-written position/funding state after a failure.
    new=deepcopy(s)
    for q in new['tickets'].values():
        if q['status']=='QUEUED' and q['symbol'] in data['symbols']:q['rules']=data['symbols'][q['symbol']]['rules']
    new=advance(new,bars,funding,marks,data['cut'])
    checks=[]
    for sym,x in data['symbols'].items():
        f=future_signals(pd.DataFrame(x['h4']),pd.DataFrame(x['funding']),STRATEGIES['DON55'])
        r=f.iloc[-1];direction=int(r.signal);available=int(r.available)
        check=dict(symbol=sym,available=available,direction=direction,adx=float(r.adx),atr=float(r.atr),
                   atr_pct=float(r.atr_pct),atr_avg50=float(r.atr_avg50),close=float(r.close),ema50=float(r.ema50),
                   don_high=float(r.don_high),don_low=float(r.don_low),funding_rate=float(r.funding_rate),
                   status='SIGNAL' if direction else 'NO_SIGNAL')
        if not all(math.isfinite(check[k]) for k in ['adx','atr','atr_pct','atr_avg50','close','ema50','don_high','don_low','funding_rate']):
            data['scan_errors'][sym]='Nonfinite signal/funding';continue
        checks.append(check)
        if not direction:continue
        tid=f'{sym}-{available}-{direction}'
        if tid in new['tickets']:continue
        status='READY' if (now//HOUR+1)*HOUR<available+4*HOUR else 'EXPIRED'
        new['tickets'][tid]=dict(id=tid,symbol=sym,direction=direction,available=available,expires=available+4*HOUR,
                                observed_at=now,status=status,reference=float(r.close),atr=float(r.atr),rules=x['rules'],evidence=check)
        event(new,now,'TICKET_CREATED',ticket=tid,status=status)
    new['scan']=checks;new['scan_errors']=data['scan_errors'];new['last_refresh']=now
    reconcile(new)
    return new

def fmt_time(t):
    return pd.Timestamp(t,unit='ms',tz='UTC').tz_convert('Asia/Ho_Chi_Minh').strftime('%d/%m/%Y %H:%M:%S')

def export(book,s):
    now=int(time.time()*1000);eq=equity(s);c=s['config'];problems=blockers(s,now)
    failed=None
    if (book/'last_error.json').exists():
        err=json.loads((book/'last_error.json').read_text())
        if err.get('time_ms',0)>=(s.get('last_refresh') or 0):failed=err['error']
    rows=['# Donchian H4 — phiếu lệnh và sổ PAPER','',
          '**CHỈ MÔ PHỎNG. Không có kết nối đặt lệnh hoặc API key.**','',
          '**LẦN CẬP NHẬT GẦN NHẤT LỖI — dữ liệu dưới đây là lần thành công trước:** '+failed if failed else 'Trạng thái: đã xuất từ sổ paper; xem mốc dữ liệu bên dưới.',
          f"Vốn đầu: ${c['capital']:.2f} · Equity tại nến H1 đã xử lý: **${eq:.2f}** · Tiền mặt: ${s['cash']:.2f}",
          f"Dữ liệu sổ đến: **{fmt_time(s['cursor'])} giờ Việt Nam**. Đây không phải equity realtime.",
          f"Risk/lệnh {100*c['risk']:.2f}% · Tổng risk ≤{100*c['total_risk']:.2f}% · Tối đa {c['max_positions']} vị thế · Đòn bẩy mô hình {c['leverage']:g}x.",
          f"Chặn vào mới: {', '.join(problems) or 'Không có tại lúc xuất báo cáo'}.",'',
          'Duyệt phiếu sẽ xếp mô phỏng vào OPEN H1 kế tiếp, nằm trước lần đóng H4 tiếp theo. Giá lệch quá '+str(c['max_drift_atr'])+' ATR so với close tín hiệu sẽ bỏ lệnh. Đây là phiên bản vào trễ cần kiểm chứng riêng, không mang kết quả backtest next-open H4 sang đây.',
          '', '## Phiếu đang chờ','',
          '| Coin / hướng | Trạng thái | Close tín hiệu | SL / TP dự kiến | Qty / Notional | Risk / Margin ($) | H1 dự kiến |','|---|---|---|---|---|---|---|']
    ticket_rows=[];details=[]
    for q in sorted(s['tickets'].values(),key=lambda q:q['available'],reverse=True):
        if q['status'] not in ('READY','QUEUED'):continue
        status=q['status']
        if status=='READY' and (now//HOUR+1)*HOUR>=q['expires']:status='EXPIRED'
        preview={};why=''
        try:preview=order_size(q['reference']*(1+q['direction']*c['slip']),q['atr'],q['direction'],min(eq*c['risk'],q.get('reserved_risk',eq*c['risk'])),q['rules'],c)
        except ValueError as e:why=str(e)
        p=preview;when=q.get('entry_at',(now//HOUR+1)*HOUR)
        levels=f"{p['stop']:.8g} / {p['target']:.8g}" if p else 'Chưa đủ điều kiện'
        size=f"{p['qty']:.8g} / ${p['notional']:.2f}" if p else '—'
        risk=f"{p['initial_risk']:.2f} / {p['margin']:.2f}" if p else '—'
        rows.append(f"| {q['symbol']} {'LONG' if q['direction']==1 else 'SHORT'} | {status} | {q['reference']:.8g} | {levels} | {size} | {risk} | {fmt_time(when)} |")
        details+=['',f"ID: `{q['id']}`. Tín hiệu đóng {fmt_time(q['available'])}; hết hạn {fmt_time(q['expires'])}." ,f"ADX {q['evidence']['adx']:.2f}; ATR% {q['evidence']['atr_pct']:.3f} > TB50 {q['evidence']['atr_avg50']:.3f}; funding tại đầu H4 {q['evidence']['funding_rate']*100:+.4f}%.",f"{why or 'SL/TP/qty là dự kiến theo close tín hiệu; khi mô phỏng khớp sẽ tính lại theo open H1 và equity lúc đó.'}",'']
        ticket_rows.append({**{k:v for k,v in q.items() if k not in ['rules','evidence']},**preview,'preview_error':why})
    if not ticket_rows:rows+=['| — | Không có phiếu chờ | — | — | — | — | — |','']
    rows+=details+['']
    rows+=['## Vị thế paper','', '| Coin | Hướng | Entry | Qty | SL hiện tại | TP | Funding đã trả ($) |','|---|---|---|---|---|---|---|']
    for sym,p in s['positions'].items():rows.append(f"| {sym} | {'LONG' if p['direction']==1 else 'SHORT'} | {p['entry']:.8g} | {p['qty']:.8g} | {p['stop']:.8g} | {p['target']:.8g} | {p['funding']:+.4f} |")
    if not s['positions']:rows.append('| — | Chưa có vị thế | — | — | — | — | — |')
    net=sum(t['net_pnl'] for t in s['trades']);rows+=['','## Nhật ký','',f"Đã đóng {len(s['trades'])} lệnh; net PnL đã đóng ${net:+.4f}. Đối soát tiền: sai lệch ${reconcile(s):.10f}.",
    'Xem trades.csv, equity.csv và events.jsonl trong cùng thư mục. Bỏ phiếu cũng có nhật ký. Không dùng số liệu này như lịch sử lệnh trên Binance.',
    '', '## Bộ lọc mới nhất','', '| Coin | Hướng tín hiệu | ADX | ATR% |','|---|---|---|---|']
    for x in s.get('scan',[]):rows.append(f"| {x['symbol']} | { {1:'LONG',-1:'SHORT',0:'Không có'}[x['direction']] } | {x['adx']:.2f} | {x['atr_pct']:.3f} |")
    rows+=['','## Dữ liệu thiếu/lỗi','']
    rows+=['- '+k+': '+v for k,v in s.get('scan_errors',{}).items()] or ['Không có lỗi ở lần quét thành công gần nhất.']
    rows+=['','## Cách vận hành','',
           'Mở run_donchian_paper.command → 1 để cập nhật → 2 để xem/duyệt phiếu → 1 sau mỗi giờ để cập nhật vị thế. Không tự chạy khi ứng dụng đóng; lần sau sẽ đọc bù các H1 đã đóng. Stop/TP là mô phỏng H1, không phải stop thật tại sàn.',
           'Dừng ngày/tuần dùng UTC, tính cả lãi/lỗ chưa thực hiện theo close H1. DD 5% khóa mở mới để rà soát; vị thế hiện tại vẫn được mô phỏng SL/TP. Chưa mô hình thanh lý chính xác, không tự đóng toàn bộ để giả định tránh thanh lý.',
           'Phí giả định 0,05% mỗi chiều và trượt 0,03% mỗi chiều; funding thực từng sự kiện. Không cam kết khớp giá hoặc thời điểm giống tiền thật.']
    (book/'PAPER_DESK_VI.md').write_text('\n'.join(rows)+'\n')
    pd.DataFrame(ticket_rows,columns=None if ticket_rows else ['id','symbol','status']).to_csv(book/'tickets.csv',index=False)
    pd.DataFrame(s['trades'],columns=None if s['trades'] else ['symbol','entry_time','exit_time','net_pnl']).to_csv(book/'trades.csv',index=False)
    pd.DataFrame(s['curve'],columns=None if s['curve'] else ['time','equity','cash','positions']).to_csv(book/'equity.csv',index=False)
    (book/'events.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in s['events']))

def refresh(book):
    with locked(book):
        s=load(book);client=PublicData();data=fetch_snapshot(client,s);new=apply_snapshot(s,data)
        raw=json.dumps(data,sort_keys=True,allow_nan=False).encode();digest=hashlib.sha256(raw).hexdigest()
        cache=book/'snapshots';cache.mkdir(exist_ok=True)
        path=cache/(digest+'.json.gz')
        if not path.exists():
            with gzip.open(path,'wb') as f:f.write(raw)
        new['snapshot']=str(path.name);event(new,data['now'],'REFRESH',snapshot=path.name,scan_errors=data['scan_errors'])
        atomic_json(book/'state.json',new);export(book,new)
        print(f"Đã cập nhật đến {fmt_time(new['cursor'])}. Equity ${equity(new):.2f}; {len(new['positions'])} vị thế; {len(new['trades'])} lệnh đóng.")
        return new

def record_error(book,error):
    if not (book/'state.json').exists():return
    try:
        with locked(book):
            atomic_json(book/'last_error.json',dict(time_ms=int(time.time()*1000),error=str(error)))
            export(book,load(book,check_hash=False))
    except (ValueError,OSError):pass  # Never overwrite a ledger owned by another process.

def action(book,kind,tid=None):
    with locked(book):
        s=load(book);now=int(time.time()*1000)
        if kind=='approve':q=approve(s,tid,now);print('Đã xếp PAPER tại H1:',fmt_time(q['entry_at']))
        elif kind=='skip':cancel(s,tid,now)
        elif kind in ('pause','resume'):
            # No retrospectively changing pending entries after their scheduled open.
            if any(q['status']=='QUEUED' and now>=q['entry_at'] for q in s['tickets'].values()):raise ValueError('Refresh before changing pause state')
            if kind=='pause':
                for q in list(s['tickets'].values()):
                    if q['status']=='QUEUED':cancel(s,q['id'],now,'MANUAL_PAUSE')
            s['paused']=kind=='pause';event(s,now,kind.upper())
        atomic_json(book/'state.json',s);export(book,s)

def init(book,capital=1000.,risk=.0025):
    with locked(book):
        if (book/'state.json').exists():raise ValueError('Sổ đã tồn tại; không ghi đè hoặc reset lịch sử.')
        s=new_state(int(time.time()*1000),dict(capital=capital,risk=risk));s['source_hash']=source_hash()
        atomic_json(book/'state.json',s);export(book,s)
        print(f'Đã tạo ví PAPER ${capital:.2f}, risk {risk*100:.2f}%: {book}')

def menu(book):
    if not (book/'state.json').exists():init(book)
    while True:
        print('\nDONCHIAN PAPER — không đặt lệnh Binance\n1. Cập nhật dữ liệu và vị thế\n2. Xem / duyệt / bỏ phiếu\n3. Xem sổ tóm tắt\n4. Tạm dừng nhận lệnh mới\n5. Bỏ tạm dừng thủ công (không xóa khóa rủi ro)\n0. Thoát')
        try:
            choice=input('Chọn: ').strip()
            if choice=='0':return
            if choice=='1':refresh(book)
            elif choice=='2':
                s=refresh(book);now=int(time.time()*1000)
                qs=[q for q in s['tickets'].values() if q['status']=='READY' and (now//HOUR+1)*HOUR<q['expires']]
                for i,q in enumerate(qs,1):
                    print(f"{i}. {q['symbol']} {'LONG' if q['direction']==1 else 'SHORT'} | close {q['reference']:.8g} | ATR {q['atr']:.8g}")
                    try:
                        p=order_size(q['reference']*(1+q['direction']*s['config']['slip']),q['atr'],q['direction'],equity(s)*s['config']['risk'],q['rules'],s['config'])
                        print(f"   SL {p['stop']:.8g} | TP {p['target']:.8g} | qty {p['qty']:.8g} | risk ${p['initial_risk']:.2f} | margin ${p['margin']:.2f}")
                    except ValueError as e:print('   CHƯA THỂ VÀO:',e)
                if not qs:print('Không có phiếu còn hạn. Không cần tạo lệnh.');continue
                answer=input('Số phiếu để xử lý (Enter quay lại): ').strip()
                if not answer:continue
                index=int(answer)
                if not 1<=index<=len(qs):raise ValueError('Số phiếu không hợp lệ')
                q=qs[index-1]
                answer=input(f"{q['symbol']}: gõ PAPER để duyệt, BO để bỏ, Enter để quay lại: ").strip().upper()
                if answer=='PAPER':action(book,'approve',q['id'])
                elif answer=='BO':action(book,'skip',q['id'])
            elif choice=='3':
                with locked(book):s=load(book,check_hash=False);export(book,s)
                print((book/'PAPER_DESK_VI.md').read_text())
            elif choice in ('4','5'):action(book,'pause' if choice=='4' else 'resume')
        except (ValueError,RuntimeError,OSError,IndexError,KeyError) as e:
            print('Chưa thực hiện:',e);record_error(book,e)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--book',type=Path,default=DEFAULT_BOOK)
    sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('init');a.add_argument('--capital',type=float,default=1000.);a.add_argument('--risk',type=float,default=.0025)
    for name in ['refresh','status','menu','pause','resume']:sub.add_parser(name)
    for name in ['approve','skip']:a=sub.add_parser(name);a.add_argument('ticket_id')
    a=p.parse_args();book=a.book.resolve()
    try:
        if a.cmd=='init':init(book,a.capital,a.risk)
        elif a.cmd=='refresh':refresh(book)
        elif a.cmd=='menu':menu(book)
        elif a.cmd=='status':
            with locked(book):s=load(book,check_hash=False);export(book,s)
            print((book/'PAPER_DESK_VI.md').read_text())
        else:action(book,a.cmd,getattr(a,'ticket_id',None))
    except KeyboardInterrupt:
        print('\nĐã thoát. Sổ paper đã lưu vẫn còn nguyên.');return 0
    except Exception as e:
        print(f'LỖI — không tiếp tục mô phỏng: {e}')
        record_error(book,e)
        return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
