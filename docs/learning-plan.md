# AIDD 学习实践：分子体检与 ESOL

2026-11-02。用户授权按产物推进、结合代码/实验讲解并同步GitHub。当前主线仅为
分子体检工具和ESOL，不重开CYP比赛实验，也不替换已保留的最佳提交。

## 学习与验收方式

每课按照「先预测现象→运行短实验→对照代码解释→改一个条件→记录结论」推进。
Agent实现/测试通过仅属于工程验收；学习者能独立解释、修改和复现才属于学习验收。
两类状态分开记录，不由自动测试或Agent代答推定个人已掌握。

| 步骤 | 需要补的知识/实践 | 工程验收 | 学习验收 | 状态 |
|---|---|---|---|---|
| L01 分子体检 | SMILES→图；隐式H；式量、logP、HBD/HBA、TPSA；电荷/盐 | 20条示例，结构图/数值/错误清单，非法结构显式报告；原输入不变 | 手工解释乙醇、乙醚、乙酸/乙酸根及手性例子；回答第一课问题 | 工程已实跑；个人待验收 |
| L02 表示与检索 | Morgan半径/位长、Tanimoto、手性和碰撞；同一结构去重 | 近邻排除自身/同一规范身份；固定配置，可复现排序 | 修改手性开关，说明相似度变化及其局限；解释5个分子的近邻 | 工具及消融已实跑；个人待验收 |
| L03 ESOL数据审计 | logS单位；SMILES唯一性；标签与特征边界 | 锁定来源revision/SHA；核对1128条预期、非法/重复/缺失/冲突；仅SMILES作模型输入 | 手算logS对应浓度；能指出哪些列不能直接作为输入 | 待执行 |
| L04 ESOL简单基线 | 均值参考、Ridge、树、核SVR；训练专用变换 | 在拟合前保存下面的划分/预算；同分子不跨集合；基线和候选共用身份 | 独立说明损失、维度、正则和预处理为何只拟合训练集 | 待执行 |
| L05 验证与诊断 | 随机/骨架泛化；MAE/RMSE；结构适用域 | 固定测试最后评估；保留预测、耗时、失败及10个错误案例 | 解释两类划分差异，提出一个有依据的后续假设 | 待执行 |
| L06 学习交付 | 复现、实验报告、用途/限制 | 新环境复现说明与GitHub版本可查；数据/模型留state | 无现成答案，重做一个小实验并讲清结果 | 待执行 |

每课的讲义和本地实测见docs/learning/；个人答案另存answers.md，不预先勾选通过。
有问题可以回到上一课；不靠增加候选来跳过未理解的知识。

## 分子体检实现约定

新模块和独立脚本复用当前RDKit/NumPy，不修改CYP的特征、划分或模型代码。
教学输入为20条手工构造结构示例，保存在examples/learning/molecules.json，
不是实验活性或药效数据。输出放state/learning/下的新目录，拒绝覆盖旧输出。
保留原始字符串；canonical isomeric SMILES仅统一本版本下的表示，不去盐、不
中和、不合并互变异构体。描述符针对完整输入图；多片段会明确提示。
Morgan默认radius2、2048bits、includeChirality=False；允许显式打开手性。
指纹用于结构近邻，不视为唯一身份，也不据此断言活性或安全性。
网页报告为本地静态HTML/结构图，不联网、不训练、不调用外部服务。

## ESOL拟合前协议草案

本表先固定比较范围；下载审计完成后锁定具体源码revision、文件SHA和逐行划分，
写入docs/learning/esol-protocol.json，再允许首次拟合。若数据不满足预期，先报告
问题并作显式修订，不在看模型分数之后修改协议。

- 任务：单终点水溶解度，目标为measured log solubility（log10 mol/L）。来源用
  DeepChem维护的Delaney/ESOL；直接读取数据，不为教程安装整个DeepChem框架。
- 输入仅SMILES推导的结构特征；排除名称、目标和既有模型预测列。原始下载不可变。
- 先按带手性的规范结构审计重复。标签冲突保持可追踪，在拟合前记录去重策略。
- 两套预登记划分：按分子身份分组的随机切分，以及骨架切分；各约60/20/20，
  seed42，组大小造成的比例偏差如实报告。无环结构按规范身份分组；不称其为独立
  化学骨架。两套测试分别封存，不挑其中更漂亮的结果。
- 四个固定候选：训练均值；六项描述符+StandardScaler/Ridge(alpha=1)；
  Morgan2048/radius2+RandomForest(300树,min_samples_leaf=2)；
  Morgan位指纹Tanimoto核SVR(C=1,epsilon=0.1)。描述符为MolWt/MolLogP/HBD/HBA/
  TPSA/可旋转键数；所有候选的特征与参数在数据审计后锁定，不网格搜索。
- 两套划分共8个开发候选评估；RF固定seed17；CPU最多2线程，整个首次基线
  runner最多600秒/2GiB。先在开发训练样本上做不选型的资源探针，再锁定协议。
- 主指标MAE，辅指标RMSE；只用验证集选模型。每套选定模型及均值参考各进行一次
  最终测试评估；保留其他候选的开发结果。测试后不回头调参或重选模型。
- 记录原标签量纲下误差、残差、最近训练结构相似度、极端预测、耗时与失败。至少
  手工检查10个案例；随机和骨架分数代表不同问题，不把它们当独立重复样本算显著性。
- 即使未超过某个模型，也可以完成一次合格对照；若连均值参考都无法超过，应先
  检查代码、标签和任务，再解释结论。不预设跨划分通用的高分门槛。

## 交付与边界

每个可复现学习节点提交并推送GitHub工作分支；原始ESOL、预测、运行报告和模型
继续留state，仅跟踪源码、讲义、必要摘要及哈希。手工教学结构列表可随代码共享。
不启用付费资源，不自动发布HF应用或参加新比赛。CYP预测和原回执保持原样。

## 路由、规则和验证清单

本阶段：writing-plans、executing-plans、test-driven-development（含testing anti-patterns）、
git-workflow、finishing-a-development-branch、verification-before-completion。
ESOL协议参考agentic-kaggle-skill的cross-validation-and-metrics与information-sharing-policy；
当前尚不拟合sklearn Pipeline，后续实现时按索引加载scikit-learn入口。无子Agent。
已读AGENTS、skills-index、engineering-workflow、python/code-style、python/data-runtime、
anti-hallucination。当前Harness为adequate；补充学习工作流入口，不改已有研究约束。
代码测试使用pytest；项目必要门禁为Ruff check/format、mypy、构建和git diff --check。
教学报告另做实际运行、结构图/数值和输出保护检查。验证记录随课更新。

来源：[RDKit入门](https://www.rdkit.org/docs/GettingStartedInPython.html)、
[ESOL数据说明](https://deepchem.readthedocs.io/en/latest/api_reference/moleculenet.html#delaney-datasets)。
