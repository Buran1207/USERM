"""Current top-five holdings Alpha screen: snapshot membership, NOT PIT backtest.
Only rank if both ETF and stock have an actual quote on the selected date.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import CONFIG


def alpha_table(stocks:pd.DataFrame, etf_signals:pd.DataFrame, holdings:pd.DataFrame, asof, calendar:pd.DatetimeIndex):
    asof=pd.Timestamp(asof)
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
        # If a stock has missing days, returns must not silently cover a longer span.
        for n in [5,20,60]:
            g[f'stock_ret_{n}']=g.close_stock/g.close_stock.shift(n)-1
            g[f'etf_ret_{n}']=g.close_etf/g.close_etf.shift(n)-1
            g[f'alpha_{n}']=g[f'stock_ret_{n}']-g[f'etf_ret_{n}']
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
    return ranked.sort_values(['fresh','alpha_strength'],ascending=[False,False],na_position='last')
