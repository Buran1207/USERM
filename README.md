# USERM V1.3（2026-11-10）｜20只ETF专用相对轮动系统

本版本以 **USERM V1.2** 为基础，**整个 USERM 仅研究20只ETF**，不再读取、保存或展示任何个股行情、前五大持仓、指数成分股、个股Alpha。**无机器学习、反转分级信号、历史交易事件验证、自动交易。**

## 三个页面

1. **ETF市场总览**：11只行业ETF + 9只科技主题ETF分组相对收益排名、量价、柱状图和ETF走势；可导出CSV。
2. **ETF轮动地图**：RRG近似四象限、历史轨迹、相对趋势EMA14/36及其5日变化。
3. **方法与数据质量**：计算定义、最新日期、ETF覆盖及缺数记录。

左侧支持中文/English、**历史研究日期日历**（最早至最新可用行情，非交易日回退）、**1–60交易日观察周期滑块**（默认20）、ETF分组选择。观察周期控制收益和组内排名，但不改变RRG固定的EMA14/36与5日动量。

## 安装与运行

将ZIP内所有文件直接放在GitHub仓库的**根目录**，Streamlit主入口设为 `app.py`。建议 Python 3.12。

本地Windows：

```bat
cd /d C:\code\USERM\USERM_Streamlit_GitHub_V1_20261104
py -3.12 -m pip install -r requirements.txt
py -3.12 -m unittest discover -s tests -v
py -3.12 -m streamlit run app.py
```

或双击 `START_USERM.bat`。本版无 `USERM_VIEWER_PASSWORD` 检查；**不代表行情已获得公开再分发授权**，应按照供应商许可管理仓库及网页访问权限。

## GitHub旧仓库清理——非常重要

**用新ZIP覆盖旧文件，GitHub不会自动删除旧仓库里的文件。** 如果是在V1.2原仓库上升级，务必在 `main` 删除以下旧文件：

```text
userm/stocks.py
data/stock_prices_part1.csv.gz
data/stock_prices_part2.csv.gz
data/stock_master.csv
data/holdings_snapshot.csv
data/holdings_snapshot_raw.csv
data/index_constituents_snapshot.csv
```

以前更老版本若存在 `userm/validation.py` 或 `METHODS_SIGNALS.md` 也删除。必须删除旧个股数据文件，否则它们虽不被新界面读取，仍可能在GitHub仓库中公开可见。

如使用Git命令，在仓库根目录执行（不存在的文件按实际情况跳过）：

```bat
git rm -f userm/stocks.py data/stock_prices_part1.csv.gz data/stock_prices_part2.csv.gz data/stock_master.csv data/holdings_snapshot.csv data/holdings_snapshot_raw.csv data/index_constituents_snapshot.csv
```

然后提交和推送。本包已将旧个股数据文件名列入 `.gitignore`，防止以后误上传；**注意 .gitignore 无法自动删除已经被 Git 跟踪的文件**。

## 数据结构

```text
USERM/
├── app.py
├── requirements.txt
├── REFRESH_FROM_LOCAL_DATA.bat
├── START_USERM.bat
├── data/
│   ├── etfs.csv
│   ├── etf_codes.csv
│   ├── etf_prices.csv.gz
│   └── snapshot_manifest.json
├── scripts/
│   └── refresh_data.py
├── tests/
│   ├── test_rotation.py
│   └── test_etf_refresh.py
└── userm/
    ├── config.py
    ├── data.py
    ├── signals.py
    └── ui.py
```

内置价格快照来自先前上传的旧数据，**截止2026-11-03，不是2026-11-10实时行情**。请用已有的本地最新收盘数据刷新后再手动上传GitHub。

## 今后更新：只刷新ETF、不再同步股票数据

这次重写了本项目自带的 `scripts/refresh_data.py`，它只读取本地已有的20只ETF CPS2数据、生成 `data/etf_prices.csv.gz`、`data/etf_codes.csv`、`data/snapshot_manifest.json`。**不读取或生成个股文件，不调用iFinD API**。

1. 如果 `C:\code\DATA\US\data\cps2_adjusted` 已更新完毕，只需双击新包内的 `REFRESH_FROM_LOCAL_DATA.bat`。
2. 可手动执行：

```bat
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data"
```

3. 刷新完成、终端显示 `SUCCESS: 20/20 ETFs` 后，仅上传以下文件到GitHub `main/data`：

```text
data/etf_prices.csv.gz
data/etf_codes.csv
data/snapshot_manifest.json
```

**盘中保护**：刷新程序使用NYSE官方交易所日历（含美国节假日、提前收盘、夏令时）计算最近已收盘时点，另外加入90分钟缓冲。即使原始CPS2有当天盘中记录也会排除；还要求发布的最后一天20/20 ETF数据齐备，并拒绝用更旧快照覆盖当前快照。依赖 `exchange-calendars` 已列入 requirements.txt。

**与原取数管理器的衔接**：现有 `US_DATA_MANAGER` 仍可负责采集本地CPS2行情，但请不要再使用旧版 `05_SYNC_ONLY_NO_API.bat` 把个股快照同步回这个ETF专用GitHub工程。改为运行上面的 **ETF-only刷新脚本**。如果每天原来是运行“取数+同步”一键程序，旧取数管理器的同步阶段仍可能重新创建个股文件；本项目未修改你Windows上原取数管理器的行为，建议采集与ETF快照刷新分开执行。

## 方法

每只ETF以**同组其他ETF的等权日收益**构造同行基准（剔除本ETF）。11只行业和9只科技主题单独排名，**不进行大盘方向前置过滤**。

```text
ETF_n = adjusted_close(t) / adjusted_close(t-n) - 1
Peer_n = peer_index(t) / peer_index(t-n) - 1
Excess_n = ETF_n - Peer_n
Rank_n = group rank(Excess_n, descending)
RS = adjusted_ETF_close / own_peer_index
X = 100 * exp( EMA14(log RS) - EMA36(log RS) )
Y = 100 * X(t) / X(t-5)
```

X/Y以100分割四象限。RRG使用可解释的**自定义近似公式**，不是StockCharts专有JdK指标。不使用未来行情、缺失日不前向填补；历史数据不足时相应字段显示空值。详见 `METHODS_ROTATION.md`。

## 测试

```bat
py -3.12 -m unittest discover -s tests -v
```

测试范围：20 ETF、1–60日观察周期、历史截断无未来信息、缺日与过期价格、市场已收盘截止日（含提前收盘）、ETF-only快照的完备性检查。Streamlit浏览器端仍需在你的实际Windows/Cloud环境启动验证。
