# USERM V1.5 | SPY基准 · 公开RRG近似算法

## 1. 与官方StockCharts的区别

本模型的固定相对基准为 **SPY ETF**；之前截图的`$SPX`是**S&P500价格指数**，不是SPY。这改变了原始相对强度，故坐标不保证一致。StockCharts官方JdK RS-Ratio / RS-Momentum完整参数未公开，本项目不冒充专有实现。

若以StockCharts为参考，需将官网Benchmark Symbol设为`SPY`，Period为Daily，Tail Length为4，截止日期、复权口径也一致；即便如此，仍有专有公式差异。

## 2. 价格与相对强度

从同一个本地CPS2调整后日线价格库读取20只ETF和SPY。20只ETF的交易池与组合排名保留，不含SPY。

```text
RS_i(t) = AdjustedClose_i(t) / AdjustedClose_SPY(t)
X_i(t)  = 100 * SMA_10(RS_i)(t) / SMA_30(RS_i)(t)
Y_i(t)  = 100 * X_i(t) / SMA_9(X_i)(t)
```

历史不足时显示缺值；不把缺失的SPY价格向前填充；全部ETF使用同一SPY基准。象限阈值均为100。

可选旧版对数EMA实现：

```text
X_i(t) = 100 * exp( EMA_14(log RS_i)(t) - EMA_36(log RS_i)(t) )
Y_i(t) = 100 * X_i(t) / X_i(t-5)
```

以上都是公开近似算法，并非JdK原始公式。

## 3. Range、Tail Length、观察周期

- `Daily`：每个点对应一个已完成美股交易日。
- `Tail Length=4`：显示当期终点及此前4个交易日位置，不参与计算公式。
- `3 months`：只作用于基准走势图显示窗口，不截断计算期。
- 左侧观察周期1–60日：只影响20只ETF的组内超额收益、排名和ETF价格页，不影响RRG平滑周期。

## 4. ETF组内Alpha保持不变

行业ETF与科技主题ETF分开排名。组内其他成员每日收益等权形成每只ETF的独立同组基准，以所选1–60个交易日的差额衡量相对收益。SPY只服务RRG，不参与组内排名。

## 5. 数据与同步

`REFRESH_ETF_AND_SPY.bat` 读取 `C:\code\DATA\US\data\cps2_adjusted`，要求最后一个已完成纽交所交易日（收盘后90分钟）内，20 ETF+SPY最新日期一致，才发布：

- `data/etf_prices.csv.gz`：20只ETF历史行情
- `data/spy_prices.csv.gz`：独立SPY日期及收盘价
- `data/etf_codes.csv`：20只ETF代码映射
- `data/snapshot_manifest.json`：日历截止、覆盖与基准元数据

禁止用ETF20等权基准伪装SPY；禁止发布盘中未收盘数据；禁止在历史观察中使用未来行情。历史复权口径与StockCharts须另行核对。
