from __future__ import annotations
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
import csv

from scripts import refresh_data as refresh


class ETFRefreshTests(unittest.TestCase):
    def test_nyse_intraday_cutoff(self):
        # Nov 10 2026 is a regular session, closes 21:00 UTC; buffer to 22:30.
        self.assertEqual(refresh.last_safe_session(datetime(2026,11,10,20,59,tzinfo=timezone.utc)), '2026-11-09')
        self.assertEqual(refresh.last_safe_session(datetime(2026,11,10,21,15,tzinfo=timezone.utc)), '2026-11-09')
        self.assertEqual(refresh.last_safe_session(datetime(2026,11,10,22,31,tzinfo=timezone.utc)), '2026-11-10')

    def test_nyse_early_close_and_holiday(self):
        # Friday after Thanksgiving (2026-11-27): closes 13:00 ET -> 18:00 UTC.
        self.assertEqual(refresh.last_safe_session(datetime(2026,11,27,19,20,tzinfo=timezone.utc)), '2026-11-25')
        self.assertEqual(refresh.last_safe_session(datetime(2026,11,27,19,31,tzinfo=timezone.utc)), '2026-11-27')
        self.assertEqual(refresh.last_safe_session(datetime(2026,11,28,20,0,tzinfo=timezone.utc)), '2026-11-27')

    def test_only_etf_rows_and_cutoff(self):
        class FakeSource:
            def resolve(self,ticker):
                return ticker+'.P'
            def iter_bars(self,symbol):
                for date in ['2026-11-06','2026-11-09','2026-11-10']:
                    yield dict(date=date,open='50',high='51',low='49',close='50',volume='1000'),'OOS'
        mapped,rows,info=refresh.make_snapshot(FakeSource(),'2026-11-09')
        self.assertEqual(len(mapped),20)
        self.assertEqual(len(rows),40)
        self.assertEqual(info['max_date'],'2026-11-09')
        self.assertTrue(all(r['date']!='2026-11-10' for r in rows))
        self.assertNotIn('stocks',info)

    def test_partial_latest_day_not_published(self):
        class PartialSource:
            def resolve(self,ticker):
                return ticker+'.P'
            def iter_bars(self,symbol):
                yield dict(date='2026-11-06',close='50'), 'OOS'
                if symbol.startswith('XLC'):
                    yield dict(date='2026-11-09',close='51'), 'OOS'
        _,rows,info=refresh.make_snapshot(PartialSource(),'2026-11-09')
        self.assertEqual(info['max_date'],'2026-11-06')
        self.assertEqual(len(rows),20)

    def test_reject_downgrade_preserves_existing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'snapshot_manifest.json').write_text('{"etfs":{"max_date":"2026-11-09"}}')
            (root/'etf_prices.csv.gz').write_bytes(b'original')
            with patch.object(refresh,'DATA',root):
                with self.assertRaisesRegex(RuntimeError,'refusing downgrade'):
                    refresh.publish({'BAI':'BAI.P'},[],{'max_date':'2026-11-06'},'2026-11-06','test')
            self.assertEqual((root/'etf_prices.csv.gz').read_bytes(),b'original')


if __name__=='__main__':
    unittest.main()
