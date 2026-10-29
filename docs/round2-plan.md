# 第二轮：有限预算的分子特征与区间回归

冻结日期：2026-10-29，训练前登记。用户授权优化、验证、真实提交及 GitHub 同步。

## 诊断与约束

首轮 Ridge 在 seed=42 骨架开发集 MA-ST-RAE=1.005436，未胜中位数参考
0.974824；CYP1A2/2D6 明显较弱。公开榜历史 223/281，今日回读 227/285、
0.928498；第三名 0.376671，不能据此承诺前三。

4,905 分子仅 41 个具有四终点标签；逐终点样本 1412/1285/1493/2335。
官方训练来自命中筛选，测试为类似物扩展且四终点稠密，存在采样差异。
同 revision 的 TDI 表未增加直接抑制标签；Emax/单浓度为其他实验结果，
本轮仅审计，不作输入或伪造 pIC50。主数据 revision 与哈希保持首轮锁定。

## 冻结协议

- 特征：Morgan radius=2/2048 bit；相同配置的 log1p count；RDKit 217 个
  二维理化、拓扑和官能团描述符。特征不读取标签/实验结果/ID。
- 保留原分子表示与原始提交 SMILES；不在此轮更改盐/互变异构/电荷标准化。
- 3 次 80/20 Bemis–Murcko group holdout，seed=42/43/44；canonical identity
  作为无环组。全部是开发切分，seed=42 已用于首轮，不声称独立测试。
- 共 10 个固定候选：median、原 Ridge(alpha=10)、bit-Tanimoto SVR(C=1/10,
  epsilon=.1)、count-Tanimoto SVR(C=10, epsilon=.1)、count 核岭(alpha=1)、
  count 区间 SVR(C=5, epsilon=0)、hybrid ExtraTrees(240 trees, leaf=3,
  max_features=.5)、descriptor HistGradientBoosting(absolute_error, 200 iterations,
  15 leaves, learning_rate=.05, l2=2)、固定 blend(.5 count-SVR + .25 ExtraTrees
  + .25 HistGradientBoosting)。无后续自动扩展搜索。
- 区间 SVR 将训练样本复制为 lower/upper 两端，epsilon=0，样本权重各 .5；
  两端绝对损失之和等于 2×区间外距离加固定区间宽度，与目标区间损失对应。
- 分终点比较 3 次官方 ST-RAE 的算术平均，取最低的非恒定候选。训练只用
  该终点已测标签；模型/插补只拟合各训练分区。blend 固定，不拟合权重。
- 提交门槛：相对原 Ridge 的三切分宏平均改善至少 5%，并胜 median 参考；
  750 行、身份、有限性、每列 std>=.01、本地和官方 validator 全通过。
- 达标后仅全量拟合选中候选/ensemble 成员一次；生成新目录，保留首轮。
- 本机 CPU、最多 2 个计算线程；目标总训练小于 30 分钟、峰值 RSS <4 GiB，
  不使用付费资源。任何预算中止留证据，不临时缩小模型后假称原协议完成。
- 公榜只读作排名差距与提交状态，不用于候选/权重选择；仅作一次新提交。
- 提交前复核最新而非历史最好条目、12h 限制、表单、报告及开源披露。

## 执行与验收

新增独立 features/optimization 模块与 CLI optimize；单元测试覆盖化学等价、
区间损失、核边界、缺失标签、分区隔离和预算/选型门槛。运行项目 pytest、
Ruff lint/format、mypy、wheel 及安装 smoke；实际训练记录耗时、版本、源码/
锁/数据/分区/预测哈希和逐终点指标，报告验证与盲测的区别。模型验证达标后
发布版本化方法报告，单次上传、保留回执、回读评分并同步 GitHub。

## 路由与工程规则

已读 Skill：brainstorming、writing-plans、executing-plans、test-driven-development
及 testing-anti-patterns、finishing-a-development-branch、git-workflow、
verification-before-completion。规则：engineering-workflow、python/code-style、
python/data-runtime、shared-code-change-safety、anti-hallucination；根级 AGENTS
为 adequate，无需补写。索引 audit 通过；manifest 扫描忽略目录时误识别附带 JS，
本轮实际涉及仅 Python，不改第三方/缓存 JS。新代码 @author cylovelife。

不加载：深度调研/论文写作（此次为现有竞赛实验）、worktree（当前干净且无并发
任务）、付费云/公司 GitLab（不涉及）。不委派共享状态与连续模型决策。
