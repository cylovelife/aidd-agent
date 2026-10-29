# CYP抑制预测的本质与第四轮创新假设

日期：2026-10-29。判断：当前最值得投入的是实验条件感知的数据迁移、删失标签处理与
选择偏差验证；分子动力学不是本轮前置条件。它有物理化学本质，也需要统计学习，
不能把“生物问题”直接等同于“必须先跑MD”。Confidence: M，测量机制明确，创新收益待实测。

## 我们实际预测什么

观测可写成 `y = assay(molecule, enzyme, substrate, concentrations, preincubation,
readout, curve_fit) + uncertainty`。分子结构决定相互作用的一部分，实验条件决定
这些作用怎样变成一个pIC50。经典快速平衡竞争抑制在适用前提下满足
`IC50 = Ki * (1 + [S]/Km)`；这已经说明同一抑制剂不能跨底物条件无脑合并IC50。
不明机制、非平衡、紧密结合、部分/混合抑制需要其他模型，不能机械套公式。
依据：[Cheng与Prusoff原论文](https://doi.org/10.1016/0006-2952(73)90196-2)、
[NCI转换器的模型与假设](https://bioinfo.abcc.ncifcrf.gov/IC50_Ki_Converter/index.php)。
Confidence: H，原理论及其明确适用前提，不据此推断本赛事全部化合物都是竞争抑制。

[赛事实验说明](https://openadmet.ghost.io/announcing-openadmets-cyp-inhibition-blind-challenge/)
说明CYP2D6使用右美沙芬底物与Echo-MS母体消耗读出；其他三个酶使用荧光探针。
直接与TDI条件通过预孵育时是否加入NADPH区分；**全库单浓度初筛是TDI条件**。
第三轮把它当独立辅助任务的隔离是必要的，本轮进一步明确这个条件，绝不将弱响应
直接解释为已知直接抑制pIC50。训练只对筛选命中扩展DRC；盲测来自另外三个酶的
强命中类似物，并对四酶稠密测量。[数据生产细节](https://openadmet.github.io/octant-cyp-inhib-blog-post/)
也指出探针、实验效应和tiering的设计取舍。Confidence: H，主办方原始方法证据。

## MD、物理模型与数据模型各自解决什么

- 二维统计模型：以已测分子和分子表示学习给定实验下的经验SAR；成本低，适合先检验
  数据、损失和验证是否正确。不能从没有真值的化学空间证明校准正确。
- 酶动力学/观测模型：约束IC50、底物条件、最大效应、曲线斜率、删失和不确定性的解释。
  这是本轮必须遵守的物理边界，但不等于需要全原子模拟。
- 对接/MD/自由能：可生成构象、相互作用、质子化/血红素配位等候选解释；要支持定量
  结果还需可信结构、参数、采样与适用化学系列的实验验证。把一个对接能量直接当
  pIC50会遗漏底物竞争与读出条件。当前缺口是低活性真实测量，而非已定位的构象采样失败；
  在现有2线程预算下不优先启动MD。此优先级是工程/研究判断，不是“MD无用”的实测结论。

## 公开数据的准入与来源差异

[PubChem AID891](https://pubchem.ncbi.nlm.nih.gov/bioassay/891)是NCATS人CYP2D6 qHTS，
Luciferin-ME EGE约30µM（记录称在Km）、CYP2D6约5nM、室温反应60分钟，发光读出。
明确有inactive记录，但也测到activator/inconclusive；抑制和部分底物竞争都会降低信号。
[检测酶干扰说明](https://www.ncbi.nlm.nih.gov/books/NBK374281/)指出luciferase检测存在
报告酶干扰风险；本轮没有取得配套反筛来逐分子排除它，因此只把该源作为辅助任务。
[AID1851](https://pubchem.ncbi.nlm.nih.gov/bioassay/1851/)是多CYP panel，整体outcome不能
充当2D6标签，且与早期qHTS有来源关联；本轮不叠加它的活动行。
Confidence: H，原始JSON协议和逐行字段已归档；对赛事迁移能力仍未知。

[ChEMBL37 CHEMBL289](https://www.ebi.ac.uk/chembl/explore/target/CHEMBL289)的IC50查询
含不同论文、底物、酶来源和实验格式，不是一个可直接合并的统一实验。`IC50 > 100µM`
对应`pIC50 < 4`，仅为源实验的上界；`pChEMBL_value`缺失不能当无活性，也不能只取
有pChEMBL值的行，否则会丢掉大量删失弱活性。保留原关系、单位和assay/document ID，
排除异常、潜在重复与说明中明确TDI/预孵育的记录；条件未报告的仍标未知，不能声称
逐行已完全对齐。ChEMBL数据使用[CC BY-SA 3.0](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions)；
PubChem参照[NCBI政策](https://www.ncbi.nlm.nih.gov/home/about/policies/)并保留NCATS来源，
不把所有贡献者内容一概声称为无版权。原始与派生数据留在state，不随MIT代码发布。

## 创新应落在哪里

第一层是测量科学：把source/assay/substrate/删失语义变成数据契约；第二层是学习方法：
只迁移结构信号，由本域真实标签校准，保留相同校准器的无外部对照；第三层是证据设计：
低/高活性、骨架外推与类似物扩展都检查，先开发后确认，失败也保留。
这是可证伪的研究方向，尚不够称为算法创新或论文贡献。真正的新增贡献须由同预算
消融、跨实验/化学系列复现和可信改善支持，不能由模型复杂度或前三目标替代。

最薄弱的三个假设是：外部inactive与赛事低活性有足够相关性、外部结构域能覆盖赛事
弱活性空间、现有少量低层验证足以区分校准收益和负迁移。对应反证是外部分类可预测
但赛事低层/总体仍不改善、外部增益不超过无外部校准对照、或确认集门槛失败。
具体预算、排除和停止规则见[冻结方案](round4-plan.md)，实测结论以第四轮结果为准。

研究范围：Standard TECH，原始论文/官方方法、原始数据库和本机实测优先；未读取
其他参赛者预测、权重或私有数据；公榜不参与选型。下载来源与响应哈希在
`state/sources/round4/manifest.json`和`state/data/cyp2d6-public/manifest.json`。

### 质量标记审计补充

ChEMBL原始IC50查询的79条精确pIC50<4记录全部带`Outside typical range`，来自26份
文献/专利记录。该标记**不是已证实错误**：[ChEMBL官方说明](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions)
说明它是范围检查，保留与否由使用者判断。本轮严格数据门槛将它们隔离，不能据此宣称
公开库没有真实低活性值。已归档完整79行和26份document/DOI映射；需要原文/SI逐项
确认单位、最高测试浓度、曲线外推及直接/TDI条件后，才可解除隔离。
例如[2020原论文及SI入口](https://pubs.acs.org/doi/10.1021/acs.jmedchem.0c00101)
对应的ChEMBL记录同时含直接和NADPH预孵育的CYP2D6测量，不能混用；本轮未对全文
及原曲线作完整复核，因此不恢复其精确值。保留这类隔离本身可能损失真正弱活性证据，
属于本轮明确限制，不通过悄悄放宽质量规则补充标签。Confidence: H（字段和出处已查），
原始数值真实性仍未验证。
