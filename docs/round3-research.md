# 第三轮调研：先检验辅助实验与验证偏差

日期：2026-10-29。建议先做折内辅助任务迁移和低活性压力验证，不扩大同一开发集
的超参搜索。辅助观测确实增加覆盖，但尚不能证明能改善盲测。Confidence: M；
数据覆盖已核实，效果必须由下面冻结实验确认。

## 已证实的数据事实

本机重新验证三份辅助原始文件 SHA256，与第二轮登记一致。单浓度表有 4,376×4
观测，浓度均为 4.95049505e-5 M、分子/酶配对无重复；与主表合并后共 4,906 个
唯一规范分子，与盲测规范身份重叠为 0。CYP2D6 有 2,883 个未测直接 pIC50 的
分子带有单浓度读数。直接标签已测/未测两组的 log2fc 中位数分别约 -1.738/+0.376，
说明只拟合已测 pIC50 会丢掉大量弱响应区域的信息。**弱响应不等于已知 pIC50<4**，
不能据缺失或 fold-change 构造虚假精确 pIC50。Confidence: H，原始表可复算。

Emax 的直接条件观测数与主表逐终点一致，没有扩大直接标签覆盖。TDI 条件在
CYP3A4 上观测更多，但测量条件/机制不同；本轮先隔离检验单浓度贡献。
另查到官方 [Octant 原始数据卡](https://huggingface.co/datasets/openadmet/Octant_CYP_inhibition_reactivity_blog_release/blob/96dc1cceaa545a22041d1e16a9c2524a658403f8/README.md)：
它的 inhibition 子集是 CYP3A4 预孵育下的组合抑制测量，并非 CYP2D6 直接标签。
本轮不下载活动行、不并入训练；不能因为同为官方发布就合并成同一个终点。

## 可借鉴的方法与边界

1. [Lo-Hi，arXiv:2310.06399](https://arxiv.org/abs/2310.06399) 区分 lead optimization
   与 hit identification 的验证任务。借鉴其“按实际使用场景选拆分”的原则：同时保留
   骨架外推控制与有训练锚点的类似物扩展压力集。不声称本项目实现了论文算法。
   [SIMPD 原论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10712068/) 进一步表明随机和
   邻居切分均不能自动替代时间切分；本赛事无合成时间，不能假造时间验证。
2. [同赛道开源实现](https://github.com/avnikonenko/openadmet_challenge_cyp_2026/tree/6570df21791bba528801b51fb22ced5c32d17270)
   展示折安全的辅助任务预训练与 joint multi-assay 思路。它是作者方法/代码证据，
   不是本项目已复现的性能结论；不复制其权重、预测或榜单校准。
3. [ADMET Workbench 方法记录](https://supercowpowers.github.io/workbench/blogs/cyp_challenge/)
   将不同测量作为不同任务，强调命中富集训练与稠密测试的人群差异。本轮只借鉴
   分离任务与偏差诊断，不采用基于榜单或假定测试活性率的校准。
4. [StackingRegressor 官方说明](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingRegressor.html)
   的折外预测原则用于辅助预测→pIC50 的第二层校准；每个外层验证分子在全部辅助
   训练中排除。[PLSRegression 官方接口](https://scikit-learn.org/stable/modules/generated/sklearn.cross_decomposition.PLSRegression.html)
   提供低成本的多输出监督表示学习，作为小数据/CPU预算下的另一种迁移候选。

研究来源均为原始论文、作者代码/方法和官方文档；未独立复现论文排名或通用最优性。
机制可行性 Confidence: M；跨实验相关性与可用信号已证实，但辅助表选择偏差、
单浓度模型本身的误差及不同测量尺度，仍可能导致负迁移。

## 决策与反证

采用五个有限候选：现有基线、折外单浓度线性迁移、线性迁移加分子残差、固定
半权混合，以及单浓度监督 PLS 表示。均只训练于允许的分子和已测标签，不用
测试结构拟合变换、不用测试标签/榜单选参数。暂不装 GPU/GNN/大预训练模型，
先验证辅助观测是否具有可重复的增益。若冻结确认集不改善 CYP2D6 低活性误差，
或损害高活性/其他终点，则本轮不提交，不能用局部成功替代该反证。

检索预算：Standard TECH，最多 20 个针对性查询；当前主问题已获得方法、代码及
本地数据证据，停止泛搜。检索及源版本快照留在忽略目录 `state/sources/round3/`。
