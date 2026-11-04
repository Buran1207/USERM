# USERM V1.0 信号技术规格｜2026-11-04

## 0. 边界与研究目的

- **无机器学习、无调参器、无自动下单**。完全使用公开可说明的时间序列公式，默认参数固定在 `userm/config.py`。
- **投资交易池**：20 ETF（11行业 + 9科技主题），同一ETF可出现L1到L4研究状态。**个股增强**：本次工作簿的20 ETF“前五大持仓”中可匹配美国上市股票，比较相对ETF的强弱。ETF选定与股票交易判断均由基金经理完成。
- **不以大盘看多为先决条件**。ETF按组内其他ETF（leave-one-out）计算相对收益；保留绝对价格条件，防止“跌得少就买”的错误。
- **研究日终**：所有状态在交易日 t 收盘后才可知道。图上标记 t 不是 t 日盘中可以买到的信号。

## 1. 观测输入与分组

- 20 ETF 由 `data/etfs.csv` 明确列示。11行业：XLC/XLY/XLP/XLE/XLF/XLV/XLI/XLB/VGT/XLU/VNQ；9科技主题：SMH/IGV/CIBR/BAI/SKYY/DTCR/BOTZ/QTUM/GRID。
- 原始输入为 `cps2_adjusted` 归档按年日线：`date, open, high, low, close, volume, partition`。`adjustment=CPS:2`，其供应商“前复权/后复权/含现金分红”精确定义尚未审计，**不宣称是真正Total Return**。
- 组别相互独立排名，**绝不把VGT、VNQ宣称为官方标普500行业ETF**；20ETF中的重合成分股不可被认为20个独立风险因子。
- 两份当前指数名单仅用于补充股票代码，ETF持仓为2026-11-02单次快照。均不用于过去历史真正的成分股回测。
- 缺失价格、缺失基准、无足够历史：返回NA；**不得用下一交易日的价格回填到上一日**。当期过期（比研究日滞后超过2个有效ETF交易日）则不发出最新有效状态。

## 2. 同组剔除自身的等权日收益基准（Peer benchmark）

对某ETF i、某个交易日 t，取其余同组ETF的日收益（复权收盘计算），等权平均：

`peer_return(i,t) = mean_{j in same group, j != i} [close(j,t)/close(j,t-1)-1]`

当天有效同组其他ETF至少3只；不足时标为缺失。将其从100起步的日收益链式复利形成 `peer_index(i,t)`：

`peer_index(i,t) = peer_index(i,t-1)*(1+peer_return(i,t))`

当日peer_return缺失则基准序列在该日不参与信号计算，底层累乘会保持上一有效状态，但不视为真实可交易价格。同行ETF各自拥有**不同**的剔除自身基准。这比将本身加入同组基准更客观；它不是SPY/QQQ，不是市场市值加权，也不是复制任何专有指数。

## 3. 多周期收益与相对超额

- `return_k(i,t)=close(i,t)/close(i,t-k)-1`
- `peer_return_k(i,t)=peer_index(i,t)/peer_index(i,t-k)-1`
- `rel_k(i,t)=return_k(i,t)-peer_return_k(i,t)`

日频观察k=1、3、5、10、20、60；主要触发使用5/10/20/60，3日仅参考快速变化。

**例子：** 某ETF过去5日涨1%，其同行等权基准涨3%，那么5日超额为-2个百分点；若该ETF跌2%，同行跌5%，其相对超额为+3个百分点，但**绝对收益仍为负，不能因此确认上涨趋势**。

## 4. 四象限轮动地图（透明自有公式）

定义 `RS(i,t)=close(i,t)/peer_index(i,t)`；用对数避免单位和非固定初始价格尺度影响：

`X(i,t) = 100*exp( EMA14(ln RS(i,t)) - EMA36(ln RS(i,t)) )`

`Y(i,t) = 100*X(i,t)/X(i,t-5)`

- X≥100、Y≥100：领先强化（LEADING）
- X≥100、Y<100：领先减弱（WEAKENING）
- X<100、Y≥100：落后改善（IMPROVING）
- X<100、Y<100：落后持续（LAGGING）

这借鉴了 RRG 关注相对趋势与动量的思想，**明确不是**JdK RS-Ratio/RS-Momentum 的专有公式，也不是 Dorsey Wright Point & Figure 专有相对强度矩阵。前36日不足以形成X，再延后5日才能形成Y。

## 5. 轮动分数与排名（不等于上涨概率）

对每个交易日、组内ETF独立计算：

- `q5=percentile_rank(rel_5)`
- `q20=percentile_rank(rel_20)`
- `q60=percentile_rank(rel_60)`

`score = 100 * (0.25*q5 + 0.35*q20 + 0.40*q60)`，高者优先。分数代表**过去表现的相对组内百分位**，不代表未来收益预测。对照历史事件应查看超额收益的实际条件分布。历史较短的ETF若无60日数据，则分数为NA。

## 6. 量价趋势辅助指标

- `MA10 / MA20 / MA50`: 调整后收盘价在过去10/20/50日简单均值（含t）。
- `prior_high20`: t-1日及以前20根调整后最高价的最大值，**严格不含当日高价**。
- `breakout20`: 当日调整后收盘价 > 前20日最高价。
- `RVOL20`: 当日原始成交量 / 前20根交易日原始成交量均值，**前20日均值不含今天**。
- `trade_proxy_usd = CPS2 adjusted close * raw volume`：仅供流动性参考，**不是实际美元成交金额**；未复权价格缺失时不生成交易限价。

## 7. 固定信号状态规则（完全确定性）

状态按以下优先级判定：L3 → L4 → W → L2 → L1 → N0；不足历史或缺少必需指标是NA。

| 状态 | 逻辑（AND，除非特别注明） | 实际意义 |
| --- | --- | --- |
| **L1 早期异动** | X<100；Y≥100.05；rel_5>0 | 相对落后格局内动量开始改善，**只是观察** |
| **L2 反转候选** | Y≥100.05；rel_5>0；rel_10>0；return_5>0；close>MA10；X<100.25 | 已获得短周期价格与相对改善共同支持，尚非中期趋势确认 |
| **L3 突破确认** | X>100；Y≥100；rel_10>0；close>MA20>MA50；close>prior_high20；RVOL20≥1.15 | 相对领先且价格突破、成交量高于前期水平。**需要次日执行层判断** |
| **L4 强势延续** | X>100；rel_20>0；rel_60>0；close>MA20>MA50 | 趋势/轮动领先继续。非新买点保证 |
| **W 风险警示** | 前5个交易日内曾处于L3或L4；当前close<MA20；rel_5<0；Y<100 | 近期强势信号失效，应复核持仓，不等于做空 |
| **N0** | 其余有足够指标的状态 | 无新触发，不必强迫买入 |
| **NA** | 50日均线或必需相对指标缺失 | 不得用虚构数据补足 |

**同日满足L3和L4优先显示L3。** 任一状态第一次出现/相比前一交易日发生变化标记为“新信号”，持续天数另行统计。W适用近期强势信号转弱；超过5天后不自动持续W。状态不包含卖出规则与仓位分配。

固定参数反转阈值的经济解释：`100`为相对趋势和动量中性，`100.05`要求动量略高于中性以减噪；`RVOL≥1.15`为交易参与的简单量价过滤。**这些是未经调优的起始假设，不能将它们包装为机构公认最优值或统计显著阈值。**

## 8. 个股Alpha（仅当前已知ETF前五大持仓）

个股与对应ETF同期调整后收盘价比较：

`stock_alpha_k=stock_return_k - etf_return_k, k=5,20,60`

`alpha_strength_pp = 100*(0.35*alpha_5+0.45*alpha_20+0.20*alpha_60)`

三类股票候选（依次优先）：

- **强势突破**：close>前20日最高价，alpha20>0，close>MA20，RVOL20≥1.20。
- **持续领先**：alpha5>0，alpha20>0，close>MA20>MA50。
- **反转观察**：alpha5>0，alpha20≤0，close>MA10，RVOL20≥1.15。

但仅在当天ETF与股票**都有真实日线**时显示有效状态；股票滞后任何交易日不得当成当天已知买入机会。某只股票可在多个ETF里重复出现，这反映归属重叠，**不代表多个独立Alpha信号**。单一持仓快照**严禁用于历史ETF成分股选择回测**。

## 9. 事件研究（不是策略实盘回测）

对每次L1/L2/L3/L4首次切换事件，观察未来5、10、20交易日；事件在T日**收盘后**可见。

- 假设T+1日**收盘价**才入场，T+1+h日**收盘价**退出（持有h个完整交易日间隔）。
- `forward_h = close(T+1+h)/close(T+1)-1`
- `peer_forward_h = peer_index(T+1+h)/peer_index(T+1)-1`
- `excess_h = forward_h - peer_forward_h`
- `MAE_h = min_{k=1..h} [close(T+1+k)/close(T+1)-1]`

展示正收益占比、超额收益胜率、中位数绝对/超额收益、中位数最大不利波动和事件数量。多信号同资产的持有窗可能重叠，不做假设其收益相互独立。即使2026文件名为OOS，也**不能在调整了2026样本上的规则后将其称为严格前瞻性样本外成绩**。若要真实检验交易策略，另需交易成本、入场滑点、退出规则、仓位约束和时间点成分/复权验证。

## 10. 参考方法与法律边界

- Nasdaq Dorsey Wright relative strength = 识别领涨而非预测大盘：https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/12953391234445-What-Relative-Strength-Is-and-Isn-t
- Nasdaq Dorsey Wright Thematic Rotation Index方法文件（专有相对强度矩阵，不复制）：https://indexes.nasdaq.com/docs/NDWTR_Methodology.pdf
- StockCharts RRG（四象限、轨迹的研究思想，不复刻指标公式）：https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts
- MSCI Momentum Indexes 2025方法（长期动量及波动控制的研究参考；V1没有复制）：https://www.msci.com/indexes/documents/methodology/2_MSCI_Momentum_Indexes_Methodology_20250417.pdf

USERM信号设计的权重、阈值为**本项目自行定义**，无机构背书。项目界面借鉴你提供的HKERM Streamlit GitHub代码包的侧栏布局、数据快照、轮动图、股票查询和CSV导出模式。未经授权不要公开再分发原始或衍生供应商数据。
