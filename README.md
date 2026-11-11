# USERM V1.5 — 20只ETF轮动 + SPY统一RRG基准

本版把V1.4的RRG基准从标普500价格指数`$SPX`**彻底改为**可交易ETF `SPY`，并保留原20只ETF组内超额收益和相对排名。**SPY仅是RRG基准，不是第21只研究/交易ETF。**

## 页面与方法（延续V1.4）

- **ETF市场总览**：20只ETF；1–60交易日观察周期滑块；同组（11行业/9科技主题）剔除自身的ETF等权收益作为Alpha对照；排名与RRG基准相互独立。
- **ETF轮动地图**：所有20只ETF统一相对`SPY`；默认透明SMA10/30/9 RRG近似，允许切换至旧EMA14/36+5日公式；日线、尾长默认4，尾长**只控制显示**。
- **方法与数据质量**：查看数据区间、SPY基准行情与公式。研究日期为历史交易日历选择，可查询历史行情，不使用未来价格。

无个股、L1–L4、机器学习、自动交易或公开JdK专有公式的冒充实现。

## 重要说明：本包不可能包含你电脑刚更新的最新行情

打包基于之前提供的USERM V1.4版本：其内置的20只ETF数据截至**2026-11-03**，以前上传的CPS2文件**没有SPY历史数据**。因此本ZIP **不包含`data/spy_prices.csv.gz`**，不会伪造SPY最新价格，也不声称已把你电脑上的2026-11-10收盘价包含在包中。

请务必先在你自己的电脑解压/覆盖代码（切勿把ZIP内的旧`data`覆盖掉你现有更新较新的文件），然后运行本地刷新脚本，生成与现有最新数据一致的真实SPY和20只ETF行情。

## Windows本地一键更新（不调用iFinD）

安装依赖（首次执行）：

```bat
cd /d C:\code\USERM\USERM_Streamlit_GitHub_V1_20261104
py -3.12 -m pip install -r requirements.txt
```

在你部署USERM的实际项目根目录中双击：

**`REFRESH_ETF_AND_SPY.bat`**

它从本地已更新的：

`C:\code\DATA\US\data\cps2_adjusted`

读取 **20 ETF + SPY，共21只标的**，检查真实纽交所收盘日（包括提前收盘和夏令时）及收盘后90分钟缓冲，不读取当日尚未完成的K线。SPY源代码若存在多个交易所后缀，请用下面命令明确指定，例如：

```bat
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data\cps2_adjusted" --spy-symbol SPY.P
```

刷新只有在20只ETF和SPY均具有**同一最新完整交易日**时才发布；若SPY数据缺失/过旧则报错，避免悄悄用其他ETF替代。仅复制压缩行情快照，不会调用iFinD，也不改写原始CPS2文件。

成功后会自动执行 `scripts\verify_data.py`，可以另行双击 `VERIFY_ETF_SPY_DATA.bat` 验证。

新版本将生成/更新以下**四个**文件：

```text
data/etf_prices.csv.gz
data/spy_prices.csv.gz
data/etf_codes.csv
data/snapshot_manifest.json
```

`data/etfs.csv` 仍是固定的20只ETF定义，不会把SPY加入其中。

## Streamlit本地与GitHub部署

运行：

```bat
py -3.12 -m streamlit run app.py
```

GitHub 上传解压后的项目内容到仓库 `main` 根目录，主入口 `app.py`。**更新代码之后，务必将上述四个最新行情文件上传到`main/data`；仅上传代码会导致SPY相关RRG图缺数据。** Cloud无法访问你Windows电脑的C盘。

从旧V1.4升级时，删除GitHub仓库中不再使用的旧文件：

```text
data/spx_prices.csv.gz
scripts/import_spx.py
scripts/compare_stockcharts_reference.py
IMPORT_SPX_FROM_LOCAL_DATA.bat
REFRESH_ETF_AND_SPX.bat
data/stockcharts_reference_20261109_approx.csv
```

旧个股数据及持仓快照也不应保留（V1.3起已取消个股）。

## SPY与StockCharts的关系

- 之前的StockCharts截图使用 `$SPX`（标普500**价格指数**），而USERM V1.5使用 `SPY`（可交易、分红ETF）。两者不是同一个价格序列，其RRG坐标可能不同。
- 如需横向对照，请先把StockCharts图表的Benchmark Symbol从`$SPX`改为`SPY`，并使用相同的日线和截至日期；但独立公开近似公式**也不保证等于专有JdK坐标**。
- 图表横轴为 `100*SMA10(ETF/SPY)/SMA30(ETF/SPY)`，纵轴为`100*X/SMA9(X)`；旧14/36版本仍可切换。尾长=4表示最近点+此前4个日节点，不决定公式周期。
- SPY与ETF同取iFinD标注CPS:2调整行情，其与StockCharts分红复权策略是否一致仍需进一步核验。

## 测试与安全

运行 `py -3.12 -m pytest -q`。测试包括盘中时点、感恩节提前收盘、SPY缺失、不一致日拒绝发布、基准变更和行情无未来数据等。此环境不含你电脑最新CPS2及SPY真实数据，需在你的本地刷新后执行数据验证。

行情可能受iFinD授权条款约束，请确认GitHub仓库和Streamlit访问权限，勿将受限行情公开再分发。应用没有额外的内置访问密码。
