# USERM V1.2 — 美股20 ETF轮动与个股Alpha

保留HKERM风格的Streamlit展示，**不使用机器学习、L1/L2/L3/L4反转交易信号、历史事件验证、自动交易**。V1.2从历史CPS:2日线计算20只ETF的同组相对表现、四象限和前五大持仓的股票相对收益。

## 本版修改（相较于USERM V1.0）

1. **修复 `pandas._libs.tslibs.parsing.DateParseError`**：原 `holdings_asof` 中可能有 `2026-11-03（网页更新）` 等注释，先正则提取 `YYYY-MM-DD` 并用 `errors='coerce'` 解析，日期不合法不再使个股页面报错。
2. **左侧新增观察周期滑块**：1–60交易日，默认20日，步长1。实际改变ETF所选周期收益、同组超额收益、ETF组内排名、相对收益柱图、个股Alpha与历史价格图的相对收益面板。
3. **删除低有效性模块**：删除ETF反转机会、历史事件验证页面，及L1–L4/W状态计算、表格标签、分布图和价格图触发标记。四象限只表达相对强弱，不当成已验证交易信号。
4. 保留四个页面：**ETF市场总览、ETF轮动地图、个股Alpha、方法与数据质量**。
5. 保持固定RRG定义：横轴基于对数相对强度的EMA14与EMA36差，纵轴为横轴5日比例变化。滑块不会修改RRG公式。
6. 保持现有离线 `data/` 数据文件结构，**与此前 `US_DATA_MANAGER_USERM_SYNC_FIXED_20261105` 数据同步工具兼容**。

## GitHub / Streamlit部署

将ZIP中的**全部文件和文件夹**上传到GitHub仓库根目录，入口 `app.py`。推荐 Python 3.12。不要把ZIP外层目录作为仓库中的新一级文件夹。

替换旧仓库时，请**删除**旧版文件 `userm/validation.py` 和 `METHODS_SIGNALS.md`（此包不再包含），否则虽不被调用，仓库仍会留有过期文档。

本地运行：

```bat
cd /d C:\code\USERM\USERM_Streamlit_GitHub_V1_20261104
py -3.12 -m pip install -r requirements.txt
py -3.12 -m unittest discover -s tests -v
py -3.12 -m streamlit run app.py
```

亦可双击 `START_USERM.bat`。本版本**不要求配置 `USERM_VIEWER_PASSWORD`**。这不表示数据可以公开分发：仓库中包含供应商来源的行情快照，强烈建议使用私有仓库和Streamlit平台级访问权限，并确认数据许可；私有GitHub仓库并不自动保证部署网页私有。

## 数据刷新（本项目不连接 iFinD）

优先继续使用你修复后的 `US_DATA_MANAGER_USERM_SYNC_FIXED_20261105`，在本地运行 `05_SYNC_ONLY_NO_API.bat` 或 `02_UPDATE_AND_SYNC_ONE_CLICK.bat`，它们会生成USERM网页需要的行情快照。随后把更新后的 `data/` 文件同步到GitHub `main/data/`。本V1.2读取路径和文件名完全不变。

也可使用本包自带的 `REFRESH_FROM_LOCAL_DATA.bat`，它调用：

```bat
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data"
```

它仅仅读取本地已存在CPS2文件，重建快照，不自动请求API；若源目录含有未收盘日行情，应首先运行你已修复的取数管理包，该管理包带美股收盘日安全截断机制。**本包的原版 `scripts/refresh_data.py` 不是交易所日历取数程序，不能替代盘中EOD安全控制。**

需上传的行情数据：

```text
data/etf_prices.csv.gz
     stock_prices_part1.csv.gz
     stock_prices_part2.csv.gz
     snapshot_manifest.json
```

`etfs.csv`、`etf_codes.csv`、`holdings_snapshot.csv`、`stock_master.csv` 等配置与持仓文件也需要保留。压缩后的股票行情分成2个文件，方便GitHub网页上传，不要重新合并为一个大文件。

## 页面与公式

**同组基准**：每只ETF与其所在组其他ETF的日收益等权组合比较（剔除自身）；11个行业ETF和9个科技主题ETF分别排名。它不是S&P500或Nasdaq100。

**观察周期** `n ∈ [1,60]`：

```text
ETF_n = close(t)/close(t-n) - 1
Peer_n = peer_index(t)/peer_index(t-n) - 1
Excess_n = ETF_n - Peer_n
Rank_n = within-group rank of Excess_n, descending
```

`n` 是**有效ETF市场交易日**间隔。缺失首日或末日行情时不使用上一条价格替代。所有分数仅用于描述当前相对强弱，不代表预测收益率。

**RRG坐标固定**：

```text
RS = adjusted_ETF_close / own_leave-one-out_peer_index
X = 100 * exp( EMA14(log RS) - EMA36(log RS) )
Y = 100 * X(t) / X(t-5)
```

`X≥100/Y≥100`领先强化，`X≥100/Y<100`领先减弱，`X<100/Y≥100`落后改善，`X<100/Y<100`落后持续。这是公开可验证的透明近似，不是StockCharts专有JdK指标。

**个股Alpha**：仅针对 `holdings_snapshot.csv` 中前五持仓可映射美股计算股票与其所属ETF的同周期相对收益，默认按所选 `n` 日超额从高到低排序。历史持仓关系来自较新的**单次快照**，不构成无幸存者偏差的历史回测。

方法和边界请见 `METHODS_ROTATION.md` 与 `DATA_QUALITY.md`。

## 测试

```bat
py -3.12 -m unittest discover -s tests -v
```

涵盖异常持仓日期、不同时段滑块、历史不使用未来价格、历史不足与缺日、个股Alpha与ETF超额计算的一致性。
