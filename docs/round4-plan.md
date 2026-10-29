# 第四轮冻结方案：实验条件分离的 CYP2D6 外部低活性迁移

登记：2026-10-29，任何本轮模型拟合之前。目标是检验公开低活性观测是否提供可迁移信号，
不是以外部实验标签冒充赛事真值；无可信改善不提交。现有预算：CPU 2线程、RSS 4 GiB、
一次模型实验最多1800秒；采集/清洗单独计时，无付费/GPU/大型新依赖。

## 从机制到可证伪假设

预测对象是给定实验条件下的直接抑制 pIC50，而非蛋白结合自由能。简化竞争抑制中
IC50=Ki(1+[S]/Km)，仅在快速平衡、竞争模式等前提成立时适用；本轮不对未知条件作
Ki换算。MD/对接可提供构象和相互作用线索，但不能补足底物、浓度、预孵育、读出和
低活性测量缺口；在当前预算下优先保留这些差异，检验数据迁移。

H1：公开非命中观测学到的结构信号，经赛事训练折内校准，可减少CYP2D6低层过预测，
同时保持高层和总体误差。反解释：不同底物/读出导致负迁移，或收益仅来自重新校准。
用相同校准器去掉外部信号的对照分辨这两种情况。不宣称方法是新算法或已具备前三能力。

## 数据准入（先审计，后拟合）

1. PubChem/NCATS AID891全量qHTS；保留SID/CID、原SMILES、phenotype、outcome、
   曲线质量与原单位。仅明确inactive→辅助类别0；明确inhibitor且Active→类别1。
   activator/inconclusive、冲突重复和无结构不进入分类；AC50与inactive均不赋精确pIC50。
   AID1851为多酶panel，汇总outcome不是CYP2D6标签，本轮只审计元数据，不重叠计数。
2. ChEMBL37 CHEMBL289、人源IC50；保留activity/assay/document ID、说明、单位、
   relation、validity、duplicate标记。只准入standard_flag=1、nM、有限正值、无异常
   validity、非potential_duplicate、说明明确inhibition且非TDI/代谢稳定性。
   `=`、`>`、`>=`、`<`、`<=`保持语义；pIC50=9-log10(nM)，不等号反向。
   仅在界限足以判断时生成独立辅助阈值类别（pIC50>=5），未知者保持缺失。
   exact pIC50<4与上界<=4单列审计。不同assay不合并为同一实验，不直接池化赛事回归。
3. 泄漏键：RDKit fragment parent、去电荷、规范互变异构体、忽略立体化学；仅作保守
   去重/排除，不改赛事提交SMILES。外部训练全局排除全部官方训练/辅助/盲测的该键，
   并排除所有官方训练/确认/盲测骨架。强于逐折排除；不借重叠化合物的外部标签。
   同来源同parent类别冲突整组排除；ChEMBL内跨assay冲突排除，不把两个数据库当独立复现。
4. raw文件逐项SHA256，原文件与失败证据不覆盖；所有活动行/缓存留在state/。
   文档仅必要汇总与哈希。ChEMBL数据CC BY-SA 3.0；NCATS/PubChem保留出处和原记录政策。

## 验证与有限候选

保留第三轮seed31415的963分子确认分区及其原哈希；开发仍为seed73/74骨架切分及
原类似物扩展切分。新保守parent若跨折，训练侧排除所有验证parent；确认parent在全部
开发训练中排除。保存额外排除计数，不能声称旧分区是历史完全未见。

辅助分类器固定LogisticRegression(C=1, solver=liblinear, max_iter=500)，Morgan bits；
每来源独立输出logit，类权重balanced。外部来源自身80/20骨架留出seed5151，报告
AUROC/balanced accuracy；不据该结果调参，再以全部允许外部观测重训。

CYP2D6四个候选（其他三终点保持第二轮模型）：

- baseline：原bit-Tanimoto SVR(C=1)。
- calibration_control：以三折GroupKFold的baseline折外预测、8个二维理化描述符
  （MolWt/MolLogP/TPSA/NumHDonors/NumHAcceptors/NumRotatableBonds/RingCount/FractionCSP3）
  拟合StandardScaler+Ridge(alpha=10)；仅当前训练折真实直接标签。
- external_calibration：同一校准器，另加两个来源的预测logit；不输入外部实测值。
- external_blend：baseline与external_calibration固定各0.5。

不扩大候选、不根据公榜或测试预测活性率校准。不同来源分类含义不同，logit不是
可互换活性概率，最终映射仅从赛事训练标签学习。低活性仍以真实pIC50<4分层。

## 选型、确认和提交

开发集沿用第三轮门槛：CYP2D6平均ST-RAE改善>=3%、低层距离改善>=10%、高层恶化<=5%；
外部候选还须ST-RAE优于calibration_control，避免把纯校准收益当外部数据收益。
三个切分至少两个总体改善，所有分层须非空；否则保留baseline，不打开确认集。
通过才一次性确认：宏平均改善>=5%、2D6 ST-RAE改善>=5%、低层改善>=10%、高层恶化<=5%、
其他终点恶化<=5%、各终点>=100标签、2D6低层>=20，1000次配对骨架bootstrap宏差95%上界<0。
任何未达标不生成新regression.csv、不上传。确认若parent清洗后数量不足，记证据不足。
全部通过才全量重训、官方validator校验、更新公开方法、复核最新提交和12h限流后上传。

## 实施与路由

新增external_data/external_transfer和独立CLI入口，不改原三轮行为；测试删失方向、panel
误用防护、salt/tautomer去重、冲突标签、外部与官方排除、折内拟合及真实门槛。
运行pytest、Ruff、mypy、wheel安装smoke、路由审计、git diff --check。Harness adequate。

实际已加载：deep-research及TECH/evidence/output引用、brainstorming、writing-plans、
executing-plans、test-driven-development及testing-anti-patterns、using-git-worktrees（核对
后当前checkout干净且无并发任务，以codex/cyp-round4分支隔离）、verification-before-completion。
规则：engineering-workflow、python/code-style、python/data-runtime、research/deep-research、
anti-hallucination、shared-code-change-safety。Git收尾时再加载git-workflow与finishing。
未加载：Java/TS/Rust、公司DB/GitLab、论文写作、MD工具；不涉及这些边界。不委派Agent。

### 拟合前身份实现核验

枚举式互变异构体规范化在复杂官方分子触及上限，失败审计保留，未进行模型拟合。
最终父体键：fragment parent→uncharger→严格sanitize→去立体→RDKit HetAtomTautomerv2。
骨架键：在父体副本中保留元素与形式电荷、将键转为单键并清除芳香/H缓存后严格sanitize，
再取Murcko。这样避免酮/烯醇外环双键差异，也保留季铵氮的必要正电荷；它可能额外合并
骨架，属于保守排除。键只作审计，不作真实物理结构或模型特征，不声称涵盖一切化学等价。
RDKit版本锁定；9项相关回归测试和全部5656个官方结构的键计算通过后才运行最终审计。
该修订在模型拟合前完成，不改候选、预算、确认分区和门槛；加载systematic-debugging。
