r"""Offline import of preexisting CPS:2 iFinD CSV.GZ files into small GitHub dashboard snapshots.

Windows example:
 py -3.12 scripts\refresh_data.py --source C:\code\DATA\US\data
For shipped test/snapshot creation from an uploaded archive:
 python scripts/refresh_data.py --cps2-zip /path/cps2_adjusted.zip

No download, web, login, quota use, training or modification of source data.
"""
from __future__ import annotations
import argparse,csv,gzip,io,json,re,sys,zipfile
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
COLUMNS=['date','symbol','open','high','low','close','volume','partition']


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


class Source:
    def __init__(self, source:Path|None, zipname:Path|None):
        self.archive=zipfile.ZipFile(zipname) if zipname else None
        if self.archive:
            self.root=str(zipname)
            paths=[n for n in self.archive.namelist() if n.lower().endswith('.csv.gz')]
        else:
            if not source or not source.exists():raise FileNotFoundError(f'Missing source directory: {source}')
            self.root=str(source)
            paths=list(source.rglob('*.csv.gz'))
        self.record={}; self.symbols=defaultdict(set)
        for p in paths:
            name=str(p).replace('\\','/')
            m=re.search(r'/(train|oos)/(20\d\d)/([^/]+\.csv\.gz)$',name,re.I)
            if not m: continue
            partition,yr,basename=m.groups()
            sym=basename[:-7].upper()  # strip '.csv.gz'
            self.record[(sym,int(yr),partition.lower())]=p
            self.symbols[sym.rsplit('.',1)[0]].add(sym)
        print('Indexed',len(self.record),'symbol-year files, unique symbols',len(set(k[0] for k in self.record)))
    def read(self,path):
        raw=self.archive.read(path) if self.archive else Path(path).read_bytes()
        return csv.DictReader(io.StringIO(gzip.decompress(raw).decode('utf-8-sig',errors='replace')))
    def bars(self,symbol):
        for key in sorted(k for k in self.record if k[0]==symbol):
            _,year,part=key
            if (year < 2026 and part!='train') or (year >= 2026 and part!='oos'):
                continue
            for row in self.read(self.record[key]):
                yield row,part.upper()
    def resolve(self,base,known=None):
        base=str(base).upper().strip(); known=known or set()
        if base in known:return base
        choices=self.symbols.get(base,())
        if not choices: return ''
        matching=sorted([s for s in choices if s in known]);
        if len(matching)==1:return matching[0]
        # Used for top-5 research only; ambiguous symbols are excluded, never guessed.
        return next(iter(choices)) if len(choices)==1 else ''
    def close(self):
        if self.archive:self.archive.close()


def export_symbol_snapshot(path:Path,symbols,source:Source):
    rows=0;bad=0; latest={}; bypart={'TRAIN':0,'OOS':0}; found=set()
    with gzip.open(path,'wt',encoding='utf-8',newline='',compresslevel=1) as handle:
        wr=csv.DictWriter(handle,fieldnames=COLUMNS,lineterminator='\n');wr.writeheader()
        for symbol in sorted(symbols):
            for raw,part in source.bars(symbol):
                try:
                    dt=str(raw.get('date','')).strip()[:10]
                    close=float(raw['close'])
                    if not (2020<=int(dt[:4])<=2100 and close>0): raise ValueError('bad price/date')
                    day=dict(date=dt,symbol=symbol,open=raw.get('open',''),high=raw.get('high',''),low=raw.get('low',''),close=raw.get('close',''),volume=raw.get('volume',''),partition=part)
                    wr.writerow(day);rows+=1;bypart[part]+=1;found.add(symbol)
                    if dt>latest.get(symbol,''): latest[symbol]=dt
                except (ValueError,KeyError,TypeError):bad+=1
    return {'rows':rows,'symbols_found':len(found),'symbols_requested':len(symbols),'invalid_rows':bad,'partition_rows':bypart,'max_date':max(latest.values(),default=''),'latest_by_symbol':latest}


def run(opts):
    source=Source(Path(opts.source) if opts.source else None,Path(opts.cps2_zip) if opts.cps2_zip else None)
    DATA.mkdir(parents=True,exist_ok=True)
    etfs=read_csv(DATA/'etfs.csv')
    etf_resolve={r['etf']:source.resolve(r['etf']) for r in etfs}
    not_found=[etf for etf,code in etf_resolve.items() if not code]
    if not_found:print('WARNING ETF missing:',not_found)
    index=read_csv(DATA/'index_constituents_snapshot.csv')
    names={r['symbol']:r['name_zh'] for r in index}
    idx=set(names)
    known=idx|set(etf_resolve.values())
    holdings=read_csv(DATA/'holdings_snapshot_raw.csv')
    holding_records=[];extra=set()
    for r in holdings:
        symbol=source.resolve(r['ticker'],known)
        # Index files may be missing; unresolved foreign holdings have blank symbol.
        if symbol and symbol not in etf_resolve.values():extra.add(symbol)
        holding_records.append(dict(etf=r['etf'],ticker=r['ticker'],symbol=symbol,weight_pct=r['weight_pct'],raw_description=r['raw_description'],holdings_asof=r['holdings_asof']))
    with (DATA/'holdings_snapshot.csv').open('w',newline='',encoding='utf-8-sig') as out:
        wr=csv.DictWriter(out,fieldnames=list(holding_records[0].keys()));wr.writeheader();wr.writerows(holding_records)
    with (DATA/'etf_codes.csv').open('w',newline='',encoding='utf-8-sig') as out:
        wr=csv.writer(out);wr.writerow(['etf','symbol']);wr.writerows(sorted(etf_resolve.items()))
    stock_symbols=(idx|extra)-{''}
    with (DATA/'stock_master.csv').open('w',newline='',encoding='utf-8-sig') as out:
        wr=csv.writer(out);wr.writerow(['symbol','name_zh','source_list']);
        for code in sorted(stock_symbols):
            cats=','.join(sorted({r['index_name'] for r in index if r['symbol']==code})) or 'ETF top5 snapshot'
            wr.writerow([code,names.get(code,code.split('.')[0]),cats])
    info_etf=export_symbol_snapshot(DATA/'etf_prices.csv.gz',{s for s in etf_resolve.values() if s},source)
    print('ETFs',info_etf['rows'],info_etf['symbols_found'],'latest',info_etf['max_date'])
    # Keep each file under GitHub's 25 MiB browser upload cap.
    ordered=sorted(stock_symbols)
    half=(len(ordered)+1)//2
    stock_parts=[]
    for n, group in enumerate((ordered[:half], ordered[half:]), start=1):
        stock_parts.append(export_symbol_snapshot(DATA/f'stock_prices_part{n}.csv.gz',group,source))
    old=DATA/'stock_prices.csv.gz'
    if old.exists():old.unlink()
    info_stock={'rows':sum(p['rows'] for p in stock_parts),
                'symbols_found':sum(p['symbols_found'] for p in stock_parts),
                'symbols_requested':sum(p['symbols_requested'] for p in stock_parts),
                'invalid_rows':sum(p['invalid_rows'] for p in stock_parts),
                'partition_rows':{k:sum(p['partition_rows'][k] for p in stock_parts) for k in ('TRAIN','OOS')},
                'max_date':max(p['max_date'] for p in stock_parts),
                'latest_by_symbol':{k:v for p in stock_parts for k,v in p['latest_by_symbol'].items()}}
    print('Stocks',info_stock['rows'],info_stock['symbols_found'],'latest',info_stock['max_date'])
    doc={'name':'USERM snapshot','schema':'USERM-v1','generated_utc':datetime.now(timezone.utc).isoformat(),
         'source':'preexisting local CPS:2 yearly files; no API extraction','source_path_type':'archive' if opts.cps2_zip else 'local directory',
         'adjustment':'CPS:2 as labeled by source; total-return treatment NOT independently verified',
         'point_in_time':'ETF holdings are one 2026-11-02 snapshot, index membership provided as current, historical membership NOT verified',
         'metadata_bd':'not used for historical signal generation; uploaded BD explicitly PIT-unverified',
         'etfs':info_etf,'stocks':info_stock,'warnings':not_found}
    (DATA/'snapshot_manifest.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    source.close()
    print('Done:',DATA,'Stock quote parts MiB',[(p.name,round(p.stat().st_size/1024**2,2)) for p in DATA.glob('stock_prices_part*.csv.gz')])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--source',help=r'C:\code\DATA\US\data (must contain cps2_adjusted/train + oos)')
    group.add_argument('--cps2-zip',help='Existing offline CPS2 archive, read without extracting')
    args=p.parse_args()
    run(args)
