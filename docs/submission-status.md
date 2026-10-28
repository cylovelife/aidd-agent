# 首次官方提交状态

## 已评分：首次有效提交完成

2026-10-28 **19:34:14，北京时间**，从官方实时回归榜下载 CSV，精确匹配本次显示名及方法报告链接：

- **MA-ST-RAE：0.9284982814029326**（越低越好）。
- **实时名次：223 / 281 条目**。
- 这是实时公开榜成绩，**不是最终名次或获奖证明**。
- 评分与回读证据：[leaderboard-result.json](leaderboard-result.json)。官方榜单 CSV SHA256：`d1efe981102b93c8a8486df0845f1341e6b53ee03b495bae8b262d4446d1f478`。

## 原始接收回执（保留历史状态）

- HF 账号：`cylovelife`；榜单使用匿名显示名 `aidd-agent`。
- 赛道：Regression Prediction。
- 接收时间：2026-10-28 **19:17:21，北京时间**（11:17:21 UTC）。
- 平台原始回复：Submission received from 'aidd-agent' for the Regression Prediction track. Your predictions are being processed and should appear on the leaderboard within 2 hours.
- 上传文件 SHA256：`a500cdab26d27142a840a785643b71e3356388dd9a3600c8296e298977f5b47c`。
- 实际方法链接：[9e83882 版本方法报告](https://github.com/cylovelife/aidd-agent/blob/9e83882/docs/method-report.md)。
- 披露：代码开放，未使用专有数据；可选私人联系方式未提供，未来出版物选项未勾选。
- 当时状态：收到、待异步评分；该原始接收回执的 `official_score=null` 保留不改写，后续评分见上节。

本地完整意图/回执：`state/submissions/20261028-first/intent.json`、`receipt.json`。公开必要回执见 [submission-receipt.json](submission-receipt.json)。官方榜单入口：[OpenADMET CYP](https://huggingface.co/spaces/openadmet/cyp-challenge)。

19:17:46 首次回读官方回归榜 CSV，共 279 条，未出现本条目；19:19:21 再次回读共 280 条，仍未出现；截至 19:31 仍在等待。19:34 回读共 281 条，已精确找到本次条目。全程仅一次上传，后续均为只读查询。

只读查询命令：`uv run --group submission aidd check --receipt-dir state/submissions/20261028-first`。它只按显示名及本次版本化方法链接同时匹配条目，保存下载榜单的哈希和查询时间；同名但方法链接不同的条目不会误判为本次评分。

## 后续判定

本轮已满足“已评分有效提交”判据。后续模型改进先登记新的协议和预算，遵守 12 小时限流，并区分最新有效提交与历史最佳；最终榜在比赛结束后另行核查。
