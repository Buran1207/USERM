# USERM V1.5 · Public EOD 数据更新补丁

本补丁仅基于原 V1.5 数据层与 UI 数据状态进行改造。核心 `userm/rrg.py`、`userm/signals.py`、`userm/data.py`、`userm/benchmarks.py` 未修改。保留原 ETF 代码、SPY、TRAIN/OOS 界线和原 ETF master。旧数据是 2026-11-17 的 CPS2 快照，首次成功迁移前保持旧数据并显示来源；没有生成或假称已经下载 Yahoo 真行情。

## 1. 数据来源与权限（必读）
Yahoo Finance/yfinance 是技术可行性验证路径，不是已获商用及再分发许可的正式行情源。当前 GitHub 为公开仓库；自动化抓取、保存、向公开仓库及 Streamlit 展示市场数据所需权利必须先取得。不要将变量 `USERM_DATA_AUTHORIZED=yes` 当作许可证。若无法取得授权，改用允许这些用途的授权行情供应商（需适配数据获取层）；本补丁没有实现第二供应商，也未验证任何供应商的合同授权。即使私有仓库也不能自动消除商用许可问题。
- Yahoo 条款：https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html
- yfinance：https://github.com/ranaroussi/yfinance

## 2. 一次性部署（建议使用补丁，不覆盖整个 GitHub）
当前 GitHub 连接仅可读，未修改线上仓库。使用有写权限的 GitHub 账户在本机 Git Bash 或 PowerShell 执行：

```powershell
cd C:\code
# 若已有 USERM git 工作树，则直接 cd 至该目录并 git pull --ff-only；不要覆盖个人修改。
git clone https://github.com/Buran1207/USERM.git USERM_public_deploy
cd USERM_public_deploy
git status --short
# 解压补丁 ZIP 到任意目录，下面改为其真实绝对路径。
git apply --check "C:\你的解压目录\USERM_public_eod.patch"
git apply "C:\你的解压目录\USERM_public_eod.patch"
git status --short
git add app.py scripts/refresh_data.py scripts/verify_data.py scripts/refresh_public.py tests/test_public_refresh.py requirements-update.txt .github/workflows/update-public-eod.yml PUBLIC_DATA_SETUP.md
git commit -m "USERM: public EOD adapter and cloud scheduler"
git push origin main
```
若 `git apply --check` 不通过（仓库有新版/本地修改），不要强行覆盖；先审阅变更合并。`git push` 必须用有仓库写权限和 workflow 修改权限的账号。保留 repo 当前额外模块、文档、data 文件等；不上传原 ZIP 里的 data.zip 或 __pycache__。

取得适用的数据使用及公开再分发许可之后，进入仓库 Settings > Secrets and variables > Actions > Variables，新建 `USERM_DATA_AUTHORIZED` 值 `yes`。确认 Actions 已启用，仓库策略允许 `GITHUB_TOKEN` contents:write，main 允许 GitHub Actions 提交。首次可在 Actions > USERM public EOD refresh > Run workflow 手动验证一次。每日任务从此不需开电脑；未许可则不启用该变量。若使用机构授权替代供应商，请先改适配器及授权控制，不要用 Yahoo 变量绕过条款。

## 3. 调度
NYSE 正常收盘：北京时间夏季 04:00、冬季 05:00。实际交易日历决定安全截止，收盘+20分钟才读取；提前收盘和节假日按 XNYS。UTC 周一至周五 20:23、20:43、21:23、21:43（北京时间次日 04:23/04:43/05:23/05:43），另有 22:23、23:23 UTC 补救（北京时间 06:23/07:23）。每个 job 最多 13 分钟。若已有当日完整 Yahoo 哈希快照，快速跳过。目标 06:00 前完成，不是服务等级保证；GitHub 排队、数据源延迟或封锁、校验失败都可能延后，后续补救失败会保留旧数据，日志标明失败。GitHub public repo 60 天无活动可能停用 schedule；正常日提交会产生仓库活动，但仍需关注异常。

## 4. 前复权与数据质量
每次完整下载 2020-01-01 起 21 个独立 ticker（实际上市日期开始），不用 EPS/财务字段，不拼接 CPS2。利用 Yahoo 原始返回的 Close 与 Adj Close：f_t=AdjClose_t/Close_t，OHLC_new_t=OHLC_t*f_t/f_T。最后一个安全交易日价格与 Yahoo Close 一致；Yahoo Close 已作拆股处理，股息通过调整比例纳入。成交量按供应商返回，不二次复权。不同供应商口径并非逐条相等，不把新历史回测视作原回测的完全复现。保留旧历史日期覆盖，不补齐 ETF 成立前价格，不用 forward fill，不填造零值，不接受缺少当日 bar。历史日期校验以 NYSE 为基础，如供应商历史确有中断需要人工审查，不能凭空补齐。记录新旧重叠区间收益差异（bp）、SHA256、数据来源、覆盖数和最新交易日。

任何一个标的失败（包括 SPY），全部保留上次快照；校验后四个文件生成一组提交。旧本地 CPS2 更新器在 Yahoo 已发布后拒绝覆盖，防止混用。原有静态 AUM/持仓日期未改；不属于行情自动更新范围。Streamlit 从仓库读取 EOD 快照，不在页面发出行情 API 请求；日期/文件修改时间驱动缓存刷新，在页面中显示落后最新已完成交易日的警告。保持原 Streamlit 部署指向 Buran1207/USERM/main/app.py，不需要换网址。已经打开的页面可能需自动 rerun 或重新载入。

## 5. 检查及状态
- 原 ZIP 和新测试共 26 个 pytest 通过（历史行情和模拟 Yahoo 返回，不是网络实测）。
- 原 RRG、signals、data、benchmarks 文件字节未改；原数据校验 PASS（32002 ETF 行，1729 SPY 行，截至 2026-11-17）。
- 当前运行环境无法访问 Yahoo/GitHub git 网络；GitHub 连接仅有 pull，无 push 权限；未验证实际 Yahoo 21 标的实时取数或 Streamlit 实际部署。不承诺 06:00 之前绝对完成。
- 上线后检查 Actions 日志 `[SUCCESS]`、`data/snapshot_manifest.json` 中 `source`、`published_last_complete_21_session` 和 `sha256`、Streamlit 侧边栏最新日期。首次运行前取得许可。若出现 Yahoo 数据缺失或源口径差异较大，应核查后再用于真实投资。

本地仅在已有使用权限的情况下可测试：
```powershell
python -m pip install -r requirements-update.txt
python scripts/refresh_public.py
python scripts/verify_data.py
```
不需要 Windows 任务计划，不依赖 iFinD 日常取数。若希望旧本地 C:\code\DATA\US 路径也同步，本补丁不含本机同步；云端更新不需要本地文件。
