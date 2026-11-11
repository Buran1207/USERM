from __future__ import annotations
import csv
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import pytest

from scripts import refresh_data as refresh
from userm.benchmarks import load_spy


def test_nyse_intraday_cutoff():
    assert refresh.last_safe_session(datetime(2026,11,10,20,59,tzinfo=timezone.utc)) == '2026-11-09'
    assert refresh.last_safe_session(datetime(2026,11,10,21,15,tzinfo=timezone.utc)) == '2026-11-09'
    assert refresh.last_safe_session(datetime(2026,11,10,22,31,tzinfo=timezone.utc)) == '2026-11-10'


def test_nyse_early_close_and_holiday():
    assert refresh.last_safe_session(datetime(2026,11,27,19,20,tzinfo=timezone.utc)) == '2026-11-25'
    assert refresh.last_safe_session(datetime(2026,11,27,19,31,tzinfo=timezone.utc)) == '2026-11-27'
    assert refresh.last_safe_session(datetime(2026,11,28,20,0,tzinfo=timezone.utc)) == '2026-11-27'


class FakeSource:
    def resolve(self, ticker):
        return ticker+'.P'
    def iter_bars(self, symbol):
        for date in ['2026-11-06','2026-11-09','2026-11-10']:
            yield {'date':date,'open':'50','high':'51','low':'49','close':'50','volume':'1000'},'OOS'


def test_20_etfs_and_spy_excluded_after_cutoff():
    fake=FakeSource()
    mapped,rows,info=refresh.make_snapshot(fake,'2026-11-09')
    # Only two bars of fake SPY does not satisfy warm-up threshold.
    with pytest.raises(RuntimeError, match='at least 50'):
        refresh.make_spy_snapshot(fake, '2026-11-09', info['max_date'])
    assert len(mapped)==20
    assert len(rows)==40
    assert all(r['date'] != '2026-11-10' for r in rows)
    assert 'SPY' not in mapped


def test_spy_requires_sufficient_history_and_matching_latest():
    class Source:
        def resolve(self,ticker):
            return ticker+'.P'
        def iter_bars(self,symbol):
            for date in pd.bdate_range('2026-08-03','2026-11-10'):
                yield {'date':str(date.date()),'close':'550'},'OOS'
    spy_rows, info = refresh.make_spy_snapshot(Source(),'2026-11-09','2026-11-09')
    assert info['rows'] > 50
    assert spy_rows[-1]['date']=='2026-11-09'
    assert all(r['date'] != '2026-11-10' for r in spy_rows)
    with pytest.raises(RuntimeError, match='misaligned'):
        refresh.make_spy_snapshot(Source(),'2026-11-06','2026-11-10')


def test_partial_etf_latest_session_not_published():
    class PartialSource:
        def resolve(self,ticker):
            return ticker+'.P'
        def iter_bars(self,symbol):
            yield {'date':'2026-11-06','close':'50'}, 'OOS'
            if symbol.startswith('XLC'):
                yield {'date':'2026-11-09','close':'51'}, 'OOS'
    _, rows, info = refresh.make_snapshot(PartialSource(),'2026-11-09')
    assert info['max_date']=='2026-11-06'
    assert len(rows)==20


def test_downgrade_rejected_preserves_existing():
    with TemporaryDirectory() as temp:
        root=Path(temp)
        (root/'snapshot_manifest.json').write_text('{"etfs":{"max_date":"2026-11-09"}}')
        (root/'etf_prices.csv.gz').write_bytes(b'original')
        spy_rows=[{'date':'2026-11-06','close':500}]
        with patch.object(refresh,'DATA',root):
            with pytest.raises(RuntimeError, match='refusing downgrade'):
                refresh.publish({'BAI':'BAI.P'}, [], {'max_date':'2026-11-06'},
                                '2026-11-06','test',spy_rows,{'max_date':'2026-11-06'})
        assert (root/'etf_prices.csv.gz').read_bytes()==b'original'


def test_publish_21_aligned_and_read_spy():
    with TemporaryDirectory() as temp:
        root=Path(temp)
        mappings={f'S{i:02}':f'S{i:02}.P' for i in range(20)}
        quotes=[{'date':'2026-11-09','symbol':code,'open':3,'high':4,'low':2,
                 'close':3,'volume':300,'partition':'OOS'} for code in mappings.values()]
        spy=[{'date':str(x.date()),'close':500+i}
             for i,x in enumerate(pd.bdate_range('2026-08-03','2026-11-09'))]
        info={'rows':len(quotes),'symbols_found':20,'min_date':'2026-11-09',
              'max_date':'2026-11-09','partition_rows':{'OOS':20}}
        si={'rows':len(spy),'max_date':'2026-11-09','min_date':spy[0]['date'],'symbol':'SPY.P'}
        with patch.object(refresh,'DATA',root):
            refresh.publish(mappings,quotes,info,'2026-11-09','test',spy,si)
        loaded=load_spy(root/'spy_prices.csv.gz')
        assert loaded is not None and loaded.index.max() == pd.Timestamp('2026-11-09')
        etf=pd.read_csv(root/'etf_prices.csv.gz')
        assert 'SPY.P' not in etf.symbol.tolist()
        assert len(etf)==20
        assert (root/'snapshot_manifest.json').exists()


def test_missing_spy_does_not_silently_fallback():
    assert load_spy(Path('/tmp/THIS_SHOULD_NOT_EXIST_4545.csv.gz')) is None
