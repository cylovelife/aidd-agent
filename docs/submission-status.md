# 首次官方提交状态

## 已收到，等待评分

- HF 账号：`cylovelife`；榜单使用匿名显示名 `aidd-agent`。
- 赛道：Regression Prediction。
- 接收时间：2026-10-28 **19:17:21，北京时间**（11:17:21 UTC）。
- 平台原始回复：Submission received from 'aidd-agent' for the Regression Prediction track. Your predictions are being processed and should appear on the leaderboard within 2 hours.
- 上传文件 SHA256：`a500cdab26d27142a840a785643b71e3356388dd9a3600c8296e298977f5b47c`。
- 实际方法链接：[9e83882 版本方法报告](https://github.com/cylovelife/aidd-agent/blob/9e83882/docs/method-report.md)。
- 披露：代码开放，未使用专有数据；可选私人联系方式未提供，未来出版物选项未勾选。
- 最新已知官方评分：**尚未返回**；不能把接收消息当评分成功或获奖证明。

本地完整意图/回执：`state/submissions/20261028-first/intent.json`、`receipt.json`。公开必要回执见 [submission-receipt.json](submission-receipt.json)。官方榜单入口：[OpenADMET CYP](https://huggingface.co/spaces/openadmet/cyp-challenge)。

19:17:46 首次回读官方回归榜 CSV，共 279 条，未出现本条目；保存在 `state/leaderboards/post-submission-01/`。19:19:21 再次回读共 280 条，仍未出现本条目；后续只读取榜单，不重复上传。

只读查询命令：`uv run --group submission aidd check --receipt-dir state/submissions/20261028-first`。它只按显示名及本次版本化方法链接同时匹配条目，保存下载榜单的哈希和查询时间；同名但方法链接不同的条目不会误判为本次评分。

## 后续判定

只有官方榜出现与本条方法链接和显示名一致的条目，并带 MA-ST-RAE 等评分时，才标记为“已评分有效提交”。记录榜单时间、分数、名次和总条目数；实时榜与最终榜分开。若超出官方提示的两小时仍未出现，先检查官方回执/错误渠道；向主办方发消息须有用户对应授权。
