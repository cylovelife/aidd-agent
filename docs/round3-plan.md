# 第三轮冻结方案：辅助观测迁移与低活性验证

2026-10-29，所有第三轮候选训练前登记。目标：修正前两轮验证暴露不足，检验
辅助观测是否改善 CYP2D6 低活性预测；无可信提升则不生成/上传新提交。

## 数据与不变量

- 使用原固定 revision 的主表及已哈希的官方 single-concentration 表；单浓度
  是独立辅助任务，绝不直接替换缺失 pIC50 或变成零值/伪精确标签。
- 分子并集 4,906。TDI、Emax 及另一个官方原始 CYP3A4 测量集本轮不参与拟合；
  审计依据见 [round3-research.md](round3-research.md)。
- 每个外层/内层验证分子均按规范分子身份从全部训练观测排除。骨架切分还按
  骨架排除；类似物切分允许共享骨架，明确只测试局部结构迁移。所有特征、标准化、
  PLS、校准和残差拟合只用该折训练分子，盲测结构只作身份/相似度审计和预测。
- 不复制外部参赛者权重/预测；不利用官方分项或测试活性率校准/选择模型。

## 验证先冻结

1. 保留 20% 骨架组为**本轮确认集**。在 seed=31415..31424 的有限序列中，取首个
   CYP2D6 已测低活性(pIC50<4)至少 20 个、各终点已测至少 100 个的切分；只看
   标签可用性/样本数，不看模型输出。它是本轮封存，不能声称历史上从未参与过拟合。
2. 剩余开发池做两次骨架组 80/20 切分，seed=73/74，控制跨骨架泛化。
3. 开发池另建类似物扩展压力集：分别保留 CYP1A2/2C9/3A4 pIC50 前25名为
   训练锚点，合并锚点后为每个挑至多10个最近 Morgan bit-Tanimoto 邻居作为验证；
   锚点永远不被抽走、精确分子身份不得相交。只模拟公开的形成机制，不声称恢复盲测分布。
4. 保存每种切分、标签数、低/高活性数、骨架重叠与最近邻相似度。模拟集过小或
   单层缺失时明确记录，不能靠重选模型分数有利的切分修复。
5. 主指标为官方 ST-RAE；同时报告 <4 与 >=4 的平均区间外距离、带符号偏差。
   单浓度预测误差单独计算，不能冒充缺失直接 pIC50 的验证标签。

## 五个候选与计算预算

- `baseline`：第二轮已冻结的逐终点模型，使用本轮相同训练分区从零重训。
- `screen_linear`：count-Tanimoto KRR(alpha=1) 学习四个单浓度 readout；外层训练
  池内再做3折 GroupKFold 产生折外辅助预测。每终点用 StandardScaler+Ridge(alpha=10)
  从这4个折外预测学习 pIC50，推理仅需分子结构。
- `screen_residual`：在上一项基础上以 count-Tanimoto KRR(alpha=1) 拟合已测 pIC50
  的训练残差，中心仅来自当前训练标签。
- `screen_blend`：baseline 与 screen_residual 各 .5，权重固定，不根据榜单调整。
- `screen_pls`：用训练池内单浓度观测拟合 StandardScaler 与 PLSRegression
  (16 components, scale=False, max_iter=100, tol=1e-6)，监督学习共享表示；
  每终点用标准化的 PLS scores + Ridge(alpha=10) 拟合其已测 pIC50。

特征沿用第二轮 Morgan bit/count 与217个二维描述符，不增加指纹/超参网格。
最多2计算线程、4 GiB RSS、单轮1800秒；无新增付费资源/大型依赖。先测开发集，
选型后才允许对确认集计算一次；失败留证据，不临时扩大候选/搜索或重选确认集。

## 选型与提交门槛

- 只在开发集分终点选择。非基线候选必须该终点平均 ST-RAE 至少改善3%，且平均
  低/高层区间外距离均不得恶化超过5%。CYP2D6 额外要求低层改善至少10%；
  没有合格候选就保留该终点 baseline。若 CYP2D6 仍为 baseline，则本轮不提交。
- 固定选型后，确认集必须宏平均 ST-RAE 改善至少5%，CYP2D6 总 ST-RAE 改善
  至少5%、低层区间外距离改善至少10%，高层不得恶化超过5%，其他终点 ST-RAE
  均不得恶化超过5%。每终点至少100个已测、CYP2D6低层至少20个，否则证据不足。
- 确认集做1000次配对骨架 bootstrap，宏平均差(候选−baseline)的95%百分位上界
  必须小于0。它只衡量本轮确认样本的不确定性，不证明验证与盲测分布已一致。
- 任一门槛不满足则正常结束，`submission_eligible=false`，不上传、不用公榜追加调参。
- 全部满足才全训练池重训选中模型，生成750行，验证身份/有限值/std/官方validator，
  发布版本化方法报告，核对最新提交与12h间隔后按既有授权上传。本轮没有绕过限流权限；
  第二轮提交时间为2026-10-29 11:45北京时间，最早下一次为当天23:45之后，以平台为准。

## 工程、路由与交付

新增 auxiliary/transfer_validation/transfer 模块和 CLI transfer，复用既有特征、
指标与基线工厂，不改变前两轮协议。测试覆盖辅助行污染不影响验证预测、规范分子/
骨架排除、折外覆盖、缺失标签保持、真实低/高失败门槛和新目录保护。运行项目 pytest、
Ruff、mypy、wheel/隔离安装 smoke；保存计划/源码/依赖/数据/分区哈希与耗时。

Skill：deep-research(TECH/Standard，frameworks-tech/evidence-grading/output-templates)、
brainstorming、writing-plans、executing-plans、test-driven-development、git-workflow、
finishing-a-development-branch、verification-before-completion。
规则：engineering-workflow、python/code-style、python/data-runtime、shared-code-change-safety、
anti-hallucination、research/deep-research。旧 Skill/规则正文沿用本对话已加载版本，
本轮已重新核对索引/根AGENTS，新增调研规则/引用已读取。Harness adequate；只涉及Python。
不加载：论文写作、付费云、公司GitLab；不委派 Agent。GitHub同步继续获授权，代码与失败
结论也应交付；竞赛上传单独受上述改善门槛约束。
