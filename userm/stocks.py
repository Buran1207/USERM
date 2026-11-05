"""Current top-five holdings Alpha screen: snapshot membership, NOT PIT backtest.
Only rank if both ETF and stock have an actual quote on the selected date.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import CONFIG


def alpha_table(stocks:pd.DataFrame, etf_signals:pd.DataFrame, holdings:pd.DataFrame, asof, calendar:pd.DatetimeIndex, observation_days:int=20):
    asof=pd.Timestamp(asof)
    observation_days=int(observation_days)
    if not 1 <= observation_days <= 60:
        raise ValueError("Observation sessions must be between 1 and 60")
    sessions=pd.DatetimeIndex(calendar)
    sessions=sessions[sessions<=asof]
    h=holdings.copy()
    h=h[h.symbol.notna() & (h.symbol.astype(str).str.strip()!='')]
    relevant=set(h.symbol)
    s=stocks[stocks.symbol.isin(relevant)&(stocks.date<=asof)].copy()
    etf=etf_signals[etf_signals.date<=asof][["date","etf","close","stage","group"]]
    m=h.merge(s,on='symbol',how='inner').merge(etf,on=['date','etf'],how='inner',suffixes=('_stock','_etf'))
    if m.empty:return pd.DataFrame()
    out=[]
    for (e,code),g in m.groupby(['etf','symbol'],sort=False):
        g=g.sort_values('date').copy()
        # Align stock and ETF to the SAME observed market calendar.
        # A window with any missing daily bar is invalid, not a longer-period
        # return masquerading as a 5/20/60-day observation.
        aligned=g.set_index('date').reindex(sessions)
        observed=aligned.close_stock.notna() & aligned.close_etf.notna()
        for n in sorted({5,20,60,observation_days}):
            complete=observed.rolling(n+1,min_periods=n+1).sum().eq(n+1)
            sr=(aligned.close_stock/aligned.close_stock.shift(n)-1).where(complete)
            er=(aligned.close_etf/aligned.close_etf.shift(n)-1).where(complete)
            suffix=str(n) if n in (5,20,60) else 'obs'
            g[f'stock_ret_{suffix}']=g.date.map(sr)
            g[f'etf_ret_{suffix}']=g.date.map(er)
            g[f'alpha_{suffix}']=g[f'stock_ret_{suffix}']-g[f'etf_ret_{suffix}']
        if observation_days in (5,20,60):
            for prefix in ('stock_ret','etf_ret','alpha'):
                g[f'{prefix}_obs']=g[f'{prefix}_{observation_days}']
        g['stock_ma10']=g.close_stock.rolling(10,min_periods=10).mean()
        g['stock_ma20']=g.close_stock.rolling(20,min_periods=20).mean()
        g['stock_ma50']=g.close_stock.rolling(50,min_periods=50).mean()
        g['prior_high20']=g.high.rolling(20,min_periods=20).max().shift(1)
        g['rvol20']=g.volume/g.volume.rolling(20,min_periods=20).mean().shift(1).replace(0,np.nan)
        g['trade_proxy_usd']=g.close_stock*g.volume
        current=g.iloc[-1].copy()
        latest=pd.Timestamp(current.date)
        age=int(((calendar>latest)&(calendar<=asof)).sum())
        current['age_sessions']=age
        current['fresh']=age<=2 and latest==asof
        if not current['fresh']:
            current['stock_signal']='行情过期'
        elif pd.isna(current['stock_ma50']) or pd.isna(current['alpha_60']):
            current['stock_signal']='历史不足'
        elif (current.close_stock>current.prior_high20 and current.alpha_20>0 and current.close_stock>current.stock_ma20 and current.rvol20>=1.2):
            current['stock_signal']='个股强势突破'
        elif (current.alpha_5>0 and current.alpha_20>0 and current.close_stock>current.stock_ma20 and current.stock_ma20>current.stock_ma50):
            current['stock_signal']='个股持续领先'
        elif (current.alpha_5>0 and current.alpha_20<=0 and current.close_stock>current.stock_ma10 and current.rvol20>=1.15):
            current['stock_signal']='个股反转观察'
        else:
            current['stock_signal']='暂无触发'
        out.append(current)
    ranked=pd.DataFrame(out)
    ranked['alpha_strength']=0.45*ranked['alpha_20']+0.35*ranked['alpha_5']+0.20*ranked['alpha_60']
    # Rescale simply to percentage points, not advertised as predicted return.
    ranked['alpha_strength_pp']=100*ranked['alpha_strength']
    ranked['obs_alpha_rank']=ranked.groupby('etf')['alpha_obs'].rank(ascending=False,method='min')
    return ranked.sort_values(['fresh','alpha_obs','alpha_strength'],ascending=[False,False,False],na_position='last')
