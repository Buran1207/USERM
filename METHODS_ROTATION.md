# USERM V1.3｜ETF-only轮动计算方法

## A. 研究对象

只使用20只ETF：11只行业ETF（XLC、XLY、XLP、XLE、XLF、XLV、XLI、XLB、VGT、XLU、VNQ）与9只科技主题ETF（SMH、IGV、CIBR、BAI、SKYY、DTCR、BOTZ、QTUM、GRID）。具体代码、iFinD后缀见 `data/etfs.csv`、`data/etf_codes.csv`。不再包含任何个股分析、指数成分或ETF持仓模块。

## B. 同组基准

ETF i 的同组其余ETF（剔除i自身）日收益等权平均，需至少3个有效同行样本：

`r_peer(i,t) = mean_{j in same group, j != i} [P(j,t)/P(j,t-1)-1]`

按日连乘为ETF专属的同行价格指数 `B(i,t)`。这不是官方指数，亦非资金流或交易强度的直接测量。若同行数据不足则基准当日标记缺失，不凭空补入一个可交易价格。

## C. RRG坐标（固定）

`RS(i,t) = P(i,t)/B(i,t)`

`X(i,t) = 100 * exp[ EMA14(ln RS(i,t)) - EMA36(ln RS(i,t)) ]`

`Y(i,t) = 100 * X(i,t) / X(i,t-5)`

- X≥100且Y≥100：领先强化。
- X≥100且Y<100：领先减弱。
- X<100且Y≥100：落后改善。
- X<100且Y<100：落后持续。

EMA使用 `pandas.Series.ewm(span=...,adjust=False,min_periods=span)`；数据不足显示“历史不足”。Y>100仅表示相对趋势指标近5日提高，不保证ETF绝对价格上涨。此为USERM公开可解释的近似RRG，不是StockCharts专有JdK公式。

## D. 自选观察周期（1–60交易日）

在所选研究日t和观察周期n，计算：

`R(i,n,t) = P(i,t)/P(i,t-n)-1`

`R_peer(i,n,t) = B(i,t)/B(i,t-n)-1`

`Excess(i,n,t) = R(i,n,t)-R_peer(i,n,t)`

组内按Excess降序计算名次，`rotation_score` 为组内百分位*100（**不是上涨概率**）。改变观察周期会改变收益、超额、排名、柱状图、ETF价格附图；不改变RRG EMA14/36与5日变化的窗口。日期t-n为ETF市场交易日历上的真正n个交易日之前；缺失首尾价格不前向填充，过期ETF不参与当日排名。

## E. 数据范围与EOD安全

Streamlit只读已生成的 `etf_prices.csv.gz`，不调用API；数据来自CPS2，现金分红总回报口径尚未独立核验，不应把复权价直接当作交易委托价。

本地 `scripts/refresh_data.py` 只读已完成下载的本地CPS2行情，使用NYSE交易日历及收盘后90分钟缓冲剔除未完成的交易日。最后可发布日必须有20/20 ETF行情，且不得早于旧快照日期。即使所选研究日为非交易日，网页也只会回退至此前已观测的交易日。

## F. 边界

没有大盘反转雷达、L1–L4信号、股票Alpha、个股研究、机器学习、自动交易、预测收益及历史事件回测。四象限只是对ETF相对状态的描述，不是买卖指令。分组内部同行基准不是全市场指数：当行业ETF整体下跌时，表现相对较强的ETF自身也可能下跌。

参考阅读：StockCharts Relative Rotation Graphs (RRG) 对相对趋势及相对动量的定义：https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts
