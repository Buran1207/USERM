"""USERM V1.5 — 20 ETF-only rotation with SPY as the fixed RRG benchmark.

RRG-style 10/30/9 SMA is a transparent approximation, NOT licensed JdK.
All data are offline EOD. No stock universe, ML, L1-L4 or trading engine.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from userm.benchmarks import load_spy
from userm.data import load_quotes, load_etf_master, manifest, table
from userm.rrg import (RRG_SMA, RRG_LEGACY, METHOD_LABELS,
                       attach_common_rrg)
from userm.signals import calculate_etf_signals, latest_table, window_series
from userm.ui import CSS, tt, fmt_pct, figstyle, rotation_map, price_chart, table_download

st.set_page_config(page_title='USERM | 20 ETF RRG-style', page_icon='📈',
                   layout='wide', initial_sidebar_state='expanded')
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_etfs():
    master = load_etf_master()
    quotes = load_quotes('etfs')
    return calculate_etf_signals(quotes, master), master, quotes


def show_records(data: pd.DataFrame, columns: dict, pct_cols=(), round_cols=(), height=350):
    if data.empty:
        st.info('没有符合条件的数据 / No eligible data')
        return
    shown = data[list(columns)].rename(columns=columns).copy()
    for col in pct_cols:
        alias = columns.get(col, col)
        if alias in shown:
            shown[alias] = shown[alias].map(fmt_pct)
    for col in round_cols:
        alias = columns.get(col, col)
        if alias in shown:
            shown[alias] = shown[alias].map(lambda v: f'{v:.2f}' if pd.notna(v) else '—')
    st.dataframe(shown, use_container_width=True, hide_index=True, height=height)


try:
    base_signals, master, quotes = cached_etfs()
    spy = load_spy()
except Exception as error:
    st.error(f'行情加载失败 / Unable to load ETF or benchmark: {error}')
    st.stop()

calendar = pd.DatetimeIndex(sorted(base_signals.date.unique()))
if calendar.empty:
    st.error('ETF行情为空 / ETF price history is empty')
    st.stop()
latest = calendar.max()
quality = manifest()

with st.sidebar:
    st.markdown('<span style="color:#b98d8f;font-size:12px;letter-spacing:2px;font-weight:800">USERM · V1.5</span>',
                unsafe_allow_html=True)
    st.markdown('### US ETF ROTATION')
    lang = st.selectbox('Language / 语言', ['中文','English'], index=0)
    english = lang == 'English'
    pages = ['ETF市场总览', 'ETF轮动地图', '方法与数据质量']
    page = st.radio('工作页面 / Workspace', pages, format_func=lambda value: tt(value, english))
    requested = st.date_input('研究日期 / As of', value=latest.date(),
                              min_value=calendar.min().date(), max_value=latest.date())
    req = pd.Timestamp(requested)
    asof = calendar[calendar <= req].max()
    if asof != req:
        st.caption(f'非交易日，回退至 / Effective session: {asof.date()}')
    period = st.slider('观察周期 / Observation period (sessions)', 1, 60, 20, 1,
                       help='仅影响ETF组内收益、超额、排名，不影响RRG横纵轴。')
    family = st.selectbox('ETF分组 / ETF family', ['全部','行业','科技主题'],
                          format_func=lambda value: tt(value, english))
    st.divider()
    st.markdown('**RRG / 轮动地图**')
    st.caption('统一基准 / Fixed RRG benchmark: SPY (S&P 500 ETF)')
    rrg_method = st.selectbox('RRG近似算法 / Formula', [RRG_SMA, RRG_LEGACY],
                             format_func=lambda v: METHOD_LABELS[v])
    tail_length = st.slider('轨迹尾长 / Prior trading days', 1, 40, 4, 1,
                            help='显示之前N个交易日+当前点；不改变RS-Ratio或RS-Momentum。')
    if spy is None:
        st.warning('缺少 data/spy_prices.csv.gz。请先运行 REFRESH_ETF_AND_SPY.bat；RRG暂不显示数值，不使用其他ETF代替SPY。')
    else:
        st.caption(f'SPY EOD: {spy.index.min().date()} — {spy.index.max().date()}')
    st.caption(f'ETF latest: {latest.date()}')
    st.caption('离线EOD数据，无自动行情下载，禁止盘中未完成K线。')

# SPY is intentionally excluded from the 20-ETF target universe and rankings.
bench = spy.rename('close') if spy is not None else pd.Series(dtype=float, name='close')
benchmark_label = 'SPY · S&P 500 ETF (not $SPX)'

try:
    signals = attach_common_rrg(base_signals, quotes, table('etf_codes.csv'), bench,
                                method=rrg_method)
except Exception as err:
    st.error(f'RRG计算出错 / Unable to calculate RRG: {err}')
    st.stop()

snapshot = latest_table(signals, asof, calendar, observation_days=period)
if family != '全部':
    snapshot = snapshot[snapshot.group == family].copy()
fresh = snapshot[snapshot.fresh].copy()
rrg_available = fresh.dropna(subset=['rs_ratio','rs_momentum'])

st.markdown('<div class="tag">USERM | 20 ETF RELATIVE ROTATION</div>', unsafe_allow_html=True)
st.title(tt(page, english))
st.caption(f'20 ETF · EOD {asof:%Y-%m-%d} · Performance window {period} sessions · '
           f'RRG Daily / Tail {tail_length} / benchmark {benchmark_label} · No ML')
if asof == latest and (pd.Timestamp.today().normalize() - latest).days > 7:
    st.warning('ETF行情距离当前日期超过7天，请先使用本地数据更新程序。')
if spy is None:
    st.warning('SPY基准未导入，ETF组内收益和排名正常；RRG坐标暂不可用。请从本地CPS2刷新21只标的。')
elif asof not in spy.index:
    st.warning('研究日缺少SPY收盘记录，RRG不会沿用上一日SPY收盘价。')

if page == 'ETF市场总览':
    metrics = st.columns(4)
    metrics[0].metric('有效ETF / Valid ETFs', f'{len(fresh)}/{len(snapshot)}')
    metrics[1].metric(f'{period}日正超额 / Positive excess', int((fresh.rel_window > 0).sum()))
    metrics[2].metric('RRG领先 / Leading RS', int((rrg_available.rs_ratio >= 100).sum()))
    metrics[3].metric('RRG改善 / Improving', int((rrg_available.quadrant == 'IMPROVING').sum()))
    st.info(f'组内排名：{period}日ETF收益减同组其他ETF等权收益。'
            f'RRG：全部ETF统一对比{benchmark_label}，采用{METHOD_LABELS[rrg_method]}。'
            '两者是不同问题，不混合评分。')
    show_records(fresh, {
        'etf':'ETF', 'name_zh':'方向', 'group':'分组', 'rotation_rank':'组内名次',
        'ret_window':f'{period}日收益', 'rel_window':f'{period}日超额',
        'rotation_score':'组内相对分位', 'quadrant':'RRG象限',
        'rs_ratio':'RRG X (近似)', 'rs_momentum':'RRG Y (近似)', 'rvol_20':'20日量比',
    }, pct_cols=['ret_window','rel_window'],
        round_cols=['rotation_rank','rotation_score','rs_ratio','rs_momentum','rvol_20'], height=490)
    st.download_button('下载ETF面板 CSV', data=table_download(fresh),
                       file_name=f'USERM_ETF_{period}D_{asof.date()}.csv', mime='text/csv')
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader(f'{period}日ETF组内相对收益')
        ranked = fresh.sort_values('rel_window', ascending=False).copy()
        ranked['excess_pp'] = ranked.rel_window * 100
        fig = go.Figure(go.Bar(x=ranked.excess_pp, y=ranked.etf, orientation='h',
                        marker_color=['#288973' if value >= 0 else '#B95C68' for value in ranked.excess_pp]))
        fig.update_layout(yaxis=dict(autorange='reversed'), xaxis_title='Excess return (percentage points)')
        st.plotly_chart(figstyle(fig, 510), use_container_width=True)
    with right:
        st.subheader('RRG象限分布')
        counts = rrg_available.groupby(['group','quadrant']).size().reset_index(name='ETF数')
        if not counts.empty:
            import plotly.express as px
            fig = px.bar(counts, x='group', y='ETF数', color='quadrant', barmode='stack',
                         category_orders={'quadrant':['LEADING','IMPROVING','WEAKENING','LAGGING','NA']},
                         color_discrete_map={
                           'LEADING':'#207A65', 'IMPROVING':'#3478B0',
                           'WEAKENING':'#C48E43', 'LAGGING':'#B04A52', 'NA':'#B0B7C3'})
            st.plotly_chart(figstyle(fig, 365), use_container_width=True)
        st.caption('RRG描述相对趋势，不是交易信号。')
    st.subheader('ETF价格与组内超额收益')
    symbols = snapshot.etf.tolist()
    if symbols:
        selected = st.selectbox('研究ETF / Symbol', symbols)
        g = window_series(signals, selected, asof, calendar, period)
        st.plotly_chart(price_chart(g, selected, period), use_container_width=True)

elif page == 'ETF轮动地图':
    st.info('参照StockCharts的Daily、Tail 4展示方式，但基准改用SPY（不是截图中的$SPX）。'
            '默认公开近似X=100×SMA10(RS)/SMA30(RS)，Y=100×X/SMA9(X)。'
            '该方法并非官方JdK算法；尾长不影响计算，3个月只影响显示范围。')
    if spy is None:
        st.warning('当前没有SPY数据，不能计算RRG坐标。请先在本地刷新，再上传 data/spy_prices.csv.gz。')
    # Reference benchmark sparkline: last 3 calendar months, not calculation history.
    preview = bench.loc[(bench.index <= asof) & (bench.index >= asof-pd.DateOffset(months=3))].dropna()
    if not preview.empty:
        small = go.Figure(go.Scatter(x=preview.index, y=preview.values, mode='lines',
                                     line=dict(color='#263e56',width=2), name=benchmark_label))
        small.update_layout(title=f'{benchmark_label} · 最近3个月展示窗口', showlegend=False)
        st.plotly_chart(figstyle(small, 180), use_container_width=True)
    symbols = rrg_available.etf.tolist()
    selected = st.multiselect('RRG展示ETF / Symbols', symbols, default=symbols,
                              max_selections=20)
    trails = signals[(signals.etf.isin(selected)) & (signals.date <= asof)].groupby(
        'etf', group_keys=False).tail(tail_length + 1)
    current = snapshot[snapshot.etf.isin(selected)].copy()
    if rrg_available.empty:
        st.warning('当前日期缺少RRG计算所需基准或历史行情，无法生成坐标。')
    else:
        st.plotly_chart(rotation_map(current, trails, english), use_container_width=True)
    st.caption(f'RRG统一基准：{benchmark_label}；方法：{METHOD_LABELS[rrg_method]}。'
               '尾长4＝4个历史日节点加最新点；非官方JdK数值。')
    show_records(rrg_available, {
        'etf':'ETF','name_zh':'方向','quadrant':'象限',
        'rs_ratio':'RRG X (近似)','rs_momentum':'RRG Y (近似)',
        'ret_window':f'{period}日收益','rel_window':f'{period}日组内超额',
        'rotation_rank':'组内名次',
    }, pct_cols=['ret_window','rel_window'],
        round_cols=['rs_ratio','rs_momentum','rotation_rank'], height=490)
    st.caption('Improving仅表示相对趋势改善，不意味着ETF价格上涨。')

elif page == '方法与数据质量':
    st.subheader('两套独立研究口径')
    st.markdown('**ETF组内Alpha排名（保留V1.3逻辑）：** 同组其他ETF的每日等权收益基准，'
                '所选周期1–60日超额收益排序；不受RRG基准及尾长影响。')
    st.latex(r'A_{i,n}=\left(\frac{P_{i,t}}{P_{i,t-n}}-1\right)-\left(\frac{B_{i,t}}{B_{i,t-n}}-1\right)')
    st.markdown(f'**统一基准RRG（当前{benchmark_label}）：** 每只ETF独立计算与同一基准的原始相对价格。')
    st.latex(r'RS_{i,t}=P_{ETF_i,t}/P_{benchmark,t}')
    st.markdown('**默认公开RRG近似：**')
    st.latex(r'X_t=100\frac{SMA_{10}(RS_t)}{SMA_{30}(RS_t)},\quad Y_t=100\frac{X_t}{SMA_{9}(X_t)}')
    st.markdown('**旧USERM可选方法：**')
    st.latex(r'X_t=100e^{EMA_{14}(\ln RS_t)-EMA_{36}(\ln RS_t)},\quad Y_t=100X_t/X_{t-5}')
    st.markdown('**日线、尾长、范围：** 每天1个新点，Tail Length=4只显示此前4个交易日；'
                'Range=3个月仅决定图表展示区间，计算仍使用2020年以来历史序列。')
    st.markdown('**StockCharts JdK的精确平滑/标准化参数未公开；用户不应把本系统坐标称为官方JdK值。**')
    st.subheader('数据覆盖')
    if quality:
        e=quality.get('etfs', {})
        cols = st.columns(4)
        cols[0].metric('ETF行情行数', f"{e.get('rows',0):,}")
        cols[1].metric('ETF数量', f"{e.get('symbols_found',0)}/20")
        cols[2].metric('最早交易日', str(e.get('min_date', calendar.min().date())))
        cols[3].metric('最新交易日', str(e.get('max_date', latest.date())))
        st.caption(f"Snapshot generated UTC: {quality.get('generated_utc','?')}")
    if spy is None:
        st.warning('尚无SPY历史。请先运行 REFRESH_ETF_AND_SPY.bat 生成 data/spy_prices.csv.gz。')
    else:
        st.success(f'SPY ETF EOD history {len(spy):,} bars: '
                   f'{spy.index.min().date()} to {spy.index.max().date()}')
    st.dataframe(snapshot[['etf','date','age_sessions','fresh','peer_count','partition',
                           'rvol_20','rotation_rank']], use_container_width=True, hide_index=True)
    st.markdown('''1. 数据为iFinD标注CPS:2的调整价格，是否与StockCharts价格复权处理完全一致尚未核验。\n
2. `data/spy_prices.csv.gz` 必须为SPY ETF真实日线行情，与20只ETF同一复权口径。\n
3. 缺失ETF或SPY的收盘日不填充、不使用未完成交易日。\n
4. 不引入个股、机器学习、反转分级、历史事件胜率或自动交易。''')

st.divider()
st.caption('USERM V1.5 · ETF-only · RRG-style approximation · SPY benchmark (not official JdK) · EOD')
