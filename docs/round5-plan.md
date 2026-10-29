# 第五轮方案：79条原始低活性记录复核与删失监督

2026-10-29。数据审计与模型选择分离；先按原文/SI确定准入覆盖，再固定数据/源码/方案
哈希后拟合。保留第四轮所有失败结论与原始文件，不因本轮来源复核修改历史输出。

## 证据准入

逐activity_id追溯26个出处：数值原单位、底物、酶来源、NADPH启动/预孵育、最高抑制剂
浓度、拟合是否超范围、重复来源。优先右美沙芬/直接条件；短暂无NADPH预孵育不能自动
判成TDI。其他底物必须单独assay/source头，未知关键条件继续隔离。

- 数据库Outside typical range是审计触发器，不等于错误；原表可解除相应隔离。
- 明确超测试范围的拟合值不作为精确标签。仅原曲线/原文支持单向界限时才形成删失；
  缺少原始响应时不从“拟合值大于最大浓度”自动证明严格实验界限。
- 原文单位或log参照单位错误必须以原表/方法纠正，去重同一化合物同一测量的IC50与logIC50。
- 数值确认但最大浓度/曲线未知保持隔离；其他终点的剂量不能补作CYP2D6剂量。
- 没有原文的记录标获取缺口；不声称26份原文/SI全部可得。

结构、原始值和派生区间留在state；公开文档只保留必要审计判定、出处及哈希。
准入覆盖/去重/排除数在审计锁中固定后才能执行模型实验。

拟合前准入锁：79条全部有逐条判定，65条隔离、10条重复排除、2条TDI排除，
仅2条ACS 2020原始SI直接抑制曲线转成`pIC50 <=4`保守界限（非精确点、非统计
置信上界）；一个研究、同一个骨架。专利另4条虽在两套名义剂量范围内，仍缺逐
化合物曲线与最大剂量分配，且底物为Vivid，暂不训练。姜黄素6个log条目存在
约1000倍标准化差异，其中1条重复；原图单位/结构映射未完成，不放入训练。
审计锁`state/sources/round5/locked-audit/audit-lock.json`在拟合前写定，逐条CSV
SHA256为`75e47ecff308fc8d9bec86bcfb8c016b6a2afd2bdda3173d261882d5f4009739`，
准入CSV为`f3aaf4f9760bc263c860b0c1a24ac5a81c5b5f94baf55a3610466b0c81e8c107`。
模型runner再次校验源文件/证据/CSV哈希，计算官方全部训练、辅助和盲测结构排除。

## 固定模型假设（拟合前）

假设：正确单位和删失边界能补充弱活性结构信息，但实验域偏移可能吸收或反转收益。
同一优化器的官方标签对照检验收益来自损失还是外部来源；不借公榜校准或增加超参搜索。

4个候选，仅改变CYP2D6，其他3终点保持第二轮固定模型：

1. baseline：bit-Tanimoto SVR(C=1, epsilon=0.1)，同分区从零拟合。
2. interval_control：仅官方已测CYP2D6的原可信区间；Tanimoto RKHS，区间外Huber损失。
3. interval_transfer：相同损失，加来源已核验的精确点/区间/单侧删失；保留独立来源偏移。
4. interval_blend：baseline与interval_transfer各半，固定权重。

形式：`f(x,assay)=k(x,X)alpha + intercept + assay_offset`。官方assay偏移固定为0，外部
每来源偏移L2正则系数1；RKHS系数正则1；Huber delta=0.1。官方每观测weight=1，外部
每观测weight=0.25；无类别重平衡或数据依赖权重。Cholesky加1e-8数值jitter，以标准化
RKHS坐标优化；不拟合盲测变换。外部缺失标签不参与损失；单侧界限另一侧保持无穷。
L-BFGS-B maxiter=2000、ftol=1e-10、gtol=1e-5；未收敛明确失败，不临时改候选。

## 验证、算力与提交

复用第三轮963分子确认集与原哈希；开发为seed73/74骨架及原类似物压力切分，明确
是重复使用的开发集。父体/盐型/互变异构体键与骨架排除复用第四轮已验证实现；外部
全局排除官方训练/辅助/确认/盲测父体与保守骨架，去除同源及同父体重复。

开发候选须：平均CYP2D6 ST-RAE改善>=3%，低层(<4)距离改善>=10%，高层恶化<=5%，
至少两个切分总体改善，低/高层均非空。外部贡献另作同优化器的直接/半权配对对照，
不把损失变化收益写成外部数据收益。允许官方区间control作为方法改善候选，但必须
明确其不使用外部标签。候选固定后按ST-RAE最小选择；不降低既有门槛。

开发无合格候选则不打开确认集、不生成盲测CSV、不上传。通过才一次性确认：宏平均
改善>=5%、2D6总体>=5%、低层>=10%、高层恶化<=5%、其他终点恶化<=5%，每终点
>=100标签/2D6低层>=20，1000次配对骨架bootstrap宏差95%上界<0。确认后不追加调参。
全部通过才全量重训、官方validator、公开版本化方法、最新提交与12h限流检查后上传。

2计算线程、4GiB峰值RSS、单轮1800秒，不用付费算力/GPU/新大型依赖；采集与PDF核验
单独计时。每轮新目录，输出源码/原始文件/数据锁/分区哈希、逐分子预测及优化轨迹。

## 实施与路由

新增独立censored模型/runner及CLI，不改前四轮语义；测试覆盖单侧损失不向边界推断
伪精确值、梯度/真实拟合、NaN/无穷合法性、源偏移、重复排除与外层污染不影响拟合。
项目pytest、Ruff、mypy与安装包smoke；科研门槛失败与工程测试失败分开报告。

已读：索引、项目AGENTS；deep-research及TECH/evidence/output引用、executing-plans、
writing-plans、brainstorming、test-driven-development及anti-patterns、PDF（只读）、
web-access、dispatching-parallel-agents、verification-before-completion。
规则：engineering-workflow、python/code-style、python/data-runtime、research/deep-research、
anti-hallucination、shared-code-change-safety。Harness adequate；Git收尾再装交付Skill。
web-access明确建议独立多来源任务委派，故3个只写各自state子目录的文献核验Agent并行，
主Agent独占优先来源、准入裁决、代码和拟合。不使用Java/TS/Rust/公司数据库/付费云流程。
