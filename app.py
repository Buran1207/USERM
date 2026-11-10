"""USERM V1.3 — 20 ETF-only relative rotation monitor.

Read-only Streamlit dashboard using offline CPS2 ETF snapshots. No stock or
holdings data, no ML, trade execution, L1-L4 alerts or event backtests.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from userm.data import load_quotes, load_etf_master, manifest
from userm.signals import calculate_etf_signals, latest_table, window_series
from userm.ui import CSS, tt, fmt_pct, figstyle, rotation_map, price_chart, table_download

st.set_page_config(page_title='USERM | US ETF Rotation Monitor', page_icon='📈',
                   layout='wide', initial_sidebar_state='expanded')
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_etfs():
    master = load_etf_master()
    return calculate_etf_signals(load_quotes('etfs'), master), master



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
    signals, master = cached_etfs()
except Exception as error:
    st.error(f'ETF行情读取失败 / Failed to load ETF quotes: {error}')
    st.info('请检查 data/etf_prices.csv.gz、data/etf_codes.csv 和 data/etfs.csv。')
    st.stop()

calendar = pd.DatetimeIndex(sorted(signals.date.unique()))
if calendar.empty:
    st.error('ETF行情为空 / ETF price history is empty')
    st.stop()
latest = calendar.max()
quality = manifest()

with st.sidebar:
    st.markdown('<span style="color:#b98d8f;font-size:12px;letter-spacing:2px;font-weight:800">USERM · V1.3</span>',
                unsafe_allow_html=True)
    st.markdown('### US ETF ROTATION')
    lang = st.selectbox('Language / 语言', ['中文', 'English'], index=0)
    english = lang == 'English'
    pages = ['ETF市场总览', 'ETF轮动地图', '方法与数据质量']
    page = st.radio('工作页面 / Workspace', pages, format_func=lambda value: tt(value, english))
    requested = st.date_input('研究日期 / As of', value=latest.date(),
                              min_value=calendar.min().date(), max_value=latest.date())
    asof_requested = pd.Timestamp(requested)
    asof = calendar[calendar <= asof_requested].max()
    if asof != asof_requested:
        st.caption(f'非交易日，回退至 / Effective trading date: {asof.date()}')
    period = st.slider('观察周期 / Observation period (trading days)',
                       min_value=1, max_value=60, value=20, step=1,
                       help='改变ETF收益、超额收益和排名；不改变RRG固定EMA14/36及5日动量。')
    family = st.selectbox('ETF分组 / ETF family', ['全部', '行业', '科技主题'],
                          format_func=lambda value: tt(value, english))
    st.caption('观察周期影响收益和排名，不影响RRG坐标公式。')
    st.caption(f'ETF latest: {latest.date()}')
    st.caption('离线EOD数据，只读网页。无自动行情抓取。')

snapshot = latest_table(signals, asof, calendar, observation_days=period)
if family != '全部':
    snapshot = snapshot[snapshot.group == family].copy()
fresh = snapshot[snapshot.fresh].copy()

st.markdown('<div class="tag">USERM | 20 ETF RELATIVE ROTATION</div>', unsafe_allow_html=True)
st.title(tt(page, english))
st.caption(f'20 ETF universe · CPS:2 adjusted daily prices · As of {asof:%Y-%m-%d} EOD '
           f'· Observation {period} trading days · No ML')
if asof == latest and (pd.Timestamp.today().normalize() - latest).days > 7:
    st.warning('ETF行情距离当前日期超过7天，请先使用本地取数/同步程序更新GitHub数据。')

if page == 'ETF市场总览':
    metrics = st.columns(4)
    metrics[0].metric('有效ETF / Valid ETFs', f'{len(fresh)}/{len(snapshot)}')
    metrics[1].metric(f'{period}日正超额 / Positive excess', int((fresh.rel_window > 0).sum()))
    metrics[2].metric('相对趋势领先 / RS leading', int((fresh.rs_ratio >= 100).sum()))
    metrics[3].metric('落后改善 / RS improving', int((fresh.quadrant == 'IMPROVING').sum()))
    st.info(f'观察周期设为{period}个交易日。超额收益=ETF同期收益－同组其余ETF等权基准收益；'
            '轮动排名完全由所选周期超额收益决定，不是预测收益或买入建议。')
    st.subheader('ETF轮动表现与排名')
    show_records(fresh, {
        'etf':'ETF', 'name_zh':'方向', 'group':'分组', 'rotation_rank':'组内名次',
        'ret_window':f'{period}日收益', 'rel_window':f'{period}日超额',
        'rotation_score':'组内相对分位', 'quadrant':'RRG象限',
        'rs_ratio':'RS趋势', 'rs_momentum':'RS动量', 'rvol_20':'20日量比',
    }, pct_cols=['ret_window','rel_window'],
        round_cols=['rotation_rank','rotation_score','rs_ratio','rs_momentum','rvol_20'], height=490)
    st.download_button('下载ETF面板 CSV', data=table_download(fresh),
                       file_name=f'USERM_ETF_{period}D_{asof.date()}.csv', mime='text/csv')
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader(f'{period}日ETF相对收益')
        ranked = fresh.sort_values('rel_window', ascending=False).copy()
        ranked['excess_pp'] = ranked.rel_window * 100
        fig = go.Figure(go.Bar(x=ranked.excess_pp, y=ranked.etf, orientation='h',
                               marker_color=['#288973' if value >= 0 else '#B95C68' for value in ranked.excess_pp]))
        fig.update_layout(yaxis=dict(autorange='reversed'), xaxis_title='Excess return (percentage points)')
        st.plotly_chart(figstyle(fig, 510), use_container_width=True)
    with right:
        st.subheader('RRG象限分布')
        counts = fresh.groupby(['group', 'quadrant']).size().reset_index(name='ETF数')
        if not counts.empty:
            import plotly.express as px
            fig = px.bar(counts, x='group', y='ETF数', color='quadrant', barmode='stack',
                         category_orders={'quadrant':['LEADING','IMPROVING','WEAKENING','LAGGING','NA']},
                         color_discrete_map={
                             'LEADING':'#207A65', 'IMPROVING':'#3478B0',
                             'WEAKENING':'#C48E43', 'LAGGING':'#B04A52', 'NA':'#B0B7C3'})
            st.plotly_chart(figstyle(fig, 365), use_container_width=True)
        st.caption('象限仅描述相对强弱与变化，不是交易信号。')
    st.subheader('ETF价格与相对收益复核')
    symbols = snapshot.etf.tolist()
    if symbols:
        selected = st.selectbox('研究ETF / Symbol', symbols)
        g = window_series(signals, selected, asof, calendar, period)
        st.plotly_chart(price_chart(g, selected, period), use_container_width=True)
        st.caption('图中为CPS:2调整价格，不等于实际委托价；下方为所选周期的历史超额收益。')

elif page == 'ETF轮动地图':
    st.info('RRG近似四象限：X=100×exp[EMA14(ln RS)−EMA36(ln RS)]，'
            'Y=100×X/X(5交易日前)。相对价格RS基于同组其他ETF的等权收益基准。'
            '观察周期只调整ETF收益排名与悬浮提示，不改变上述坐标。')
    symbols = fresh.etf.tolist()
    selected = st.multiselect('历史轨迹 / Trails', symbols, default=symbols[:2], max_selections=4)
    trail_len = st.slider('轨迹长度 / Trail sessions', 5, 40, 15)
    trails = signals[(signals.etf.isin(selected)) & (signals.date <= asof)].groupby('etf', group_keys=False).tail(trail_len)
    st.plotly_chart(rotation_map(snapshot, trails, english), use_container_width=True)
    st.subheader('四象限与所选周期相对收益')
    show_records(fresh, {
        'etf':'ETF','name_zh':'方向','quadrant':'象限',
        'rs_ratio':'RS趋势','rs_momentum':'RS动量','ret_window':f'{period}日收益',
        'rel_window':f'{period}日超额','rotation_rank':'组内名次',
    }, pct_cols=['ret_window','rel_window'], round_cols=['rs_ratio','rs_momentum','rotation_rank'], height=460)
    st.caption('Improving表示相对趋势改善，不意味着ETF价格一定上涨。')

elif page == '方法与数据质量':
    st.subheader('透明计算规则（非交易信号）')
    st.markdown('**基准**：11只行业ETF或9只科技主题ETF各自内部，其他ETF的日收益等权平均，'
                '并逐日连乘成相对比较基准。计算时剔除被比较ETF自身。')
    st.latex(r'r^{peer}_{i,t}=\frac{1}{N_t-1}\sum_{j\neq i}r_{j,t},\qquad RS_{i,t}=\frac{P_{i,t}}{B_{i,t}}')
    st.markdown('**RRG坐标**：借鉴StockCharts的相对趋势/动量四象限概念，'
                '但不是StockCharts专有JdK数值。')
    st.latex(r'X_t=100\exp(EMA_{14}(\ln RS_t)-EMA_{36}(\ln RS_t)),\qquad Y_t=100\frac{X_t}{X_{t-5}}')
    st.markdown('**可选观察周期（1–60交易日）**：')
    st.latex(r'R_{i,n}=\frac{P_{i,t}}{P_{i,t-n}}-1,\quad A_{i,n}=R_{i,n}-\left(\frac{B_{i,t}}{B_{i,t-n}}-1\right)')
    st.markdown('组内名次由所选周期的超额收益从高到低排列；RRG坐标保持固定。'
                '不输出L1–L4、风险警报或历史事件胜率。')
    st.subheader('数据覆盖及限制')
    if quality:
        e = quality.get('etfs', {})
        cols = st.columns(4)
        cols[0].metric('ETF行情行数', f"{e.get('rows', 0):,}")
        cols[1].metric('ETF数量', f"{e.get('symbols_found', 0)}/20")
        cols[2].metric('最早交易日', str(e.get('min_date', calendar.min().date())))
        cols[3].metric('最新交易日', str(e.get('max_date', latest.date())))
        st.caption(f"Snapshot generated UTC: {quality.get('generated_utc', '?')}")
    details = snapshot[['etf','date','age_sessions','fresh','peer_count','partition','rvol_20','rotation_rank']].sort_values('etf')
    st.dataframe(details, use_container_width=True, hide_index=True)
    st.markdown('''1. CPS:2是数据源标注的复权价格；现金分红总回报口径未独立核验，也不是实际委托价格。
2. 仅研究20只ETF，11只一级行业ETF及9只科技主题ETF分别进行组内相对收益比较。
3. 观察周期严格按ETF市场交易日计算，期初或期末缺失行情不前向填充。
4. RRG为可解释的EMA14/36与5日相对动量，并非StockCharts专有指标。
5. 不使用机器学习、反转分级信号、历史交易事件回测或自动交易功能。
6. 快照不得包含未收盘交易日；上传前核对最新日期及供应商数据许可。''')
    st.caption('详细方法：METHODS_ROTATION.md、README.md、DATA_QUALITY.md')

st.divider()
st.caption('USERM V1.3 | 20 ETF relative-rotation research only · Offline EOD snapshot · No execution')
