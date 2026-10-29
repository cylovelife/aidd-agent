# 第二轮官方提交记录（2026-10-29）

## 已接收，等待官方评分

北京时间 **2026-10-29 11:45:50**，平台接收真实 HF 账号 `cylovelife`、匿名显示名
`aidd-agent` 的第二轮 Regression Prediction 提交。当前回执状态为
`received_pending_scoring`；平台提示最多可能需要 2 小时处理。
**尚无第二轮官方分数/排名，不将本地改善当作盲测成绩。**

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
