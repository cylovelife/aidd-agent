# aidd-agent

个人 AIDD 学习与竞赛工程。首个任务是 OpenADMET CYP 2026 的药物代谢酶直接抑制活性预测，目标是在截止前完成一次有效盲测提交。

第二轮预测已获官方评分：截至 **2026-10-29 12:06（北京时间）**，显示名 `aidd-agent`，
实时回归榜 **222 / 285**，**MA-ST-RAE 0.920131**（越低越好），比首轮 0.928498
改善约 **0.90%**。名次为实时公开榜，不是最终名次；见[第二轮提交与评分记录](docs/submission-round2.md)。
首轮历史 223/281 与回执保留在[首轮记录](docs/submission-status.md)。

2026-10-29 第二轮优化：10 个固定候选、3 个骨架开发切分，宏平均误差由原 Ridge
0.985167 降至 **0.735632**（下降 25.33%），本机单次约 2 分钟、峰值内存约
1.45 GiB。开发集结果不能代替盲测分数；见[第二轮运行与差距分析](docs/run-2026-10-29.md)、
[第二轮方法报告](docs/method-report-round2.md)和[第二轮官方状态](docs/submission-round2.md)。

- [竞赛执行计划与进度](docs/competition-plan.md)
- [资格、规则与官方来源](docs/cyp-rules.md)
- [公开方法报告](docs/method-report.md)
- [2026-10-28 运行记录](docs/run-2026-10-28.md)
- [数据与上游版本锁](docs/sources-lock.json)

## 本地复现

需要 `uv` 和 Python 3.12；首次运行需联网下载依赖与公开数据，训练在本机 CPU 完成。

```bash
uv sync --frozen
uv run aidd fetch
uv run aidd baseline --output-dir state/runs/my-first-run
uv run aidd validate state/runs/my-first-run/regression.csv
uv run aidd optimize --output-dir state/runs/my-second-run
uv run aidd validate state/runs/my-second-run/regression.csv
```

输出目录必须不存在，已有原始数据须通过 SHA256 校验；不覆盖旧实验。原始文件、预测与本地回执保存在被 Git 忽略的 `state/`。

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/aidd_agent
```

本地分组验证与官方盲测分开报告；没有平台评分回执就不报告比赛分数。代码采用 MIT；`src/aidd_agent/vendor/openadmet/` 保留上游 Apache-2.0 许可，数据遵守其自己的许可。

## 官方提交

`uv sync --frozen --group submission` 安装可选 SDK。`aidd submit` 是一次真实外部提交，需要明确给出 HF 账号、版本化方法报告 URL、已审核预测 SHA256 和新的回执目录，详见 `uv run --group submission aidd submit --help`。已有回执目录会拒绝再次上传；网络结果不明时先查记录。不要通过重试或多账号绕过官方每 12 小时一次的限流。

只读回查已提交条目，不会重新上传：

```bash
uv run --group submission aidd check --receipt-dir state/submissions/20261028-first
```
