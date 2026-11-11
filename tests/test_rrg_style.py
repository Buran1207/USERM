import numpy as np
import pandas as pd
import pytest
from userm.rrg import (RRG_SMA, RRG_LEGACY, rrg_series,
                        attach_common_rrg)
from userm.data import load_quotes, load_etf_master, table
from userm.signals import calculate_etf_signals, latest_table


def _example(n=110):
    dates = pd.bdate_range('2026-01-05', periods=n)
    bench = pd.Series(np.exp(np.arange(n) * .002), index=dates)
    asset = bench * np.exp(np.arange(n) * .003)
    return dates, asset, bench


def test_flat_relative_100():
    dates, asset, bench = _example()
    for method in [RRG_SMA, RRG_LEGACY]:
        res = rrg_series(asset/2, bench, method)
        assert res.rs_ratio.iloc[-1] > 100  # relative uptrend detected
    res = rrg_series(bench * 1.52, bench, RRG_SMA)
    assert res.rs_ratio.iloc[-1] == pytest.approx(100)
    assert res.rs_momentum.iloc[-1] == pytest.approx(100)


def test_future_cannot_change_historical_rrg():
    _, asset, bench = _example()
    for method in [RRG_SMA, RRG_LEGACY]:
        full = rrg_series(asset, bench, method)
        past = rrg_series(asset.iloc[:-15], bench.iloc[:-15], method)
        pd.testing.assert_frame_equal(full.iloc[:-15], past)


def test_missing_benchmark_does_not_forward_fill():
    dates, asset, bench = _example()
    bench.iloc[-1] = np.nan
    res = rrg_series(asset, bench)
    assert np.isnan(res.rs_ratio.iloc[-1])
    assert res.quadrant.iloc[-1] == 'NA'


def test_method_different_but_tail_no_effect():
    _, asset, bench = _example()
    x = rrg_series(asset,bench,RRG_SMA)
    # changing displayed tail is just slicing; end coordinate must be stable
    assert x.tail(5).iloc[-1].rs_ratio == x.tail(20).iloc[-1].rs_ratio
    assert x.tail(5).iloc[-1].rs_momentum == x.tail(20).iloc[-1].rs_momentum


def test_common_benchmark_and_peer_rank_independent():
    q=load_quotes(); master=load_etf_master(); maps=table('etf_codes.csv')
    orig=calculate_etf_signals(q, master)
    prices=q[q.symbol==maps.loc[maps.etf=='VGT','symbol'].iloc[0]].set_index('date')['close']
    bench=prices.rename('close')
    modified=attach_common_rrg(orig,q,maps,bench,RRG_SMA)
    assert len(modified)==len(orig)
    assert modified['rs_ratio'].notna().sum() > 30000
    calendar=pd.DatetimeIndex(sorted(modified.date.unique()))
    one=latest_table(orig,calendar[-1],calendar,20)
    two=latest_table(modified,calendar[-1],calendar,20)
    pd.testing.assert_frame_equal(one[['etf','rotation_rank','rel_window']],
                                  two[['etf','rotation_rank','rel_window']])
    assert modified.loc[modified.etf=='BOTZ','rs_ratio'].iloc[-1] != pytest.approx(
        orig.loc[orig.etf=='BOTZ','rs_ratio'].iloc[-1])


def test_spy_versus_spx_not_interchangeable():
    # Two different benchmarks must generally produce different coordinates.
    dates, asset, spy = _example()
    spx = spy * np.exp(np.arange(len(spy)) * .002)
    x_spy=rrg_series(asset,spy,RRG_SMA)
    x_spx=rrg_series(asset,spx,RRG_SMA)
    assert x_spy.rs_ratio.iloc[-1] != pytest.approx(x_spx.rs_ratio.iloc[-1])
