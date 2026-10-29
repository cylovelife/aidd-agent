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

第三轮已完成辅助数据审计、折外迁移与联合任务网络两阶段实验；低活性误差有下降，
但未兼顾总体/高活性，**没有提交新结果**，保留确认集。
见[第三轮结果与未解决的数据缺口](docs/round3-results.md)、[调研依据](docs/round3-research.md)。

第四轮完成NCATS/PubChem与ChEMBL公开CYP2D6低活性审计；保留实验条件、删失关系，
排除官方分子/骨架重叠后测试来源分离的迁移。固定混合在开发集改善1.30%，未达门槛，
**不提交，确认集继续封存**。见[第一性原理与来源研究](docs/round4-research.md)、
[冻结方案](docs/round4-plan.md)、[结果与复现](docs/round4-results.md)。

第五轮逐条复核79条可疑精确低活性记录的原文/SI，仅2条原始曲线支持保守删失界限，
未补齐多骨架覆盖。固定删失监督对照总体仅改善0.48%，低活性层反而恶化4.27%；
**不提交，确认集仍未评估**。见[审计、实测与限制](docs/round5-results.md)、
[拟合前方案](docs/round5-plan.md)、[26个出处的证据锁](docs/round5-evidence-lock.json)。

第六轮继续核验姜黄素原件，新增4条来自两个新骨架家族的来源原生界限，合计6父体/3骨架；
姜黄素视觉/响应缺口仍未关闭，未准入。固定实验总体改善0.55%、低层恶化4.21%，
**仍不提交、确认集未评估**。见[原件可得性、准入与实测](docs/round6-results.md)、
[冻结方案](docs/round6-plan.md)、[证据锁](docs/round6-evidence-lock.json)。

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
uv run aidd transfer --output-dir state/runs/my-third-run
```

可选CPU神经对照（不需要GPU）：

```bash
uv sync --frozen --group neural
uv run --group neural aidd transfer --neural --output-dir state/runs/my-neural-run
```

第三轮命令会执行冻结门槛；未达标时只保存实验报告，不生成可上传预测。

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
