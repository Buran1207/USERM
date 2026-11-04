# USERM · US Equity Rotation & Reversal Monitor

**美股ETF轮动与早期反转研究系统（无机器学习）。** 以你现有HKERM为界面基础，围绕20只ETF及其领先成分股，寻找当前强势、相对强度转向、趋势突破与个股Alpha。无自动下单、不做大盘择时闸门。

> **本包开箱包含已生成的数据快照：20只ETF行情截至2026-11-03，518只独立股票代码样本的行情截至2026-10-09。** 不能声称个股信号已更新至11月。2026-11-02的ETF前五持仓是**单次持仓快照**，不是历史实时持仓。复权口径为源文件自称 `CPS:2`，分红总回报处理未完成独立核验。

## 一、立即上传GitHub运行

1. 解压 `USERM_Streamlit_GitHub.zip` 到 `C:\code\USERM`。**将解压后文件夹内部的全部文件上传到GitHub仓库根目录**（不是把外层文件夹再包一层）。必须包括隐藏 `.streamlit/config.toml`、`userm/`、`data/` 和 `app.py`。
2. 推荐建立**私有GitHub仓库**；先确认iFinD数据协议允许对相应团队/部署环境提供衍生数据。此包含由已上传的iFinD数据精简出来的历史复权行情，**不应直接放在公共GitHub仓库或公开共享网页**。
3. 在Streamlit部署平台连接仓库，主入口设置为 `app.py`，Python建议3.12。`requirements.txt` 包含全部运行依赖。Streamlit Community Cloud的网页访问控制及私有repo政策需自行核验；**private repo不代表网页一定只能内部访问**。
4. **云端必须设置访问密码**：在Streamlit部署配置的Secrets中填入 `USERM_VIEWER_PASSWORD = "替换为足够长的随机密码"`（不可提交入GitHub）。程序在识别到非本机网页URL且未设置此密码时**拒绝加载行情**。这是基础访问保护，不替代企业级身份管理与合同合规许可。
5. 配置团队访问控制、合规许可之后再分享网页。Streamlit端无iFinD API登录、无机器学习训练、无自动交易。

### 本地Windows启动

```bat
cd /d C:\code\USERM
py -3.12 -m pip install -r requirements.txt
py -3.12 -m streamlit run app.py
```

或者双击 `START_USERM.bat`。

## 二、六个页面

| 页面 | 用途 |
| --- | --- |
| ETF市场总览 | 20ETF两组排名、最新状态切换、5/20日相对超额、价格趋势 |
| ETF轮动地图 | 相对趋势与动量自有四象限公式、可选4条历史轨迹 |
| ETF反转机会 | L1早期异动、L2反转候选、L3突破、L4趋势延续、W风险警示 |
| 个股Alpha | 最新可用日期的ETF前五持仓个股 vs 对应ETF，显示历史数据滞后 |
| 历史事件验证 | 2020–2025 TRAIN / 2026 OOS文件分区，5/10/20交易日后的相对表现 |
| 方法与数据质量 | 规则公式、数据覆盖、CPS2/PIT缺口、过期警示 |

**请先读 `METHODS_SIGNALS.md`，所有信号公式、阈值和解释均在其中。**

## 三、本地行情更新（不重新取数）

脚本仅读取已在你电脑保存的 `CPS:2` 按年日行情CSV.GZ；不会连接iFinD、不修改原始数据、不上传秘钥。

默认假定以下目录在 `C:\code\DATA\US\data` 内部某一层存在：

```text
cps2_adjusted/
  train/2020/AAPL.O.csv.gz
  train/2021/AAPL.O.csv.gz
  ...
  train/2025/AAPL.O.csv.gz
  oos/2026/AAPL.O.csv.gz
```

实际文件可能为更深的子文件夹，刷新脚本自动索引`train/YYYY`与`oos/YYYY`模式。

```bat
cd /d C:\code\USERM
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data"
py -3.12 -m unittest discover -s tests -v
py -3.12 -m streamlit run app.py
```

或者双击 `REFRESH_FROM_LOCAL_DATA.bat`。如果手上只有ZIP归档，可用：

```bat
py -3.12 scripts\refresh_data.py --cps2-zip "C:\path\cps2_adjusted.zip"
```

注意：脚本是**全量重建压缩后网页快照**，会替换USERM自己的`data/etf_prices.csv.gz`、`data/stock_prices_part1.csv.gz` + `data/stock_prices_part2.csv.gz`、`data/snapshot_manifest.json`，**不会改动**`C:\code\DATA\US\data`。刷新后需要你自行git add/commit/push，GitHub部署页面才会同步新数据；本网页不会自动读取你本地C盘。若股票文件仍停留10月9日，显示的股票可交易信号不会自动变新。

### 本地刷新脚本输出

- `data/etf_prices.csv.gz`：20只ETF调整后日线（约1.1MiB）
- `data/stock_prices_part1.csv.gz` + `data/stock_prices_part2.csv.gz`：518只独立股票代码日线（各约13MiB（便于GitHub网页上传））
- `data/holdings_snapshot.csv`：2026-11-02 ETF前五持仓代码映射，未解析的外国股票留空
- `data/etf_codes.csv`：20ETF → iFinD交易所代码
- `data/stock_master.csv`：纳指100及标普500去重名单与可用ETF前五股票
- `data/snapshot_manifest.json`：各证券实际最后日期、TRAIN/OOS行数、质量声明

**不需要将388MB的原始ZIP及392MB的metadata ZIP上传到GitHub。**

## 四、数据分区、指标与安全边界

- 2020–2025输入列标记TRAIN，2026及以后标记OOS。即使分区叫OOS，也不能因已看过2026的数据而误称“严格未经使用的样本外”。
- 当前提供的股票库比ETF慢十余个交易日；个股Alpha页会阻止将其当作最新候选。
- ETF持仓只有前五大，含国外股票、基金及股票代码歧义，不能算全行业广度或历史ETF成分。
- 没有未复权OHLC，不提供真实入场价/止损价；调整后价格仅用于研究收益与趋势。CPS:2未独立证实含全部分红再投收益。
- 不计交易成本和滑点；所有历史事件从**信号日的下一个交易日收盘**开始。不可把图上低点或当日涨幅当作可得到的成交。
- 这是 **EOD research monitor**，非实盘订单/组合风险系统，不能自动下单。
- 看板不需要密钥。不上传 `iFinDLogin`、API key、SQLite状态库、原始`metadata_bd`。

## 五、文件结构

```text
app.py                  Streamlit web入口
userm/config.py         固定参数
userm/data.py           快照读取/质量检查
userm/signals.py        ETF轮动/反转状态引擎
userm/stocks.py         ETF关联持仓的个股Alpha
userm/validation.py     事件研究，T+1执行假设
userm/ui.py             HKERM风格的展示层
scripts/refresh_data.py 仅从已有CPS2归档/目录刷新
DATA_QUALITY.md         样本缺口与准确性说明
METHODS_SIGNALS.md      完整计算口径
```

## 六、项目方法来源（借鉴，不复制专有算法）

- Nasdaq Dorsey Wright识别相对领导方向：https://nasdaqdorseywright.zendesk.com/hc/en-us/articles/12953391234445-What-Relative-Strength-Is-and-Isn-t
- StockCharts RRG四象限和轨迹：https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts
- Nasdaq Dorsey Wright Thematic Rotation指数方法：https://indexes.nasdaq.com/docs/NDWTR_Methodology.pdf
- MSCI Momentum长期动量研究：https://www.msci.com/indexes/documents/methodology/2_MSCI_Momentum_Indexes_Methodology_20250417.pdf

`USERM`中公式、分数和阈值均由本项目独立定义，与任何机构的商业指标无等价/授权关系。
