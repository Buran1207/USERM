"""USERM presentation inspired by the existing HKERM Streamlit design."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
.tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:1.5px;color:#8c1d28}
</style>'''

TRANS = {
    'ETF市场总览': 'ETF Overview', 'ETF轮动地图': 'Rotation Map',
    '方法与数据质量': 'Methods & Data Quality',
    '行业': 'Sector', '科技主题': 'Tech Theme', '全部': 'All',
    '领先强化': 'Leading', '领先减弱': 'Weakening',
    '落后改善': 'Improving', '落后持续': 'Lagging',
    '历史不足': 'Insufficient history', '行情过期': 'Stale data',
    '领先': 'Leading', '落后': 'Lagging',
}

def tt(value, english=False):
    return TRANS.get(str(value), str(value)) if english else str(value)

def fmt_pct(value):
    return f'{value*100:+.2f}%' if pd.notna(value) else '—'

def figstyle(fig, height=420):
    fig.update_layout(height=height, margin=dict(l=15, r=15, t=40, b=20),
        font=dict(family='Arial, Microsoft YaHei, sans-serif', size=12, color='#243246'),
        paper_bgcolor='white', plot_bgcolor='white', hovermode='closest',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
    fig.update_xaxes(showgrid=True, gridcolor='#EEF1F5', zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor='#EEF1F5', zeroline=False)
    return fig

def rotation_map(current: pd.DataFrame, trails: pd.DataFrame | None = None, english=False):
    """Four tinted quadrants and latest-date-color trails (StockCharts-style)."""
    colors = {'LEADING':'#21845f','IMPROVING':'#2767d0',
              'WEAKENING':'#ca9327','LAGGING':'#df4039'}
    backgrounds = {'LEADING':'rgba(69,167,92,0.19)',
                   'IMPROVING':'rgba(64,90,213,0.17)',
                   'WEAKENING':'rgba(235,188,72,0.18)',
                   'LAGGING':'rgba(242,87,89,0.17)'}
    valid=current[current.fresh].dropna(subset=['rs_ratio','rs_momentum'])
    fig=go.Figure()
    displayed = [valid[['rs_ratio','rs_momentum']]]
    if trails is not None and not trails.empty:
        displayed += [trails[['rs_ratio','rs_momentum']].dropna()]
    values = pd.concat(displayed, ignore_index=True).replace([float('inf'),float('-inf')],float('nan')).dropna()
    if values.empty:
        return figstyle(fig, 590)
    xmin = min(98.5,float(values.rs_ratio.min()))
    xmax = max(101.5,float(values.rs_ratio.max()))
    ymin = min(99.5,float(values.rs_momentum.min()))
    ymax = max(100.5,float(values.rs_momentum.max()))
    dx = max(0.6,(xmax-xmin)*0.08); dy = max(0.2,(ymax-ymin)*0.12)
    xmin-=dx; xmax+=dx; ymin-=dy; ymax+=dy
    for quad,x0,x1,y0,y1 in [
        ('IMPROVING',xmin,100,100,ymax),('LEADING',100,xmax,100,ymax),
        ('LAGGING',xmin,100,ymin,100),('WEAKENING',100,xmax,ymin,100)]:
        if x1 > x0 and y1 > y0:
            fig.add_shape(type='rect',x0=x0,x1=x1,y0=y0,y1=y1,
                          line=dict(width=0),fillcolor=backgrounds[quad],layer='below')
    fig.add_hline(y=100,line_width=1.3,line_color='#333d48')
    fig.add_vline(x=100,line_width=1.3,line_color='#333d48')
    for name,xx,yy,anchor in [
        ('Improving',xmin+dx*.5,ymax-dy*.5,'left'),
        ('Leading',xmax-dx*.5,ymax-dy*.5,'right'),
        ('Lagging',xmin+dx*.5,ymin+dy*.5,'left'),
        ('Weakening',xmax-dx*.5,ymin+dy*.5,'right')]:
        q=name.upper()
        fig.add_annotation(x=xx,y=yy,text=f'<b>{name}</b>',showarrow=False,
                           xanchor=anchor,font=dict(color=colors[q],size=16))
    for _,row in valid.iterrows():
        code=row.etf; quad=row.quadrant; color=colors.get(quad,'#9299a3')
        if trails is not None and not trails.empty:
            track=trails[trails.etf==code].sort_values('date').dropna(subset=['rs_ratio','rs_momentum'])
            if len(track)>1:
                fig.add_trace(go.Scatter(
                    x=track.rs_ratio,y=track.rs_momentum,
                    mode='lines+markers',showlegend=False,name=f'{code} trail',
                    line=dict(color=color,width=2.5),marker=dict(color=color,size=5),
                    customdata=track.date.dt.strftime('%Y-%m-%d'),
                    hovertemplate=f'{code} %{{customdata}}<br>X %{{x:.2f}}<br>Y %{{y:.2f}}<extra></extra>'))
        fig.add_trace(go.Scatter(
            x=[row.rs_ratio],y=[row.rs_momentum],mode='markers+text',
            text=[code],textposition='middle right',showlegend=False,
            marker=dict(size=12,color=color,line=dict(width=1,color='#fff')),
            hovertemplate=f'<b>{code}</b><br>X %{{x:.2f}}<br>Y %{{y:.2f}}<extra></extra>'))
    fig.update_xaxes(title_text='RRG-style RS-Ratio (100 = neutral)',range=[xmin,xmax])
    fig.update_yaxes(title_text='RRG-style RS-Momentum (100 = neutral)',range=[ymin,ymax])
    return figstyle(fig,610)

def price_chart(chart_data: pd.DataFrame, symbol: str, observation_days: int):
    g = chart_data.copy()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.1,
                        row_heights=[.72, .28])
    fig.add_trace(go.Scatter(x=g.date, y=g.close, name='CPS2 close',
                             line=dict(color='#18344e', width=2)), row=1, col=1)
    for h, color in [(20, '#C58A44'), (50, '#8C1D28')]:
        fig.add_trace(go.Scatter(x=g.date, y=g[f'ma_{h}'], name=f'MA{h}',
                                 line=dict(color=color, width=1.5)), row=1, col=1)
    excess = g.rel_window * 100
    fig.add_trace(go.Bar(x=g.date, y=excess,
        marker_color=['#288973' if v >= 0 else '#B95C68' for v in excess.fillna(0)],
        name=f'{observation_days}D excess (pp)'), row=2, col=1)
    fig.update_yaxes(title_text='CPS2 price', row=1, col=1)
    fig.update_yaxes(title_text=f'{observation_days}D excess pp', row=2, col=1)
    fig.update_layout(title=f'{symbol} · adjusted close, MA20/MA50 and {observation_days}D relative return')
    return figstyle(fig, 530)

def table_download(frame: pd.DataFrame):
    return frame.to_csv(index=False).encode('utf-8-sig')

