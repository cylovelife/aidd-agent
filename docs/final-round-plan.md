# 最后一轮：冻结神经头与有限编码器微调

2026-11-02，CYP标签拟合前冻结。用户授权最后一轮；有可信提升才上传，否则保留
当前有效提交、总结全部参赛过程并同步GitHub。不因本轮失败追加候选或再开新轮。

## 资源探针与固定训练预算

先在原开发fit身份中的128个分子上测4个batch，合成零目标，不用CYP标签训练或
验证分数、不复用参数。CPU2线程、batch32，单batch中位0.174579秒，进程峰值
986644480bytes；探针原件在state/sources/final-round/resource-probe.json。
据此冻结单seed17、最大12epochs、内层检查4/8/12；部分解冻最坏内层12+重训12，
三个外层切分预计约1200–1500秒。整个开发runner硬上限1800秒、4GiB，不扩预算、
不使用GPU/付费算力。实际越限保留诊断并停止依赖步骤，不把未完成训练记为负结果。

## 三个固定候选

baseline：原第二轮终点模型，第七轮同分区已保存预测，哈希/身份复核后复用。
frozen_head：原CheMeleon固定2048维向量，LayerNorm（无可学习仿射参数）→
Linear2048/64→ReLU→Dropout0.1→Linear64/4，四终点独立输出、共享隐层。
partial_tune：相同初始化/相同头，仅解冻原编码器最终原子投影W_o权重与bias，
其余消息传递权重冻结；沿原MeanAggregation，不全量微调。
使用LayerNorm避免第八轮逐特征稀有方差放大，不通过验证结果选择归一化。
预训练来源/权重/依赖沿用round7-sources-lock.json；仅本地编码，无分子上传。

两神经候选均AdamW，头lr1e-3、W_o lr1e-5，weight_decay1e-4、grad norm<=1，
batch32（以batch组随机打乱，seed17），无额外调度/增强/低活性重加权。
每终点标签按fit-only均值/标准差变换，区间同步变换。mask缺失，按终点平均，
损失为0.5×（点值SmoothL1 + 区间外距离SmoothL1），beta0.5，不截断预测。
同一外层fit内用scaffold GroupShuffleSplit(seed101,15%)挑选4/8/12中最小宏ST-RAE
epoch；随后丢弃内层参数，重新加载原权重和头初始化，用外层fit重训选定epochs。
外层标签仅最终评估；原963分子确认不进入任何开发fit/valid/早停。
若部分投影微调仍不达标，不追加全量微调、更多seed/epoch/学习率/集成。

## 验证与提交门槛全部沿用

逐行复用第七轮scaffold73/74/analog expansion及原确认SHA256
f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a。
select_development不改：每终点ST-RAE改善>=3%，低层恶化<=5%（2D6改善>=10%），
高层恶化<=5%，至少2/3切分总体改善；组合宏平均>=3%且2D6合格才能开一次确认。
确认沿用confirmation_gate：宏及2D6各>=5%、2D6低层>=10%、高层及其他终点
恶化<=5%，各终点>=100标签/2D6低层>=20；1000次配对骨架bootstrap宏差95%上界<0。
先锁定一个组合再开确认，失败不重选。开发无合格则确认不评估、不生成盲测CSV。
通过全部条件才全量重训/官方validator/身份有限值及标准差检查、最新规则和最新
有效提交/12h核对、公开准确方法及预训练披露后上传并回读；公榜只核验身份/接收状态。

## “最好成绩”的核验边界和交付

核对本项目所有已获官方评分提交；无新合格方案时保留其中分数最低的现有有效提交。
不把未经盲测的本地候选称为更好，不保证未尝试模型/隐藏榜或最终排名的全局最优。
实时回读需匹配本项目alias和版本化方法URL；若网络受阻，保留既有回执并明确缺口，
继续完成本地实验与总结，不宣称实时核验通过。方法报告需保持公开可访问。
按tech-blogger整理技术总结：问题/数据/验证、各轮方案、正负结果、失效诊断、
本轮结果、官方提交、限制与可复现入口；不将工程检查当研究效果或最终比赛成绩。
代码/报告/摘要哈希同步GitHub；原数据、模型、预测、训练轨迹留state。

路由：writing-plans、executing-plans、test-driven-development、verification-before-completion、
git-workflow、finishing-a-development-branch、tech-blogger（总结）。规则：AGENTS、
skills-index、engineering-workflow、Python code-style/data-runtime、shared-code-change-safety、
anti-hallucination、writing/tech-blog；研究/官方资料复用本会话已核验证据。Harness adequate。
