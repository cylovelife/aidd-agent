# CYP 资格、规则与来源核查

核查日期：2026-10-28（Asia/Shanghai）。一手来源：

1. [官方公告](https://openadmet.ghost.io/announcing-openadmets-cyp-inhibition-blind-challenge/)
2. [实时提交平台及 FAQ](https://huggingface.co/spaces/openadmet/cyp-challenge)；本轮通过该公开 Gradio 应用 `/config` 读取提交表单、FAQ 和时间表。
3. [官方教程](https://github.com/OpenADMET/CYP-Challenge-Tutorial)
4. [官方数据](https://huggingface.co/datasets/openadmet/cyp-challenge-train-test)

## 资格与身份

- 官方参加步骤要求 Hugging Face 账号，表单必填真实 Username；公开页面未列学历、机构、地域或收费门槛。这个结论是**未发现公开排除项**，不是主办方对个人资格的专门确认。
- 同一团队/实验室共同准备的参赛者只用一个 HF 账号；不允许密切合作团队通过个人多账号重复提交。
- 表单支持匿名展示；可填 Alias。姓名、邮箱、Discord、机构为可选私人字段，本轮不代填；不虚构机构背书。
- 用户已提供 HF Username `cylovelife`，公开个人页面可访问；账户的实际参赛接受状态仍需真实提交回执确认。

## 赛道与提交

- 首轮仅回归，独立评分；无需同时参加 TDI 分类或结构预测。
- 回归 CSV/Parquet 必须是 750 行、6 列，列名：`SMILES`、`Molecule_Name`、`CYP1A2_pIC50_direct_inhibition`、`CYP2C9_pIC50_direct_inhibition`、`CYP2D6_pIC50_direct_inhibition`、`CYP3A4_pIC50_direct_inhibition`。
- 每分子四列预测必须全部是有限数值；ID/SMILES 与官方测试集对应。以官方 validator 实际检查为准。
- 进一步核读平台 `submission.py` 与 `config.py`：回归每列必须非恒定且样本标准差至少 **0.01**。官方教程 validator 未覆盖此项，本项目额外检查；常数参考不上传。
- 频率：最多每 12 小时一次；最新有效提交计入实时榜。结果未明先检查既有记录，不重复非幂等提交。
- 截止：2026-11-03 23:59 UTC，即 2026-11-04 07:59 北京时间。
- 实时表单要求最终榜单参赛者截止前提供可访问的 HTTPS 方法报告；若声明开源，也必须提供公开代码链接。可选未来出版物参与勾选不等于报名必需项。

## 数据、开放与评分

- 外部数据及预训练模型允许；专有训练数据必须勾选并公开披露。首轮只用官方公开数据，`proprietary data=false`。
- 标准榜单不强制代码开源；申报创新 ML 认可需要开放代码。本项目按用户授权同步 GitHub，只有确认仓库公开可访问后才声明 `open source=true`。
- 官方数据卡与教程标注 Apache-2.0；下载时保存实际 revision、许可证与出处，复用上游文件时保留许可/作者标记。
- 主指标是四终点宏平均 Soft-Threshold RAE；官方解释为对低活性区域作区间容忍处理。实际实现需读取官方 scorer 并验证，不能用普通 MAE 冒充。
- 单一连续盲测阶段；9 月的 interim 公布全测试集表现，FAQ 明确不会在比赛结束前公开测试标签。

## 尚未核实或尚未发生

- 账号 `cylovelife` 的平台接受状态、是否已有提交及账户层面限制。
- 本轮已固定官方教程 revision `832ae6d6447b07c2c71059de34d07f1130388247`，复用其评分函数和 validator；提交文件已本地通过。平台实时评分尚未发生。
- 官方有效回执、异步评分完成和最终名次。

上列不确定性不阻止本地环境、数据与基线工作。后续发现规则更新时记录差异并调整，不能把旧快照当实时许可。
