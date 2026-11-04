"""Presentation helpers adapted from HKERM Streamlit's dark-sidebar, bilingual,
RRG-trail, security-explorer and CSV-export interaction patterns.
"""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .config import STAGE_COLORS,STAGES,QUADRANTS

CSS='''<style>
.block-container{padding-top:1.15rem;padding-bottom:2rem;max-width:1510px}
[data-testid="stSidebar"]{background:#172337}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] .stCaption{color:#ecf3fa!important}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#fff!important}
[data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"],
[data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"] *,
[data-testid="stSidebar"] [data-baseweb="select"] input{color:#202d42!important;-webkit-text-fill-color:#202d42!important}
[data-baseweb="popover"] [role="option"], [data-baseweb="popover"] [role="option"] *{color:#202d42!important}
h1,h2,h3{letter-spacing:-.025em}h1{font-weight:780!important}
[data-testid="stMetric"]{background:#f6f7f9;border:1px solid #e3e6ea;padding:13px;border-radius:10px}
.smallnote{font-size:12px;color:#68788c}
.tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:1.5px;color:#8c1d28}
</style>'''

TRANS={
"ETF市场总览":"ETF Overview","ETF轮动地图":"Rotation Map","ETF反转机会":"ETF Reversal Alerts",
"个股Alpha":"Stock Alpha","历史事件验证":"Historical Event Study","方法与数据质量":"Methods & Data Quality",
"行业":"Sector","科技主题":"Tech Theme","全部":"All","领先强化":"Leading",
"领先减弱":"Weakening","落后改善":"Improving","落后持续":"Lagging","历史不足":"Insufficient",
"无触发":"Neutral","早期异动":"Early improvement","反转候选":"Reversal candidate",
"突破确认":"Breakout confirmation","强势延续":"Trend continuation","风险警示":"Risk warning",
"行情过期":"Stale data","暂无触发":"No trigger","个股强势突破":"Stock breakout",
"个股持续领先":"Stock leadership","个股反转观察":"Stock reversal watch","近期轮动":"Recent rotation"
}

def tt(v,english=False):
    return TRANS.get(str(v),str(v)) if english else str(v)


def fmt_pct(v):
    return f"{v*100:+.2f}%" if pd.notna(v) else "—"


def figstyle(fig, height=420):
    fig.update_layout(height=height,margin=dict(l=15,r=15,t=40,b=20),
       font=dict(family='Arial, Microsoft YaHei, sans-serif',size=12,color='#243246'),
       paper_bgcolor='white',plot_bgcolor='white',hovermode='closest',
       legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1))
    fig.update_xaxes(showgrid=True,gridcolor='#EEF1F5',zeroline=False)
    fig.update_yaxes(showgrid=True,gridcolor='#EEF1F5',zeroline=False)
    return fig


def rotation_map(d:pd.DataFrame, trails:pd.DataFrame|None=None,english=False):
    fig=go.Figure()
    fig.add_hline(y=100,line_width=1,line_dash='dot',line_color='#8f9baa')
    fig.add_vline(x=100,line_width=1,line_dash='dot',line_color='#8f9baa')
    labels={'LEADING':'Leading / 领先强化','WEAKENING':'Weakening / 领先减弱',
            'IMPROVING':'Improving / 落后改善','LAGGING':'Lagging / 落后持续'}
    for i,quad in enumerate(['LEADING','IMPROVING','WEAKENING','LAGGING']):
        g=d[(d.quadrant==quad)&d.fresh]
        if g.empty:continue
        fig.add_trace(go.Scatter(x=g.rs_ratio,y=g.rs_momentum,mode='markers+text',name=labels[quad],
            text=g.etf,textposition='top center',textfont=dict(size=11),
            marker=dict(size=13,color={'LEADING':'#207A65','IMPROVING':'#3478B0','WEAKENING':'#C48E43','LAGGING':'#B04A52'}[quad],
                line=dict(width=1,color='#ffffff')),
            customdata=g[['name_zh','stage','rel_5','rel_20']].to_numpy(),
            hovertemplate='<b>%{text}</b> %{customdata[0]}<br>RS ratio %{x:.2f}<br>RS momentum %{y:.2f}<br>stage %{customdata[1]}<br>5d excess %{customdata[2]:+.2%}<br>20d excess %{customdata[3]:+.2%}<extra></extra>'))
    if trails is not None and not trails.empty:
        for name,g in trails.groupby('etf'):
            g=g.dropna(subset=['rs_ratio','rs_momentum']).sort_values('date')
            if len(g)<2:continue
            fig.add_trace(go.Scatter(x=g.rs_ratio,y=g.rs_momentum,mode='lines+markers',
                name=f'{name} trail',line=dict(color='#8C1D28',width=2),
                marker=dict(color='#8C1D28',size=4),opacity=.65,showlegend=False,
                hovertemplate=name+' %{x:.2f}, %{y:.2f}<extra></extra>'))
    fig.update_layout(xaxis_title='Relative strength trend (100=neutral)',
            yaxis_title='Relative momentum (100=neutral)')
    return figstyle(fig,570)


def price_chart(d:pd.DataFrame,asof, ticker:str):
    g=d[(d.etf==ticker)&(d.date<=pd.Timestamp(asof))].sort_values('date').tail(260)
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.1,row_heights=[.72,.28])
    fig.add_trace(go.Scatter(x=g.date,y=g.close,name='CPS2 close',line=dict(color='#18344e',width=2)),row=1,col=1)
    for n,color in [(20,'#C58A44'),(50,'#8C1D28')]:
        fig.add_trace(go.Scatter(x=g.date,y=g[f'ma_{n}'],name=f'MA{n}',line=dict(color=color,width=1.5)),row=1,col=1)
    for label,color in [('L1','#D3A15E'),('L2','#B15B43'),('L3','#8C1D28'),('L4','#2C7B65'),('W','#B22222')]:
        events=g[(g.stage==label)&(g.new_signal)]
        if not events.empty:
            fig.add_trace(go.Scatter(x=events.date,y=events.close,mode='markers',name=label,
                marker=dict(color=color,size=10,symbol='diamond'),
                hovertemplate='%{x|%Y-%m-%d}<br>Signal '+label+'<extra></extra>'),row=1,col=1)
    fig.add_trace(go.Bar(x=g.date,y=g.rel_5*100,marker_color=['#288973' if a>=0 else '#B95C68' for a in g.rel_5.fillna(0)],name='5d excess (pp)'),row=2,col=1)
    fig.update_yaxes(title_text='CPS2 price',row=1,col=1)
    fig.update_yaxes(title_text='5D excess pp',row=2,col=1)
    fig.update_layout(title=f'{ticker} · adjusted price, 20/50 day MA & signal transitions')
    return figstyle(fig,530)


def table_download(df:pd.DataFrame,name='USERM_export.csv'):
    return df.to_csv(index=False).encode('utf-8-sig')


def tradingview_url(symbol):
    """Open a general public ticker search; no exchange mapping asserted."""
    from urllib.parse import quote
    return f"https://www.tradingview.com/symbols/{quote(str(symbol).split('.')[0])}/"
