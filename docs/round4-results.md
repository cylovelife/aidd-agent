# 第四轮：公开CYP2D6低活性数据审计与迁移结果

**不提交。** 本轮公开数据确实补充了弱活性/不活跃辅助观测，但固定方案没有获得
达到门槛的赛事本域改善。确认集仍封存，未生成盲测CSV，未调用上传。第二轮有效
提交保持原状；不把本轮开发集结果当成新的官方成绩或接近前三的证明。

## 第一性原理判断

问题是“给定实验条件下的抑制活性与测量过程”的预测，有物理化学基础，但当前
最主要缺口是标签选择与跨实验条件差异。酶动力学知识必须约束数据解释；全原子MD
不是本轮前置条件，无法直接产生缺失的低活性实验真值。优先创新方向是条件感知的
数据契约、删失监督、域内校准及可证伪验证，而非先增加模型复杂度。
机制、来源和适用边界详见[研究记录](round4-research.md)，执行规则见[冻结方案](round4-plan.md)。

## 数据审计：补到了什么，没有补到什么

来源：NCATS/PubChem [AID891](https://pubchem.ncbi.nlm.nih.gov/bioassay/891)及
[ChEMBL37 CHEMBL289](https://www.ebi.ac.uk/chembl/explore/target/CHEMBL289)。

| 项目 | PubChem AID891 | ChEMBL37 IC50 |
|---|---:|---:|
| 原始活动记录 | 10,320 | 8,684 |
| 语义及结构准入后记录 | 8,408 | 6,176 |
| 官方重叠/冲突排除、源内父体去重后 | 5,674 | 5,062 |
| 辅助类别0 | 4,511（明确inactive） | 3,649（足以判断pIC50<5） |
| 辅助类别1 | 1,163（明确active inhibitor） | 1,413（足以判断pIC50>=5） |

两来源类别含义不同，各训练一个辅助分类器，不把它们当同一个实验，也不将logit
当成可互换的概率。共10,736条源内去重任务记录、跨源10,696个父体；不把跨数据库
重叠算独立复现。全部官方训练/辅助/确认/盲测父体与保守骨架全局排除，命中父体
380条、骨架2386条（两个计数有交集），另剔除105组源内类别冲突。

AID891原始有175条outcome=Inactive但phenotype=Activator，全部隔离；还有1722条
Inconclusive inhibitor也不转负例。没有将inactive或缺失AC50填成0或pIC50=4。
该源使用Luciferin-ME EGE/发光，与赛事右美沙芬/Echo-MS不同；报告酶干扰未被逐分子
反筛排除。ChEMBL保留assay/document、原单位和不等号，排除明确TDI、质量标记、
潜在重复；未知条件仍未知，没有声称逐行测量完全对齐。

ChEMBL语义准入后有**257条源实验pIC50上界<=4**，全局排除和去重后保留**227条**。
这是删失弱活性证据，不是227个精确赛事标签。原始79条精确pIC50<4来自26份文献/专利，
全部带Outside typical range；本轮严格门槛隔离，但该标记不等于已证实错误。
已保存79行与26份document/DOI映射，未完成逐篇原文/SI/最高浓度与曲线外推核验。
因此“本轮无未标记精确低活性准入”不能写成“公开库没有真实精确低活性”。

## 实验与消融

固定两个来源的Morgan bits逻辑回归；分别作seed5151骨架留出，然后全允许数据重训。
源内AUROC为0.8648（PubChem）、0.8218（ChEMBL），balanced accuracy为0.7599/0.7346。
这些说明来源自身的结构信号可学习，不能证明跨到底物不同的赛事数据仍然可用。

赛事四候选只改变CYP2D6；三个开发切分沿用第三轮，另外三终点保持原冻结模型。
基线折外预测通过内层GroupKFold生成，标准化和校准仅拟合当前训练折的真实赛事标签。

| CYP2D6，三开发切分平均 | ST-RAE↓ | 低层区间外距离↓ | 高层区间外距离↓ |
|---|---:|---:|---:|
| baseline | 0.932629 | 0.804857 | 0.362003 |
| 相同校准器，无外部信号 | 0.939566 | 0.637837 | 0.383850 |
| 外部信号＋域内校准 | 0.941017 | 0.632012 | 0.384838 |
| baseline/外部校准各半 | 0.920486 | 0.713466 | 0.366167 |

固定半权混合总体改善**1.30%**、低层改善**11.35%**、高层恶化**1.15%**；三个切分
均小幅总体改善，但未达预登记>=3%的总体门槛。完整外部校准相对无外部校准对照
总体略差，不能把20%量级的低层改善全部归因于外部数据。

门槛判定后，另以已保存预测计算“baseline/无外部校准各半”的固定消融，不新增拟合、
不改候选或判定：其平均ST-RAE=0.922873。外部混合0.920486相对仅改善约0.26%，
未建立稳健的外部数据增益。该消融是开发后诊断，不充当独立确认试验。
结构化汇总及哈希见[round4-result.json](round4-result.json)。

确认集963分子、seed31415，CSV SHA256仍为
`f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a`。
本轮未打开，因此没有确认bootstrap通过、没有可信盲测提升的声明。开发低层样本数
仅17/19/31，切分存在复用，跨条件外推仍不确定。

## 资源、复现与验证

最终数据审计21.94秒；模型实验8.15秒、峰值RSS 912,162,816 bytes（约0.85 GiB），
CPU最多2线程，无付费资源/GPU/新依赖。此前身份清洗失败均在拟合前，保留日志，
最终解决枚举截断、季铵氮及酮/烯醇骨架键问题；不是研究候选搜索或额外模型轮次。

```bash
uv sync --frozen
uv run python scripts/fetch_cyp2d6.py --output-dir state/data/cyp2d6-public
uv run aidd audit-external --output-dir state/runs/my-round4-audit
uv run aidd external --audit-dir state/runs/my-round4-audit --output-dir state/runs/my-round4
```

下载器锁定[源哈希](round4-sources-lock.json)，现有目录拒绝覆盖；源变化则保留证据并
明确失败，不悄悄接受新版本。原始数据、逐分子预测、源内切分/排除轨迹、缓存留在state。
正式输出为`state/runs/20261029-round4-audit-05/`、`state/runs/20261029-round4-01/`。

工程Harness adequate，无原模块语义变更；CLI增加audit-external/external。
39项pytest（含optional neural原有回归）通过，Ruff lint/format、mypy通过。
wheel构建与隔离安装后的真实分子身份计算/四候选拟合smoke通过；不是官方上传验收。
源哈希、数据排除和最终版本核验见本轮结构化证据；不声明远程CI或部署。
最终下载器在新目录重新下载33个原始文件，逐项SHA256与锁一致；最终代码/计划/依赖
哈希与实验protocol一致。复核外部对官方父体/骨架重叠均为0，开发训练/验证与确认集
交叉为0。见[完成核验](round4-verification.json)。原始ChEMBL准入记录没有已声明的
assay_variant_mutation/accession，但这不能填补未报告的底物/浓度条件。

实际Skill：deep-research（TECH/evidence/output引用）、brainstorming、writing-plans、
executing-plans、test-driven-development（含testing-anti-patterns）、using-git-worktrees
（评估后使用干净checkout内工作分支）、systematic-debugging、git-workflow、
finishing-a-development-branch、verification-before-completion。
实际规则：engineering-workflow、python/code-style、python/data-runtime、research/deep-research、
anti-hallucination、shared-code-change-safety；已读索引及项目AGENTS。未使用子Agent、
公司DB/GitLab、MD/付费云、其他参赛者模型/预测。GitHub使用已核对的个人身份与SSH路由。

## 后续科学路径

优先逐篇解除79条精确低活性记录的隔离，尤其明确右美沙芬/直接抑制的原文/SI；这可能
补充校准证据，但仅26份出处且存在重复/TDI/原曲线未知，不能保证最终有效数量。
第二个方向是按assay/substrate分层的删失监督与域差异不确定性，需匹配的消融和留实验/
留化学系列验证；不能将本轮两个简单来源分类器的失败推广为外部数据无用。

本轮证据支持停止上传和保留确认集，不支持扩大同一开发集超参搜索。前三是目标，
不是可证明的当前成功概率；下一项实验必须由新数据核验或新机制假设触发。
