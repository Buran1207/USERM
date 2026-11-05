# USERM V1.2｜相对轮动与个股Alpha计算规则

## A. 市场研究范围

- 交易观察核心为11只一级行业ETF与9只科技主题ETF，共20只，代码和分组详见 `data/etfs.csv`。
- ETF排名**仅与同组其他ETF比较**。不以大盘趋势作为交易准入条件。
- 研究对象为ETF及其快照前五大持仓中的可解析美股，不是全ETF成分股。
- 不输出或保存L1–L4、反转胜率、后验交易信号或历史事件绩效。模型只给出**发生了什么**，不预测将发生什么。

## B. 输入和计算次序

1. 读取离线CPS2调整后日OHLCV：日、证券代码、开、高、低、收、成交量。
2. 对每个ETF `i` 取同组其余ETF，计算当日收盘到前收盘的收益，按可得样本**等权平均** `peer_return(i,t)`。最少3个有效同行样本。
3. 从100开始逐日累乘得到ETF专属的 `peer_index(i,t)`，当日同行不足时置缺值，不虚构当日基准价格。
4. RRG坐标使用该基准的相对强度，与观察周期滑块无关。
5. 根据用户所选研究日 `t` 和观察周期 `n`，计算ETF与同行基准的 `t-n → t` 收益及超额，按组内超额高低排名。
6. 个股在其本身和对应ETF都具备`t`与`t-n`原始记录时，计算同区间超额。历史持仓关系来自单次快照，因此仅是描述性分析。

## C. RRG定义

`RS(i,t) = adjusted_close(i,t) / peer_index(i,t)`

`X(i,t) = 100 * exp[EMA14(ln RS(i,t)) - EMA36(ln RS(i,t))]`

`Y(i,t) = 100 * X(i,t) / X(i,t-5)`

- 领先强化：`X >=100, Y>=100`。
- 领先减弱：`X >=100, Y<100`。
- 落后改善：`X <100, Y>=100`。
- 落后持续：`X <100, Y<100`。

`X/Y` 100为中性线。**X>100不保证ETF价格上涨**；Y>100表示5日内X改善，而非价格每天加速上涨。EMA使用 `pandas.Series.ewm(adjust=False, min_periods=span)`，不足36+5个有效历史数据点时不强行绘出四象限。上述是项目自定义的透明近似，非JdK专有计算式。

## D. 观察周期滑块（1–60交易日）

定义 `P(i,t)` 是ETF调整后收盘价，`B(i,t)` 是上述同行基准，`n` 是滑块选中的交易日数量：

`R(i,n,t) = P(i,t)/P(i,t-n)-1`

`Rpeer(i,n,t) = B(i,t)/B(i,t-n)-1`

`A(i,n,t) = R(i,n,t)-Rpeer(i,n,t)`

`Rank(i,n,t) = 同组按A从高到低排序的名次`

`Score(i,n,t) = 同组A的百分位*100`（仅显示组内相对分位，不是上涨概率）。

滑块影响ETF表格、排序、可视化柱图、价格图副面板、个股Alpha。**不影响RRG坐标公式**。开始日和结束日均需真实行情记录；历史不足时显示缺失。若研究日ETF不存在当日行情，仍展示最后有效日期及其过期状态，但**不列入该日排名**。

## E. 个股Alpha

给定同一个研究日和所选 `n`：

`StockReturn(n,t) = StockClose(t)/StockClose(t-n)-1`

`EtfReturn(n,t) = ETFclose(t)/ETFclose(t-n)-1`

`StockAlpha(n,t) = StockReturn(n,t)-EtfReturn(n,t)`

- 正数：所选时间内股票**相对该ETF**领先；负数相对落后。
- 股票和ETF双方都必须在研究日、观察窗起点有真实收盘价，不可将缺失日的前一价格填上。
- 股票缺失所选研究日行情会标记过期，不纳入有效相对排名。
- 同一股票可能同时出现在不同ETF持仓，结果允许重复列示，但不代表独立的多项Alpha证据。

## F. 截止日期与历史有效性

- Streamlit只读取 `data/` 已同步的日线，不连接iFinD，不会在盘中向API取未收盘行情。
- 生成新网页快照时应使用取数管理程序中纽约交易所**已完成收盘日**的日历截断。
- 当前仓库中的历史ETF和个股数据可能并不同步，页面会给出警告。
- `holdings_asof` 日期允许带网页注记。先提取 `YYYY-MM-DD`，无效日期转为缺值，**不能直接 `pd.Timestamp(字符串最大值)`**。
- 只有ETF前五持仓和单次指数名单，不能用于真正按历史时点的投资组合绩效或事件胜率。
- CPS2是原数据复权字段标签，尚未独立核验现金分红处理；真实委托价须用未复权数据。

### 来源

StockCharts RRG概念（不复制其专有指标）：https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts

纳斯达克Dorsey Wright相对强度方法，仅用于研究启发：https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/12953391234445-What-Relative-Strength-Is-and-Isn-t
