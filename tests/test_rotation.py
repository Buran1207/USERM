import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
from userm.data import load_etf_master, load_quotes, load_holdings
from userm.signals import calculate_etf_signals, latest_table, window_series
from userm.stocks import alpha_table


class USERMRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = load_etf_master()
        cls.quotes = load_quotes('etfs')
        cls.signals = calculate_etf_signals(cls.quotes, cls.master)
        cls.calendar = pd.DatetimeIndex(sorted(cls.signals.date.unique()))
        cls.end = cls.calendar.max()

    def test_all_20_etfs(self):
        self.assertEqual(self.master.etf.nunique(), 20)
        self.assertEqual(self.master.groupby('group').size().to_dict(), {'行业':11, '科技主题':9})
        self.assertEqual(self.signals.etf.nunique(), 20)

    def test_slider_changes_returns_and_rank(self):
        d1 = latest_table(self.signals, self.end, self.calendar, 1)
        d7 = latest_table(self.signals, self.end, self.calendar, 7)
        d20 = latest_table(self.signals, self.end, self.calendar, 20)
        self.assertEqual(d1.rel_window.notna().sum(), 20)
        self.assertEqual(d7.rel_window.notna().sum(), 20)
        self.assertEqual(d20.rel_window.notna().sum(), 20)
        a = d1.set_index('etf')['rel_window']
        b = d7.set_index('etf')['rel_window']
        self.assertGreater(float((a-b).abs().max()), 1e-6)
        self.assertTrue((d1.groupby('group').rotation_rank.min() == 1).all())
        self.assertTrue((d20.groupby('group').rotation_rank.min() == 1).all())

    def test_exact_session_reference_matches_chart(self):
        for n in (1, 5, 7, 20, 60):
            table = latest_table(self.signals, self.end, self.calendar, n).set_index('etf')
            chart = window_series(self.signals, 'SMH', self.end, self.calendar, n)
            self.assertAlmostEqual(table.loc['SMH','rel_window'], chart.iloc[-1].rel_window, places=11)
            expected = (table.loc['SMH', 'close'] / table.loc['SMH', 'close_start'] - 1) - (table.loc['SMH', 'benchmark_close'] / table.loc['SMH', 'peer_start'] - 1)
            self.assertAlmostEqual(table.loc['SMH','rel_window'], expected, places=11)

    def test_horizon_boundaries_and_earliest_date(self):
        for n in (0, 61):
            with self.assertRaises(ValueError):
                latest_table(self.signals, self.end, self.calendar, n)
        earliest = latest_table(self.signals, self.calendar.min(), self.calendar, 20)
        self.assertTrue(earliest.rel_window.isna().all())

    def test_no_lookahead(self):
        cut = pd.Timestamp('2025-12-31')
        past_prices = self.quotes.loc[self.quotes.date <= cut]
        prior = calculate_etf_signals(past_prices, self.master)
        full = self.signals[self.signals.date <= cut]
        order = ['etf','date']
        prior = prior.sort_values(order).reset_index(drop=True)
        full = full.sort_values(order).reset_index(drop=True)
        self.assertEqual(len(prior), len(full))
        for column in ('rs_ratio','rs_momentum','rel_5','rel_20','benchmark_close'):
            np.testing.assert_allclose(prior[column], full[column], equal_nan=True, atol=1e-9)
        chosen = self.calendar[self.calendar <= cut]
        a = latest_table(prior, chosen.max(), chosen, 13).set_index('etf')
        b = latest_table(full, chosen.max(), chosen, 13).set_index('etf')
        np.testing.assert_allclose(a.sort_index().rel_window, b.sort_index().rel_window, equal_nan=True)

    def test_stale_etf_not_ranked_or_forward_filled(self):
        # Remove one ETF's last observation while market day is still present.
        d = self.signals[~((self.signals.etf == 'SMH') & (self.signals.date == self.end))]
        result = latest_table(d, self.end, self.calendar, 13).set_index('etf')
        self.assertFalse(bool(result.loc['SMH','fresh']))
        self.assertTrue(pd.isna(result.loc['SMH','rotation_rank']))
        self.assertTrue(pd.isna(result.loc['SMH','rel_window']))
        self.assertEqual(int(result.loc['SMH','age_sessions']), 1)

    def test_holdings_annotation_date_and_bad_date(self):
        h = load_holdings()
        self.assertTrue(pd.Timestamp('2026-11-03') in set(h.holdings_date.dropna()))
        from userm import data
        mock_hold = pd.DataFrame({'etf':['A','B','C'], 'ticker':['X','Y','Z'],
                                  'symbol':['X.N','Y.N','Z.N'], 'weight_pct':[1,2,3],
                                  'holdings_asof':['2026-11-03（网页更新）', 'bad date', None]})
        with patch.object(pd, 'read_csv', return_value=mock_hold):
            parsed = data.load_holdings()
        self.assertEqual(parsed.loc[0, 'holdings_date'], pd.Timestamp('2026-11-03'))
        self.assertTrue(pd.isna(parsed.loc[1,'holdings_date']))
        self.assertTrue(pd.isna(parsed.loc[2,'holdings_date']))

    def test_stock_alpha_slider_and_reference_columns(self):
        stock = load_quotes('stocks')
        h = load_holdings()
        end = min(stock.date.max(), self.end)
        for n in (1, 5, 13, 20, 60):
            result = alpha_table(stock, self.signals, h, end, self.calendar, n)
            self.assertGreater(len(result), 0)
            for col in ('alpha_5','alpha_20','alpha_60','alpha_window','stock_ret_window','etf_ret_window'):
                self.assertIn(col, result)
            valid = result.dropna(subset=['alpha_window'])
            self.assertGreater(len(valid), 0)
            np.testing.assert_allclose(valid.alpha_window, valid.stock_ret_window - valid.etf_ret_window, atol=1e-11)
            self.assertTrue((result.loc[result.fresh, 'age_sessions'] == 0).all())
            self.assertTrue((valid.position.isin(['领先','落后'])).all())

if __name__ == '__main__':
    unittest.main()
