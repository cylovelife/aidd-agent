# 第二轮官方提交记录（2026-10-29）

## 已评分：MA-ST-RAE 0.920131，实时榜 222/285

北京时间 **2026-10-29 12:06:04**，从官方实时回归榜下载 CSV，精确匹配
`aidd-agent` 和本轮版本化方法 URL，确认 **MA-ST-RAE 0.920131143142261**，
**222/285 条目**。相比首轮 0.9284982814，误差相对下降 **0.90%**；
提交前回读首轮为 227/285。它是已评分的实时公开榜结果，不是最终名次。

[评分回读证据](round2-leaderboard-result.json)；官方榜单 CSV SHA256：
`e2c663880ac7c1df647484e9a6611d6a61d8362722132b69112d3ecfd2b2a8b7`。
本地开发集的 25.33% 改善没有等幅转化为官方收益，不能以本地成绩宣称接近前三。
分终点回读显示 CYP2C9/3A4 改善、CYP1A2/2D6 退步；
见 [官方分项证据](round2-endpoint-result.json) 和 [完整差距复盘](run-2026-10-29.md)。

## 接收历史

北京时间 **2026-10-29 11:45:50**，平台接收真实 HF 账号 `cylovelife`、匿名显示名
`aidd-agent` 的第二轮 Regression Prediction 提交。当前回执状态为
`received_pending_scoring`；平台提示最多可能需要 2 小时处理。
原始接收回执保留该状态；上方评分证据独立记录，不覆盖接收历史。

- 方法/代码版本：`01b451df45e915c28b70a065e676f38ff9b15767`。
- [版本化公开方法报告](https://github.com/cylovelife/aidd-agent/blob/01b451df45e915c28b70a065e676f38ff9b15767/docs/method-report-round2.md)。
- 预测 SHA256：`f6b1987532b0d2469e5527f8702d6017f04dc5a65c32cebd6c4f16d50fc49b28`。
- [平台接收回执](round2-submission-receipt.json)；完整本地证据：
  `state/submissions/20261029-round2/`。
- 主数据 revision 与首轮一致；无专有数据、代码公开、出版选项不勾选、私人字段不填写。
- 本地与官方 validator 均通过；三切分开发集改善 25.33%，不是官方评分。
- 提交前再次回读首轮最新条目：227/285、0.9284982814、2026-10-28 11:17 UTC。
  已满足 12 小时间隔；仅上传本轮一次，结果不明时不重试。

后续检查必须精确匹配新的方法 URL 与 alias，不能把还显示在榜上的旧方法
0.928498 分数误认作第二轮。最新有效提交计分，不是历史最好成绩。
首轮历史证据保留在 [submission-status.md](submission-status.md)。

```bash
uv run --group submission aidd check --receipt-dir state/submissions/20261029-round2
```
