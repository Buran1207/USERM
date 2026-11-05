"""USERM V1.2 — 20 ETF relative rotation and stock Alpha monitor.

Read-only Streamlit dashboard based on offline CPS2 snapshots. No ML, trade
execution, L1-L4 trading alerts, or historical event backtest. Data may be
licensed; apply hosting/access controls appropriate to your iFinD agreement.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from userm.data import load_quotes, load_etf_master, load_holdings, manifest
from userm.signals import calculate_etf_signals, latest_table, window_series
from userm.stocks import alpha_table
from userm.ui import CSS, tt, fmt_pct, figstyle, rotation_map, price_chart, table_download, tradingview_url

st.set_page_config(page_title='USERM | US ETF Rotation Monitor', page_icon='📈',
                   layout='wide', initial_sidebar_state='expanded')
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_etfs():
    master = load_etf_master()
    return calculate_etf_signals(load_quotes('etfs'), master), master


@st.cache_data(show_spinner=False)
def cached_stocks():
    return load_quotes('stocks')


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


def safe_day(value):
    """Manifest fields may be null or annotated text. Never raise on bad dates."""
    if value is None:
        return pd.NaT
    date_part = pd.Series([str(value)]).str.extract(r'(\d{4}-\d{2}-\d{2})', expand=False).iloc[0]
    return pd.to_datetime(date_part, format='%Y-%m-%d', errors='coerce')


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
stock_latest = safe_day(quality.get('stocks', {}).get('max_date'))

with st.sidebar:
    st.markdown('<span style="color:#b98d8f;font-size:12px;letter-spacing:2px;font-weight:800">USERM · V1.2</span>',
                unsafe_allow_html=True)
    st.markdown('### US EQUITY ROTATION')
    lang = st.selectbox('Language / 语言', ['中文', 'English'], index=0)
    english = lang == 'English'
    pages = ['ETF市场总览', 'ETF轮动地图', '个股Alpha', '方法与数据质量']
    page = st.radio('工作页面 / Workspace', pages, format_func=lambda value: tt(value, english))
    requested = st.date_input('研究日期 / As of', value=latest.date(),
                              min_value=calendar.min().date(), max_value=latest.date())
    asof_requested = pd.Timestamp(requested)
    asof = calendar[calendar <= asof_requested].max()
    if asof != asof_requested:
        st.caption(f'非交易日，回退至 / Effective trading date: {asof.date()}')
    period = st.slider('观察周期 / Observation period (trading days)',
                       min_value=1, max_value=60, value=20, step=1,
                       help='改变ETF排名、收益和个股Alpha；不改变RRG固定EMA14/36及5日动量。')
    family = st.selectbox('ETF分组 / ETF family', ['全部', '行业', '科技主题'],
                          format_func=lambda value: tt(value, english))
    st.caption('观察周期影响收益和排名，不影响RRG坐标公式。')
    st.caption(f'ETF latest: {latest.date()}')
    st.caption(f"Stock latest: {stock_latest.date() if pd.notna(stock_latest) else '未知'}")
    st.caption('离线EOD数据，只读网页。无自动行情抓取。')

snapshot = latest_table(signals, asof, calendar, observation_days=period)
if family != '全部':
    snapshot = snapshot[snapshot.group == family].copy()
fresh = snapshot[snapshot.fresh].copy()

st.markdown('<div class="tag">USERM | 20 ETF ROTATION & STOCK ALPHA</div>', unsafe_allow_html=True)
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

elif page == '个股Alpha':
    st.markdown('研究范围为上传的20只ETF**前五大持仓快照**中可映射到美股的股票，不等于ETF全部持仓。')
    try:
        stocks = cached_stocks()
    except Exception as error:
        st.error(f'股票行情读取失败 / Stock quotes unavailable: {error}')
        st.stop()
    # Manifest might be old/stale; actual loaded price dates are authoritative.
    actual_stock_last = pd.Timestamp(stocks.date.max()) if not stocks.empty else pd.NaT
    if pd.isna(actual_stock_last):
        st.warning('股票历史数据为空。请先更新本地快照。')
        st.stop()
    effective = min(asof, actual_stock_last)
    eligible_dates = calendar[calendar <= effective]
    if eligible_dates.empty:
        st.info('股票行情时间范围和ETF时间范围没有交集。')
        st.stop()
    stock_asof = eligible_dates.max()
    if stock_asof < asof:
        missing = int(((calendar > stock_asof) & (calendar <= asof)).sum())
        st.warning(f'股票最新实际行情为{actual_stock_last.date()}，落后所选ETF研究日{missing}个交易日。'
                   '下方为历史研究，不能当作当期交易候选。')
    stock_request = st.date_input('个股研究日期 / Stock review date',
                                  value=stock_asof.date(), min_value=eligible_dates.min().date(),
                                  max_value=stock_asof.date(), key='stock_review_date')
    stock_day = eligible_dates[eligible_dates <= pd.Timestamp(stock_request)].max()
    holdings = load_holdings()
    known_dates = holdings.get('holdings_date', pd.Series(dtype='datetime64[ns]')).dropna()
    if not known_dates.empty and stock_day < known_dates.max():
        st.warning(f'ETF前五大持仓为较新的单次快照（最晚{known_dates.max().date()}），'
                   f'晚于所选股票日{stock_day.date()}。这里仅做事后相对表现比较，不视为历史实时持仓。')
    invalid_count = int(holdings.holdings_date.isna().sum()) if 'holdings_date' in holdings else 0
    if invalid_count:
        st.caption(f'部分持仓日期无法识别：{invalid_count}行已跳过日期比较，持仓关系仍需核实。')
    alpha = alpha_table(stocks, signals, holdings, stock_day, calendar, observation_days=period)
    if alpha.empty:
        st.info('所选研究日没有ETF与股票同时匹配的行情。')
        st.stop()
    etf_filter = st.selectbox('关联ETF / ETF', ['全部'] + sorted(alpha.etf.unique().tolist()))
    if etf_filter != '全部':
        alpha = alpha[alpha.etf == etf_filter]
    only_positive = st.checkbox(f'仅显示{period}日超额收益为正的股票', value=False)
    if only_positive:
        alpha = alpha[alpha.alpha_window > 0]
    show_records(alpha, {
        'etf':'关联ETF','ticker':'股票','symbol':'iFinD代码','weight_pct':'持仓快照权重(%)',
        'date':'行情日期','age_sessions':'缺失交易日','position':'相对位置',
        'stock_ret_window':f'股票{period}日收益','etf_ret_window':f'ETF{period}日收益',
        'alpha_window':f'观察期{period}日超额','alpha_5':'5日超额','alpha_20':'20日超额','alpha_60':'60日超额',
    }, pct_cols=['stock_ret_window','etf_ret_window','alpha_window','alpha_5','alpha_20','alpha_60'],
        round_cols=['weight_pct'], height=480)
    st.download_button('导出个股Alpha研究表', data=table_download(alpha),
                       file_name=f'USERM_stock_alpha_{period}D_{stock_day.date()}.csv', mime='text/csv')
    st.caption('个股和ETF均须在观察期首尾有真实行情，缺日不前向填充。超额收益不是未来收益预测。')
    if not alpha.empty:
        leader = alpha.iloc[0]
        st.markdown(f"示例观察对象：**{leader['ticker']}**（关联 **{leader['etf']}**） · "
                    f"[TradingView 股票图]({tradingview_url(leader['ticker'])})")

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
        e, s = quality.get('etfs', {}), quality.get('stocks', {})
        cols = st.columns(4)
        cols[0].metric('ETF行数', f"{e.get('rows', 0):,}")
        cols[1].metric('ETF数量', f"{e.get('symbols_found', 0)}/20")
        cols[2].metric('股票行数', f"{s.get('rows', 0):,}")
        cols[3].metric('股票代码', str(s.get('symbols_found', 0)))
        st.caption(f"ETF latest: {e.get('max_date','?')} | Stock latest: {s.get('max_date','?')} "
                   f"| Snapshot generated UTC: {quality.get('generated_utc','?')}")
    details = snapshot[['etf','date','age_sessions','fresh','peer_count','partition','rvol_20','rotation_rank']].sort_values('etf')
    st.dataframe(details, use_container_width=True, hide_index=True)
    st.markdown('''1. CPS:2为原数据标记的复权价格；现金分红总回报口径未独立核验，不能作为实际委托价。
2. ETF持仓和指数成分表均为单次快照，不具备历史逐日时点有效性。历史个股Alpha仅供事后描述。
3. 观察周期严格按ETF市场交易日计算，不用上一条可得价格替代缺失端点。
4. 未设置机器学习、反转打分、历史交易事件回测或自动交易功能。
5. 仓库中的行情数据可能受iFinD授权限制；网页是否可公开访问由部署环境决定。''')
    st.caption('详细方法：METHODS_ROTATION.md、README.md、DATA_QUALITY.md')

st.divider()
st.caption('USERM V1.2 | ETF relative-rotation and stock Alpha research only · Offline EOD snapshot · No execution')
