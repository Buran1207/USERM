"""No-ML ETF rotation and reversal engine; fully backward-looking at every date.

RS benchmark: leave-one-out daily equal-weight RETURNS of other ETF peers in
same family; not an official index, not a fund NAV. RS ratio coordinates are a
transparent EMA approximation, NOT proprietary licensed JdK / Dorsey Wright.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import SignalConfig, CONFIG


def _pct(s: pd.Series, h: int) -> pd.Series:
    return s / s.shift(h) - 1.0


def _quadrant(x: pd.Series, y: pd.Series) -> pd.Series:
    ret = pd.Series("NA", index=x.index, dtype=object)
    valid = x.notna() & y.notna()
    ret.loc[valid & (x >= 100) & (y >= 100)] = "LEADING"
    ret.loc[valid & (x >= 100) & (y < 100)] = "WEAKENING"
    ret.loc[valid & (x < 100) & (y >= 100)] = "IMPROVING"
    ret.loc[valid & (x < 100) & (y < 100)] = "LAGGING"
    return ret


def _one_etf(frame: pd.DataFrame, peer_index: pd.Series, cfg: SignalConfig) -> pd.DataFrame:
    x = frame.sort_index().copy()
    price = x["close"]
    high = x["high"]
    vol = x["volume"]
    bench = peer_index.reindex(x.index)
    # No signal if peer benchmark not available / valid.
    log_rs = np.log(price.where(price > 0)) - np.log(bench.where(bench > 0))
    efast = log_rs.ewm(span=cfg.rs_fast_ema, adjust=False, min_periods=cfg.rs_fast_ema).mean()
    eslow = log_rs.ewm(span=cfg.rs_slow_ema, adjust=False, min_periods=cfg.rs_slow_ema).mean()
    x["rs_ratio"] = 100.0 * np.exp(efast - eslow)
    x["rs_momentum"] = 100.0 * x["rs_ratio"] / x["rs_ratio"].shift(cfg.rs_momentum_lag)
    x["quadrant"] = _quadrant(x["rs_ratio"],x["rs_momentum"])
    for h in [1,3,5,10,20,60]:
        x[f"ret_{h}"] = _pct(price,h)
        x[f"peer_ret_{h}"] = _pct(bench,h)
        x[f"rel_{h}"] = x[f"ret_{h}"] - x[f"peer_ret_{h}"]
    for n in [cfg.ma_fast,cfg.ma_medium,cfg.ma_long]:
        x[f"ma_{n}"] = price.rolling(n,min_periods=n).mean()
    x["rvol_20"] = vol / vol.rolling(cfg.rvol_window,min_periods=cfg.rvol_window).mean().shift(1).replace(0,np.nan)
    x["prior_20_high"] = high.rolling(cfg.breakout_window,min_periods=cfg.breakout_window).max().shift(1)
    x["breakout_20"] = (price > x["prior_20_high"]).fillna(False)
    x["benchmark_close"] = bench
    x["trade_proxy_usd"] = price * vol  # adjusted close x raw volume: a proxy, NOT exact transaction value
    x["stage"],x["new_signal"],x["stage_age"],x["reason"] = _states(x,cfg)
    return x


def _states(d: pd.DataFrame,cfg:SignalConfig):
    st,events,ages,reasons=[],[],[],[]
    previous="NA"; age=0; since_strong=9999
    for p in d.itertuples():
        x=getattr(p,"rs_ratio"); y=getattr(p,"rs_momentum")
        m10=getattr(p,f"ma_{cfg.ma_fast}");m20=getattr(p,f"ma_{cfg.ma_medium}");m50=getattr(p,f"ma_{cfg.ma_long}")
        # No fallback to 0 for unavailable history.
        valid = all(pd.notna(v) for v in [x,y,m10,m20,m50,p.rel_5,p.rel_10,p.rel_20,p.ret_5])
        if not valid:
            current="NA"; why="不足50日或相对指标缺失"
        else:
            lagging_turn = x < 100 and y >= cfg.early_momentum_floor and p.rel_5 > 0
            l1 = lagging_turn
            l2 = y >= cfg.early_momentum_floor and p.rel_5 > 0 and p.rel_10 > 0 and p.ret_5 > 0 and p.close > m10 and (x < 100.25)
            l3 = x > 100 and y >= 100 and p.rel_10 > 0 and p.close > m20 and m20 > m50 and bool(p.breakout_20) and pd.notna(p.rvol_20) and p.rvol_20 >= cfg.rvol_confirmation
            l4 = x > 100 and p.rel_20 > 0 and pd.notna(p.rel_60) and p.rel_60 > 0 and p.close > m20 and m20 > m50
            risk = since_strong <= cfg.signal_event_cooldown and p.close < m20 and p.rel_5 < cfg.hard_risk_relative_5d and y < 100
            if l3: current="L3";why="相对趋势强+突破前20日高点+成交量确认"
            elif l4: current="L4";why="相对趋势领先+20/60日超额收益正+均线向上"
            elif risk: current="W";why="近期曾为强势信号，现跌破20日均线且相对动量转负"
            elif l2: current="L2";why="短中期相对改善+5日上涨+站上10日均线"
            elif l1: current="L1";why="落后区域相对动量转正且5日超额收益正"
            else: current="N0";why="暂不符合四档触发条件"
        changed = current != previous
        age = 1 if changed else age+1
        st.append(current)
        events.append(bool(changed and current in {"L1","L2","L3","L4","W"}))
        ages.append(age);reasons.append(why)
        if current in {"L3","L4"}: since_strong=0
        else: since_strong+=1
        previous=current
    return st,events,ages,reasons


def calculate_etf_signals(quotes:pd.DataFrame, master:pd.DataFrame,cfg:SignalConfig=CONFIG) -> pd.DataFrame:
    """Daily state engine with no future observations and no forward-fill.

    Peer EW index uses daily rebalance by averaging peers' observed returns.
    It includes a changing set when returns are missing: quality notes required.
    All calculations are EOD. Signal is usable no earlier than next session.
    """
    from .data import table
    etf_map=master.set_index("etf")
    codes=table("etf_codes.csv").dropna(subset=["symbol"])
    q=quotes.merge(codes,on="symbol",how="inner",validate="many_to_one")
    q=q.merge(master[["etf","group","name_zh"]],on="etf",how="inner",validate="many_to_one")
    if q.empty: raise ValueError("No ETF daily bars matched the configured 20 ETF symbols")
    outputs=[]
    for family, g in q.groupby("group",sort=False):
        close=g.pivot(index="date",columns="etf",values="close").sort_index()
        pct=close.pct_change(fill_method=None)
        bysymbol={k:v.set_index("date").sort_index() for k,v in g.groupby("etf")}
        for etf, bars in bysymbol.items():
            others=pct.drop(columns=[etf])
            peer_r=others.mean(axis=1)
            peer_r[others.count(axis=1)<cfg.min_peer_returns]=np.nan
            # Missing peer days do not create false NaN in cumulative price, but
            # absence of enough peers is flagged and no signal is evaluated that day.
            idx=100*(1+peer_r.fillna(0)).cumprod()
            idx.loc[peer_r.isna()]=np.nan
            out=_one_etf(bars,idx,cfg).reset_index()
            out["etf"]=etf;out["group"]=family;out["name_zh"]=etf_map.loc[etf,"name_zh"]
            out["peer_count"] = others.count(axis=1).reindex(out.date).values
            outputs.append(out)
    all_data=pd.concat(outputs,ignore_index=True).sort_values(["date","group","etf"])
    # Purely cross-sectional percentile ranks, separate group each date.
    for k in [5,20,60]:
        all_data[f"rank_rel_{k}"]=all_data.groupby(["date","group"])[f"rel_{k}"].rank(pct=True,ascending=True)
    all_data["rotation_score"]=(0.25*all_data["rank_rel_5"]+0.35*all_data["rank_rel_20"]+0.40*all_data["rank_rel_60"])*100
    all_data["rotation_rank"] = all_data.groupby(["date","group"])["rotation_score"].rank(ascending=False,method="min")
    return all_data.reset_index(drop=True)


def latest_table(signals:pd.DataFrame,asof, calendar:pd.DatetimeIndex, max_stale_sessions:int=2) -> pd.DataFrame:
    asof=pd.Timestamp(asof)
    snap=signals[signals.date <=asof].sort_values("date").groupby("etf",as_index=False).tail(1).copy()
    snap["age_sessions"]=[int(((calendar>v)&(calendar<=asof)).sum()) for v in snap.date]
    snap["fresh"] = snap.age_sessions<=max_stale_sessions
    # Missing most recent date => not eligible for current signals even though
    # last known indicator is presented in history.
    for col in ["stage","rotation_rank","rotation_score"]:
        if col=="stage":snap.loc[~snap.fresh,col]="NA"
        else:snap.loc[~snap.fresh,col]=np.nan
    return snap.sort_values(["group","rotation_rank","etf"],na_position="last")
