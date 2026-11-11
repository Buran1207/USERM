# USERM V1.5 — 数据质量说明

- **20只ETF交易池**：随包原有快照截至2026-11-03，仅用于安装后查看旧数据。
- **SPY RRG基准**：此前上传的CPS2历史ZIP没有SPY，所以本次代码ZIP不包含真实`spy_prices.csv.gz`。不能推断你的本地最新价格。
- **最新行情的正确来源**：你电脑现有`C:\code\DATA\US\data\cps2_adjusted`。运行`REFRESH_ETF_AND_SPY.bat`从本地更新20 ETF+SPY，并验证21只标的最新日期一致。
- **EOD保护**：使用NYSE交易日历（节假日/提前收盘/夏令时），只处理收盘后90分钟的已完成交易日。不使用盘中当天未完成行情。
- **发布行为**：任何标的缺失、SPY与ETF日期不齐、历史不足或旧快照较新，均拒绝覆盖；不会静默切换RRG基准。
- **GitHub数据**：必须同步`etf_prices.csv.gz`、`spy_prices.csv.gz`、`etf_codes.csv`、`snapshot_manifest.json`四个文件。
- **复权与展示**：CPS:2数据的分红总回报含义与StockCharts的对齐程度尚需实证核对。SPY与`$SPX`不是同一个基准，RRG读数不能直接逐点比较。
