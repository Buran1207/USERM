"""USERM | US ETF Rotation & Reversal Monitor

A research-only Streamlit derivative of the user's HKERM workflow.
No data extraction, credentials, proprietary strategy replication, machine learning,
or order placement. Every signal uses completed daily bars only.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from userm.config import STAGES,QUADRANTS,STAGE_COLORS,DATA
from userm.data import load_quotes,load_etf_master,load_holdings,manifest,table
from userm.signals import calculate_etf_signals,latest_table
from userm.stocks import alpha_table
from userm.validation import event_study,event_summary
from userm.ui import CSS,tt,fmt_pct,figstyle,rotation_map,price_chart,table_download,tradingview_url

st.set_page_config(page_title="USERM | US ETF Rotation Monitor",page_icon="📈",layout="wide",initial_sidebar_state="expanded")
st.markdown(CSS,unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_signals():
    m=load_etf_master()
    q=load_quotes('etfs')
    return calculate_etf_signals(q,m),m

@st.cache_data(show_spinner=False)
def cached_stocks():
    return load_quotes('stocks')

@st.cache_data(show_spinner=False)
def cached_events(s:pd.DataFrame):
    return event_study(s)


def show_records(data:pd.DataFrame, cols:dict, pct_cols=(),round_cols=(), height=350):
    if data.empty:
        st.info('没有符合条件的数据 / No eligible data');return
    f=data[list(cols)].rename(columns=cols).copy()
    for key in pct_cols:
        alias=cols.get(key,key)
        if alias in f:f[alias]=f[alias].map(fmt_pct)
    for key in round_cols:
        alias=cols.get(key,key)
        if alias in f:f[alias]=f[alias].apply(lambda x: f'{x:.2f}' if pd.notna(x) else '—')
    st.dataframe(f,use_container_width=True,hide_index=True,height=height)

try:
    signals,master=cached_signals()
except Exception as exc:
    st.error(f'ETF数据加载失败 / Failed to load ETF data: {exc}')
    st.info('请确认仓库内 data/etf_prices.csv.gz、data/etf_codes.csv、data/etfs.csv 均已上传。')
    st.stop()

cal=pd.DatetimeIndex(sorted(signals.date.unique()))
latest=cal.max()
manifest_info=manifest()
stock_latest=pd.Timestamp(manifest_info.get('stocks',{}).get('max_date','1900-01-01'))

with st.sidebar:
    st.markdown('<span style="color:#b98d8f;font-size:12px;letter-spacing:2px;font-weight:800">USERM · V1.0</span>',unsafe_allow_html=True)
    st.markdown('### US EQUITY ROTATION')
    lang=st.selectbox('Language / 语言',['中文','English'],index=0)
    EN=lang=='English'
    page_items=['ETF市场总览','ETF轮动地图','ETF反转机会','个股Alpha','历史事件验证','方法与数据质量']
    page=st.radio('工作页面 / Workspace',page_items,format_func=lambda v:tt(v,EN))
    requested=st.date_input('研究截止日 / As of',value=latest.date(),min_value=cal.min().date(),max_value=latest.date())
    chosen=pd.Timestamp(requested)
    asof=cal[cal<=chosen].max()
    if asof != chosen: st.caption(f'已回退至最近ETF交易日 / Effective session: {asof.date()}')
    group=st.selectbox('ETF分组 / ETF family',['全部','行业','科技主题'],format_func=lambda v:tt(v,EN))
    st.caption('数据本地计算，网页只读 · No live execution or data fetching')
    st.caption(f'ETF latest: {latest.date()}')
    st.caption(f'Stock latest: {stock_latest.date()}')

snap=latest_table(signals,asof,cal)
if group != '全部':snap=snap[snap.group==group]
fresh=snap[snap.fresh].copy()

st.markdown('<div class="tag">USERM | US EQUITY ROTATION & REVERSAL</div>',unsafe_allow_html=True)
st.title(tt(page,EN))
st.caption(f"20 ETF Core Universe  ·  CPS:2 adjusted daily prices  ·  {asof:%Y-%m-%d} EOD  ·  No machine learning")
if asof==latest and (pd.Timestamp.today().normalize()-latest).days>7:
    st.warning('ETF数据距离当前日期超过7天；请先离线刷新数据。本网页不会自动取得行情。')

if page=='ETF市场总览':
    mcols=st.columns(4)
    mcols[0].metric('ETF有效数 / Fresh ETFs',f'{len(fresh)}/{len(snap)}')
    mcols[1].metric('L1/L2 · Early',int(fresh.stage.isin(['L1','L2']).sum()))
    mcols[2].metric('L3/L4 · Strong',int(fresh.stage.isin(['L3','L4']).sum()))
    mcols[3].metric('W · Risk',int((fresh.stage=='W').sum()))
    st.info('本页的Alpha为ETF相对同组其他ETF等权日收益基准的超额收益，并不是对标普500或纳指100的超额收益。相对强势≠必然上涨。')
    st.subheader('ETF轮动与交易研究清单')
    show_records(fresh,{'etf':'ETF','name_zh':'方向','group':'分组','stage':'信号','quadrant':'轮动象限',
        'rotation_rank':'组内名次','rotation_score':'轮动分数','ret_5':'5日收益','rel_5':'5日超额',
        'rel_20':'20日超额','rel_60':'60日超额','rvol_20':'量比'},
        pct_cols=['ret_5','rel_5','rel_20','rel_60'],round_cols=['rotation_rank','rotation_score','rvol_20'],height=460)
    st.download_button('下载ETF当前面板 CSV',data=table_download(fresh),file_name=f'USERM_etf_panel_{asof.date()}.csv',mime='text/csv')
    left,right=st.columns([1.2,1])
    with left:
        st.subheader('短期与中期相对表现')
        dd=fresh.sort_values('rel_5',ascending=False).copy()
        dd['5日超额(pp)']=100*dd.rel_5;dd['20日超额(pp)']=100*dd.rel_20
        fig=go.Figure()
        fig.add_trace(go.Bar(y=dd.etf,x=dd['5日超额(pp)'],name='5D',orientation='h',marker_color='#8C1D28'))
        fig.add_trace(go.Bar(y=dd.etf,x=dd['20日超额(pp)'],name='20D',orientation='h',marker_color='#A6B4C2'))
        fig.update_layout(barmode='group',yaxis=dict(autorange='reversed'),xaxis_title='Percentage points versus peer equal-weight basket')
        st.plotly_chart(figstyle(fig,540),use_container_width=True)
    with right:
        st.subheader('信号分布')
        c=fresh.groupby(['group','stage']).size().reset_index(name='ETF数')
        if not c.empty:
            fig=px.bar(c,x='group',y='ETF数',color='stage',barmode='stack',color_discrete_map=STAGE_COLORS,
                       category_orders={'stage':['L1','L2','L3','L4','W','N0','NA']})
            st.plotly_chart(figstyle(fig,350),use_container_width=True)
        st.markdown('**最新变化 / Stage transitions**')
        new=fresh[fresh.new_signal].sort_values(['group','stage','etf'])
        if new.empty:st.caption('本日无新状态切换；已有信号仍可能延续。')
        else:show_records(new,{'etf':'ETF','group':'组别','stage':'新状态','reason':'触发依据'},height=230)
    st.subheader('ETF价格与信号复核')
    pick=st.selectbox('研究对象 / Symbol',snap.etf.tolist(),index=0)
    st.plotly_chart(price_chart(signals,asof,pick),use_container_width=True)
    st.caption('图中均为CPS:2历史调整价格，不等于实际委托价。红/绿色标记仅表示当日收盘后规则发生状态切换。')

elif page=='ETF轮动地图':
    st.info('RRG风格四象限：横轴为相对强度EMA(14)/EMA(36)之比，纵轴为该比值5日变化。100是中性线；这是公开定义的自有近似公式，并非JdK专有指标。')
    selected=st.multiselect('历史轨迹 / Trails',fresh.etf.tolist(),default=fresh.etf.head(2).tolist(),max_selections=4)
    n=st.slider('轨迹长度 / Lookback sessions',5,40,15)
    trails=signals[(signals.etf.isin(selected))&(signals.date<=asof)].groupby('etf',group_keys=False).tail(n)
    st.plotly_chart(rotation_map(snap,trails,EN),use_container_width=True)
    st.subheader('象限与转向')
    show_records(fresh,{'etf':'ETF','name_zh':'方向','quadrant':'象限','rs_ratio':'RS趋势','rs_momentum':'RS动量','rel_5':'5日超额','rel_20':'20日超额','stage':'信号'},
        pct_cols=['rel_5','rel_20'],round_cols=['rs_ratio','rs_momentum'],height=460)
    st.caption('移动至“落后改善”不等于底部确认。L2/L3信号还要求价格及趋势条件。')

elif page=='ETF反转机会':
    filter_stages=st.multiselect('状态筛选 / Stages',options=['L1','L2','L3','L4','W','N0'],default=['L1','L2','L3','L4','W'],format_func=lambda v:f'{v} {tt(STAGES[v],EN)}')
    only_new=st.checkbox('仅本交易日新触发 / Today-only transitions',value=False)
    d=fresh[fresh.stage.isin(filter_stages)]
    if only_new:d=d[d.new_signal]
    show_records(d,{'etf':'ETF','name_zh':'方向','group':'组别','stage':'信号','stage_age':'本状态持续天数',
        'rel_5':'5日超额','rel_10':'10日超额','rel_20':'20日超额',
        'rs_ratio':'RS趋势','rs_momentum':'RS动量','rvol_20':'相对量比','reason':'触发解释'},
        pct_cols=['rel_5','rel_10','rel_20'],round_cols=['rs_ratio','rs_momentum','rvol_20'],height=460)
    st.download_button('导出候选清单 / Export',data=table_download(d),file_name=f'USERM_alerts_{asof.date()}.csv',mime='text/csv')
    st.subheader('信号历史与失效观察')
    codes=d.etf.tolist() if not d.empty else snap.etf.tolist()
    etf=st.selectbox('ETF',codes)
    hist=signals[(signals.etf==etf)&(signals.date<=asof)].sort_values('date')
    changes=hist[hist.new_signal].tail(25).sort_values('date',ascending=False)
    show_records(changes,{'date':'收盘触发日','stage':'状态','quadrant':'象限','rel_5':'5日超额','reason':'规则解释'},pct_cols=['rel_5'],height=340)
    st.plotly_chart(price_chart(signals,asof,etf),use_container_width=True)
    st.warning('L1/L2为研究预警，L3/L4亦不是自动买入指令；风险警示W不是卖空信号。真实订单需另行考虑未复权价格、滑点、持仓和止损。')

elif page=='个股Alpha':
    st.markdown('**筛选范围：20只ETF在上传的2026-11-02持仓快照中的前五大持仓。** 未有完整持仓的部分不强行声称已覆盖全部成分股。')
    if stock_latest<asof:
        missing=int(((cal>stock_latest)&(cal<=asof)).sum())
        st.error(f'个股行情落后ETF市场 {missing} 个交易日（股票最新 {stock_latest.date()}；ETF {asof.date()}）。**当前无法输出可交易的最新个股Alpha候选。** 以下仅可切换至有行情的历史研究日。')
    effective=min(stock_latest,asof)
    if effective < cal.min():st.stop()
    stock_day=st.date_input('个股观察日 / Stock review date',value=effective.date(),min_value=cal.min().date(),max_value=effective.date())
    stock_day=cal[cal<=pd.Timestamp(stock_day)].max()
    holdings=load_holdings()
    if stock_day<pd.Timestamp(holdings.holdings_asof.dropna().max()):
        st.warning('重要：ETF持仓关系来自2026-11-02单次快照，晚于所选个股研究日。历史股票对比只是事后描述，不能当作当时已知的ETF持仓或无偏回测。')
    stocks=cached_stocks()
    alpha=alpha_table(stocks,signals,holdings,stock_day,cal)
    if alpha.empty:st.info('该日期没有匹配行情。');st.stop()
    stock_filter=st.selectbox('关联ETF / ETF',['全部']+sorted(alpha.etf.unique().tolist()))
    if stock_filter!='全部':alpha=alpha[alpha.etf==stock_filter]
    only_signal=st.checkbox('仅显示有信号个股 / Signals only',value=False)
    if only_signal:alpha=alpha[alpha.stock_signal.isin(['个股强势突破','个股持续领先','个股反转观察'])]
    show_records(alpha,{'etf':'关联ETF','ticker':'股票','symbol':'iFinD代码','weight_pct':'快照权重(%)',
        'date':'实际价格日','age_sessions':'缺失交易日','stock_signal':'个股状态',
        'stock_ret_5':'5日涨幅','alpha_5':'5日超额','alpha_20':'20日超额','alpha_60':'60日超额',
        'rvol20':'量比','alpha_strength_pp':'Alpha强度(百分点)'},
        pct_cols=['stock_ret_5','alpha_5','alpha_20','alpha_60'],round_cols=['weight_pct','rvol20','alpha_strength_pp'],height=480)
    st.download_button('导出个股研究表 / Export stocks',data=table_download(alpha),file_name=f'USERM_stock_alpha_{stock_day.date()}.csv',mime='text/csv')
    st.caption('仅对2026-11-02快照中的可解析美国上市证券进行研究；国外股票、无法确定的证券代码和历史缺失记录不强行补造。')
    if not alpha.empty:
        show=alpha.iloc[0]
        st.markdown(f"首位观察对象：**{show['ticker']}** / 关联 **{show['etf']}** · [TradingView 股票图]({tradingview_url(show['ticker'])})")

elif page=='历史事件验证':
    st.warning('这是固定规则的事后事件研究，不是已验证可交易收益：持仓信号相关、可能重叠；不含交易成本/卖出规则。2026分区为文件中的OOS标签，但在已观察过2026数据后不得再次宣称为完全未接触的前瞻样本外检验。')
    events=cached_events(signals)
    period=st.radio('研究分区 / Partition',['2026 OOS partition','2020–2025 TRAIN'],horizontal=True)
    horizon=st.selectbox('信号后持有天数 / Holding sessions',[5,10,20],index=1)
    summary=event_summary(events,horizon=horizon,period=period)
    show_records(summary,{'group':'组别','stage':'触发等级','count':'事件数','win_rate':'正收益比例',
                          'alpha_hit_rate':'超额收益正比例','med_return':'中位数收益','med_alpha':'中位数超额','med_mae':'中位数最大不利波动'},
                 pct_cols=['win_rate','alpha_hit_rate','med_return','med_alpha','med_mae'],height=330)
    st.caption(f'执行假设：信号在T日收盘后可见，T+1日收盘买入，持有{horizon}个完整交易间隔至T+{horizon+1}日收盘；对照组为同组剔除自身的ETF等权组合。')
    if not summary.empty:
        summary=summary.copy();summary['med_alpha_pp']=summary.med_alpha*100
        fig=px.bar(summary,x='stage',y='med_alpha_pp',color='group',barmode='group',
                   labels={'y':'Median forward excess (pp)','stage':'Signal stage'})
        st.plotly_chart(figstyle(fig,380),use_container_width=True)
    recent=events[(events.period==period)&events[f'forward_{horizon}'].notna()].sort_values('date',ascending=False)
    st.subheader('事件逐笔记录 / Event ledger')
    show_records(recent.head(200),{'date':'触发日','etf':'ETF','stage':'状态',
                  f'forward_{horizon}':f'后{horizon}日收益',f'excess_{horizon}':f'后{horizon}日超额',
                  f'mae_{horizon}':f'后{horizon}日最大不利波动'},
                 pct_cols=[f'forward_{horizon}',f'excess_{horizon}',f'mae_{horizon}'],height=370)
    st.download_button('导出全部历史事件 / Export events',data=table_download(events),file_name='USERM_history_events.csv',mime='text/csv')

elif page=='方法与数据质量':
    st.subheader('信号规则速览')
    st.markdown('''**基准**：同组其他ETF每日收益等权平均，逐日链式构造100起点的研究基准；剔除被评分ETF自身。不是标普500、纳指100或任何可投资ETF价格。''')
    st.latex(r"r^{peer}_{i,t}=\frac{1}{N_{t}-1}\sum_{j\ne i}r_{j,t},\quad RS_{i,t}=\frac{P_{i,t}}{B_{i,t}}")
    st.markdown('**四象限（自有透明近似，不是JdK专有算法）**')
    st.latex(r"X_t=100\exp\left(EMA_{14}(\ln RS_t)-EMA_{36}(\ln RS_t)\right),\quad Y_t=100\frac{X_t}{X_{t-5}}")
    st.markdown('''- **L1 早期异动：** X<100，Y≥100.05，5日超额收益>0。
- **L2 反转候选：** Y≥100.05，5/10日超额收益>0，5日绝对收益>0，收盘价>10日均线，且X<100.25。
- **L3 突破确认：** X>100，Y≥100，10日超额收益>0，收盘>MA20>MA50，突破前20日最高价，量比≥1.15。
- **L4 强势延续：** X>100，20/60日超额收益>0，收盘>MA20>MA50。
- **W 风险警示：** 过去5个交易日内曾有L3/L4，当前收盘价<MA20、5日超额收益<0、Y<100。
- **N0/NA：** 不触发 / 关键历史不足。信号优先级为L3 → L4 → W → L2 → L1 → N0。''')
    st.markdown('''**轮动分数**：同组内5日超额收益百分位×25% + 20日超额收益百分位×35% + 60日超额收益百分位×40%，区间0–100；只代表相对排序，不是上涨概率或预测收益。''')
    st.markdown('**样本和日期质量**')
    if manifest_info:
        a,b=manifest_info.get('etfs',{}),manifest_info.get('stocks',{})
        qa=st.columns(4)
        qa[0].metric('ETF行数',f"{a.get('rows',0):,}")
        qa[1].metric('ETF覆盖',f"{a.get('symbols_found',0)}/20")
        qa[2].metric('股票行数',f"{b.get('rows',0):,}")
        qa[3].metric('个股代码',str(b.get('symbols_found',0)))
        st.caption(f"ETF last: {a.get('max_date','?')} | Stock last: {b.get('max_date','?')} | ZIP snapshot created UTC: {manifest_info.get('generated_utc','?')}")
    inspect=snap[['etf','date','age_sessions','fresh','peer_count','partition','rvol_20','stage']].sort_values('etf')
    st.dataframe(inspect,use_container_width=True,hide_index=True)
    st.markdown('''**强制数据边界说明**

1. 输入为上传的CPS:2价格，不能独立保证现金分红已按总回报调整。没有原始未复权价格，不提供实际交易限价。
2. `metadata_bd.zip` 的标记是 `pit_verified=false`、`split_dividend_event_history_verified=false`，故不用于历史复权验证或预测。
3. 两份指数成分名单与2026-11-02 ETF前五持仓均是单次快照，**不能当作历史真实持仓**。股票Alpha页面不提供无偏历史回测。
4. ETF组基准使用历史上“今天这20只ETF”的固定池，包含幸存者/产品存续偏差；不同成立时间ETF无法在早期提供信号。
5. 当日行情缺失则不前向填充；最新缺失超过2个有效交易日的ETF会被标记过期。股票必须与ETF同日有价格才能成为候选。
6. 历史验证不含滑点、费用、成交约束、证券借贷及卖出执行规则。日终数据的交易最早是下一交易日。
7. ETF前五大持仓可能包括非美国上市股票及基金，未解析的证券代码留空，不虚构数据。''')
    st.caption('研究说明完整文件：METHODS_SIGNALS.md、README.md、DATA_QUALITY.md')

st.divider()
st.caption('USERM | Research support only · No discretionary allocation, return forecast, investment advice or trade execution · Sources: provided HKERM + CPS2 archives + supplied constituents/ETF snapshot')
