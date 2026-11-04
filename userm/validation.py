"""Event study only; no retraining or inferred tradable P&L.
Signal generated after t close, entry at CLOSE(t+1), exit CLOSE(t+1+h).
No same-day entry, no fake closed market day returns, no optimization.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


def _events_for_symbol(g:pd.DataFrame,horizons=(5,10,20)) -> pd.DataFrame:
    g=g.sort_values('date').copy()
    eligible=g.new_signal & g.stage.isin(['L1','L2','L3','L4'])
    e=g.loc[eligible,['date','etf','group','stage','partition','quadrant']].copy()
    close=g.close;bench=g.benchmark_close
    for h in horizons:
        # start one bar AFTER signal day; H complete close-close sessions
        asset_forward=close.shift(-(1+h))/close.shift(-1)-1
        benchmark_forward=bench.shift(-(1+h))/bench.shift(-1)-1
        allpath=pd.concat([close.shift(-(1+k))/close.shift(-1)-1 for k in range(1,h+1)],axis=1)
        e[f'forward_{h}']=asset_forward.loc[e.index]
        e[f'peer_forward_{h}']=benchmark_forward.loc[e.index]
        e[f'excess_{h}']=e[f'forward_{h}']-e[f'peer_forward_{h}']
        e[f'mae_{h}']=allpath.min(axis=1).loc[e.index]
    return e


def event_study(signals:pd.DataFrame)->pd.DataFrame:
    data=[_events_for_symbol(g) for _,g in signals.groupby('etf')]
    if not data:return pd.DataFrame()
    out=pd.concat(data,ignore_index=True)
    out['period']=out.date.apply(lambda d:'2026 OOS partition' if d.year>=2026 else '2020–2025 TRAIN')
    return out


def event_summary(events:pd.DataFrame,horizon=10,period='2026 OOS partition') -> pd.DataFrame:
    if events.empty:return pd.DataFrame()
    d=events[events.period==period].dropna(subset=[f'forward_{horizon}',f'excess_{horizon}'])
    if d.empty:return pd.DataFrame()
    rows=[]
    for (group,stage),g in d.groupby(['group','stage']):
        rows.append(dict(group=group,stage=stage,count=len(g),
                         win_rate=(g[f'forward_{horizon}']>0).mean(),
                         alpha_hit_rate=(g[f'excess_{horizon}']>0).mean(),
                         med_return=g[f'forward_{horizon}'].median(),
                         med_alpha=g[f'excess_{horizon}'].median(),
                         med_mae=g[f'mae_{horizon}'].median()))
    return pd.DataFrame(rows).sort_values(['group','stage'])
