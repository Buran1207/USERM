# USERM V1.3｜ETF-only行情与质量说明

- 本次ZIP内置历史快照：**20只ETF、31,802条日线、2020-01-02—2026-11-03**（源于此前上传的CPS2包，非2026-11-10最新市场行情）。
- 有效ETF代码见 `data/etf_codes.csv`，11只行业ETF与9只科技主题ETF各自建立同组同行基准。
- `data/` 仅包含 `etfs.csv`、`etf_codes.csv`、`etf_prices.csv.gz`、`snapshot_manifest.json`。
- **已移除全部股票行情、股票字典、ETF前五持仓、指数成分股快照及个股Alpha依赖**。

## 必须留意

1. **复权定义**：本地文件标记为CPS2，分红再投资总回报处理未独立核实，价格不可直接用于下单。
2. **行情截至日**：网页标明其实际最后交易日，不会联网取新行情；请本地先完成iFinD采集后执行ETF-only快照刷新。
3. **盘中保护**：刷新脚本采用NYSE日历（含夏令时、提前收盘）和收盘后90分钟缓冲，不纳入尚未确认收盘的当日行情；最近交易日须包含20只ETF才发布。
4. **历史完整性**：观察周期使用真实交易日；行情缺失不前向填充；历史不足时空值，不假造历史四象限。
5. **相对强弱非绝对收益**：ETF跑赢同行不意味着价格上涨，更不代表已验证的未来收益。
6. **旧GitHub文件**：如果你直接覆盖旧仓库，旧个股行情可能仍在远程仓库，需按README的清单从GitHub main明确删除。

更新时只需上传 `data/etf_prices.csv.gz`、`data/etf_codes.csv`、`data/snapshot_manifest.json`；`etfs.csv` 仅在20只ETF的配置变化时更新。原始 `C:\code\DATA\US\data\cps2_adjusted` 不要上传GitHub。
