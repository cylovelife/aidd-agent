# 第七轮：指纹消融与冻结预训练表示

2026-11-01。**实验完成，开发门槛未通过，不提交。** 未评估963分子确认集，
未生成新的盲测CSV；未调用官方上传或榜单查询，第二轮提交没有被本轮替换。

## 固定条件与结果

[拟合前方案](round7-plan.md)固定了五个候选、三个开发切分、模型超参及门槛。
仅官方直接标签监督，缺失不填零。保持原确认分区哈希；开发3943分子，
scaffold73/74和analog expansion均为复用开发集，不能称独立盲测。
两个骨架切分骨架交叉0；类似物压力切分按设计共享32个骨架、保留训练锚点。
各切分精确分子交叉0，开发训练和评估均不含确认分子。

下表为三个开发切分均值，ST-RAE越小越好；宏平均再对四终点等权平均。
本轮基线用第二轮固定模型在本轮分区重训；不能将0.770835与第二轮不同分区的
0.735632或官方0.920131直接比较。完整数值、相似度分层及产物哈希见
[结构化结果](round7-result.json)。

| 表示/方案 | 四终点宏ST-RAE | CYP2D6 ST-RAE | CYP2D6低层区间距离 |
|---|---:|---:|---:|
| 原表示/固定模型基线 | 0.770835 | 0.932629 | 0.804857 |
| radius2 + 手性 | 0.770482 | 0.933710 | 0.801249 |
| radius3 | 0.778967 | 0.927327 | 0.810125 |
| Feature Morgan | 0.773812 | 0.894788 | 0.772789 |
| 冻结CheMeleon + StandardScaler/Ridge | 2.184158 | 2.282228 | 1.050976 |

手性宏改善约0.046%，未达到任何终点准入门槛。radius3宏指标退步。
Feature Morgan在2D6总体改善约4.06%、低层约3.98%，未达到低层>=10%的
预设门槛；2C9退步。不能看到总体小改善后放宽低层条件。最终四终点均保留baseline，
开发组合门槛未通过，确认保持封存。第一终点使用纯描述符，三个指纹变体的1A2
预测逐值相同，是预定负对照。

CheMeleon对照显著退步。该候选同时引入冻结图表示与固定Ridge读出头，与现有
终点集成不是纯单因素模型比较；结果只否定这一个固定组合，不能归因于所有
预训练模型或所有图网络。没有根据开发结果调Ridge正则、微调编码器或追加候选。
检查真实权重严格加载、2048维/有限性、行顺序与小批次编码一致性，未以随机权重代替。

## 预训练来源、运行时与可得性

[CheMeleon官方教程](https://chemprop.readthedocs.io/en/main/chemeleon_foundation_finetuning.html)
和[Zenodo v2权重](https://zenodo.org/records/15460715)；来源及SHA256见
[来源锁](round7-sources-lock.json)。官方MD5吻合，Zenodo metadata及上游代码为MIT。
本轮仅下载和本地编码，没有上传分子或重新分发权重。结构/描述符预训练的逐分子
重叠未审计，可能包括赛事已有结构；不声称预训练语料与赛事全量无交叉。

Chemprop2.3.1初始解析要求RDKit降级，拟合前改用2.2.1并锁回原RDKit2026.9.1。
仅增加可选representation依赖组；基线特征运行时及217描述符注册表保持原版本。
编码器冻结eval、CPU两线程、均值聚合，所有标准化和Ridge仅拟合当前训练标签。
指纹模型保持原终点模型/集成权重。单次运行指纹提取/拟合239.390秒，预训练
编码/拟合30.846秒，总约270.24秒；峰值RSS2,420,146,176bytes（约2.25GiB）。
未用GPU或付费资源；时间不含下载、安装、开发与验证。

## 验证和复现

- 52项pytest通过；普通、neural、representation组均检查。新增真实手性区分、
  保持描述符不变、非法结构/变体、fit-only标签隔离、门槛失败、原目录/缺权重拒绝。
- Ruff check/format、mypy21源文件通过；wheel/sdist构建及CLI help通过。
- 60行开发评估的ST-RAE/MAE/低高层距离从保存逐分子预测独立复算，最大误差
  `8.881784197001252e-16`；预测身份顺序、分区/确认排除检查通过。
- 运行协议的全部src源码、uv.lock和方案SHA256与最终实现吻合；确认分区与第三轮
  原SHA256相同，无confirmation-opened标记、无regression.csv。
- 相似度分层固定为<0.4、[0.4,0.6)、>=0.6，统计各终点样本数与区间外距离，
  仅作诊断，不追加选型。不能由稀少弱活性标签证明目标区域已校准。

```bash
uv sync --frozen --group representation
uv run --group representation aidd representation \
  --weights state/sources/round7/chemeleon_mp.pt \
  --output-dir state/runs/my-round7-run
uv run --group representation python scripts/summarize_round7.py \
  state/runs/20261101-round7-01 --output state/recomputed-round7.json
```

下载权重链接及校验和以来源锁为准；权重放ignored state，已有实验目录拒绝覆盖。
复现只使用封存分区的身份而不评估其标签；若未来开发通过，runner核查已有确认打开
标记，只允许选定一个组合确认。确认通过是全量拟合/官方校验的交接点，研究runner
本身不会上传。

代码、冻结方案、来源和正负结果同步GitHub；原始数据、权重、向量及逐分子预测留state。
未执行新官方提交/validator/实时规则复核，因为开发门槛已经失败；软件检查不冒充
官方评分。后续若继续，应针对新证据或明确的新机制假设登记实验，不能重复追逐本轮
开发集或通过更改门槛消耗确认集。

实际路由/规则清单见方案。Harness adequate，仅补AGENTS本轮入口；没有修改历史
特征或模型函数行为。GitHub使用个人foxmail提交身份和专用SSH key。
