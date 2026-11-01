# 第七轮：固定验证下的分子表示消融

2026-11-01，任何本轮模型拟合前冻结。用户授权实施、有可信提升才提交、同步GitHub。

## 不变量与验证

复用第三轮4906分子主/辅助身份并集，仅官方真实直接标签监督；不使用辅助实验值作输入。
原始数据与第二轮提交不覆盖；确认分区沿用seed31415、963分子及既有SHA256
`f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a`。
它从第三轮起未评估，但部分样本在更早研究曾使用，不宣称历史上完全独立。
开发仅3943分子，固定scaffold73/74与analog expansion，按原radius2 bits生成并冻结
精确分区，不为新指纹重选样本。analog可共享骨架、精确分子不交叉；相似度差异如实报告。
每个切分/终点保存逐分子预测、ST-RAE、低/高层区间距离、相似度分层误差。

## 有限候选与归因

五个候选：baseline（第二轮终点模型）、chiral_r2、radius3、feature_morgan、chemeleon。
前三个指纹变体各只改Morgan生成器一个因素：includeChirality=True、radius=3、
MorganFeatureAtomInvGen；均2048 bins，bits与log1p counts成对变化，217描述符保持。
保持第二轮每终点模型、超参、固定集成权重不变。因此1A2纯描述符基线在三个变体中
相同，是有意的负对照，不声称该终点接受了指纹改动。无网格搜索或新集成。
预训练对照：Chemprop2.2.1、Zenodo15460715 CheMeleon消息传递权重，冻结eval，
均值聚合成2048维向量；每终点fit-only StandardScaler + Ridge(alpha10)，不微调。
来源 https://chemprop.readthedocs.io/en/main/chemeleon_foundation_finetuning.html
及 https://zenodo.org/records/15460715 。权重md5须为6a80b54fdb7de37ef0374d302f01e8ce，
下载后另存SHA256、来源/许可证说明。预训练为外部结构/描述符知识，不新增赛事活性
标签；预训练语料逐分子重叠未知，必须披露，不能称已全量排除。仅下载公共权重，
不向服务上传分子。失败保留诊断，禁止以随机权重冒充预训练；可独立完成指纹实验。

## 选型与门槛

按原choose_transfer_models每终点选择：开发均值ST-RAE改善>=3%，低层不得恶化>5%
（2D6必须改善>=10%），高层恶化<=5%；再要求所选模型至少2/3切分ST-RAE改善。
最终组合宏平均开发改善>=3%，且2D6必须有合格改动，才能打开一次确认。
只选定一个组合，再打开；不得按确认结果重选、回退不同组合或追加候选。
确认沿用confirmation_gate：宏平均及2D6各改善>=5%、2D6低层改善>=10%、高层
及其他终点恶化<=5%；各终点>=100标签、2D6低层>=20；1000次配对骨架bootstrap
宏差95%上界<0。确认失败停止，不重开。开发无候选则确认保持未评估，不产盲测CSV。
通过才全量重训、官方validator、原SMILES/750唯一身份/有限四列/标准差检查，
复核实时规则、最新提交及12h间隔、公开准确方法报告后提交并回读；公榜不选型。

## 执行与交付

本机CPU2线程、4GiB峰值RSS；指纹开发拟合与预训练编码/拟合各1800秒上限，
下载/安装/软件检查另计；不使用GPU/付费算力。新目录保留诊断，缓存哈希绑定
原始SMILES顺序、编码源码、依赖和权重。预训练在指纹之后执行，不按指纹结果改方案。
实现独立representation模块，旧入口不变。测试真实手性区分、缺失/非有限输入、
fit-only预处理、分子/确认排除及门槛失败路径。项目pytest、Ruff、mypy及可选组检查。
GitHub同步代码、冻结方案、结果摘要/哈希；模型/原数据/预测留state。负结果也交付。

实际流程：deep-research、writing-plans、executing-plans、test-driven-development、
verification-before-completion、git-workflow、finishing-a-development-branch。
规则：AGENTS、skills-index、engineering-workflow、Python code-style/data-runtime、
shared-code-change-safety、anti-hallucination、research/deep-research。Harness adequate。

拟合前兼容性决策：Chemprop2.3.1间接要求RDKit2026.3.6，会改变历史特征运行时；
改用上游支持CheMeleon的2.2.1并锁定原RDKit2026.9.1。未拟合或查看开发分数。
CheMeleon上游代码MIT，公共权重来源锁和哈希保存在本轮sources-lock；不转发权重。
