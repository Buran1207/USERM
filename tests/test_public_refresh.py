from datetime import datetime, timezone
from pathlib import Path
import shutil
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from scripts import refresh_public as p


def test_dst_and_early_close():
    assert p.last_safe_session(datetime(2026,11,18,21,19,tzinfo=timezone.utc),20)=='2026-11-17'
    assert p.last_safe_session(datetime(2026,11,18,21,20,tzinfo=timezone.utc),20)=='2026-11-18'
    assert p.last_safe_session(datetime(2026,7,9,20,20,tzinfo=timezone.utc),20)=='2026-07-09'
    assert p.last_safe_session(datetime(2026,11,27,18,20,tzinfo=timezone.utc),20)=='2026-11-27'


def frame(dates):
    n=len(dates); c=100+np.arange(n)/10
    return pd.DataFrame({'Open':c-0.1,'High':c+1,'Low':c-1,'Close':c,
        'Adj Close':c*np.linspace(.8,.95,n),'Volume':1000}, index=dates)


def test_normalized_adjustment_and_cutoff():
    dates=p.sessions('2026-11-13','2026-11-19')
    raw=frame(dates); out=p.normalize(raw,'XLC.P','2026-11-18',dates[:-1]);
    assert out.date.iloc[-1]=='2026-11-18'
    assert out.close.iloc[-1]==pytest.approx(raw.Close.iloc[-2])
    assert out.close.iloc[0]==pytest.approx(raw['Adj Close'].iloc[0]/(raw['Adj Close'].iloc[-2]/raw.Close.iloc[-2]))
    assert out.volume.eq(1000).all() and out.partition.eq('OOS').all()
    assert list(out)==p.COLS


def test_missing_and_invalid_rejected():
    dates=p.sessions('2026-11-13','2026-11-19'); raw=frame(dates)
    with pytest.raises(ValueError,match='missing target'):
        p.normalize(raw.iloc[:-1],'SPY.P','2026-11-19',[])
    with pytest.raises(ValueError,match='calendar gap'):
        p.normalize(raw.drop(dates[1]),'SPY.P','2026-11-19',[])
    with pytest.raises(ValueError,match='would lose'):
        p.normalize(raw.drop(dates[1]),'SPY.P','2026-11-19',dates)
    raw.iloc[0,0]=np.nan
    with pytest.raises(ValueError,match='nonfinite'):
        p.normalize(raw,'SPY.P','2026-11-19',[])


def test_end_to_end_and_failure(tmp_path):
    for f in ('etf_prices.csv.gz','spy_prices.csv.gz','snapshot_manifest.json','etfs.csv','etf_codes.csv'):
        shutil.copy2(p.DATA/f,tmp_path/f)
    old=pd.read_csv(tmp_path/'etf_prices.csv.gz'); starts=old.groupby('symbol').date.min().to_dict()
    mapping=pd.read_csv(tmp_path/'etf_codes.csv'); start={e:starts[s] for e,s in zip(mapping.etf,mapping.symbol)}; start['SPY']=pd.read_csv(tmp_path/'spy_prices.csv.gz').date.min()
    # Exercise actual old history footprint, extending exactly one real session.
    latest=old.date.max(); target=p.sessions(latest,pd.Timestamp(latest)+pd.Timedelta(days=7))[1]
    close=p.xcals.get_calendar('XNYS').session_close(target).to_pydatetime()
    from datetime import timedelta
    now=close+timedelta(minutes=21)
    def fake(ticker, cutoff): return frame(p.sessions(start[ticker],cutoff))
    original={f:p.sha(tmp_path/f) for f in p.FILES if (tmp_path/f).exists()}
    def broken(ticker,cutoff): return None if ticker=='SPY' else fake(ticker,cutoff)
    with patch.object(p.time,'sleep'):
        with pytest.raises(RuntimeError,match='SPY'): p.refresh(tmp_path,now,broken)
    assert original=={f:p.sha(tmp_path/f) for f in p.FILES if (tmp_path/f).exists()}
    assert p.refresh(tmp_path,now,fake)
    new=pd.read_csv(tmp_path/'etf_prices.csv.gz'); spy=pd.read_csv(tmp_path/'spy_prices.csv.gz')
    assert new.symbol.nunique()==20 and new.groupby('symbol').date.max().eq(str(target.date())).all()
    assert spy.date.max()==str(target.date())
    assert (tmp_path/'spy_snapshot_manifest.json').exists()
    assert not p.refresh(tmp_path,now,broken)
