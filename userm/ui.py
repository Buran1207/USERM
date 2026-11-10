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
    fig = go.Figure()
    fig.add_hline(y=100, line_width=1, line_dash='dot', line_color='#8f9baa')
    fig.add_vline(x=100, line_width=1, line_dash='dot', line_color='#8f9baa')
    labels = {
        'LEADING': 'Leading / 领先强化', 'WEAKENING': 'Weakening / 领先减弱',
        'IMPROVING': 'Improving / 落后改善', 'LAGGING': 'Lagging / 落后持续',
    }
    for quadrant in ['LEADING', 'IMPROVING', 'WEAKENING', 'LAGGING']:
        d = current[(current.quadrant == quadrant) & current.fresh]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d.rs_ratio, y=d.rs_momentum, mode='markers+text', name=labels[quadrant],
            text=d.etf, textposition='top center', textfont=dict(size=11),
            marker=dict(size=13, color={
                'LEADING': '#207A65', 'IMPROVING': '#3478B0',
                'WEAKENING': '#C48E43', 'LAGGING': '#B04A52'}[quadrant],
                line=dict(width=1, color='#ffffff')),
            customdata=d[['name_zh', 'rel_window']].to_numpy(),
            hovertemplate='<b>%{text}</b> %{customdata[0]}<br>RS trend %{x:.2f}<br>RS momentum %{y:.2f}<br>Selected-period excess %{customdata[1]:+.2%}<extra></extra>'
        ))
    if trails is not None and not trails.empty:
        for symbol, group in trails.groupby('etf'):
            group = group.dropna(subset=['rs_ratio', 'rs_momentum']).sort_values('date')
            if len(group) < 2:
                continue
            fig.add_trace(go.Scatter(
                x=group.rs_ratio, y=group.rs_momentum, mode='lines+markers',
                name=f'{symbol} trail', line=dict(color='#8C1D28', width=2),
                marker=dict(color='#8C1D28', size=4), opacity=.65, showlegend=False,
                hovertemplate=symbol+' %{x:.2f}, %{y:.2f}<extra></extra>'
            ))
    fig.update_layout(xaxis_title='Relative strength trend (100=neutral)',
                      yaxis_title='Relative momentum (100=neutral)')
    return figstyle(fig, 570)

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

