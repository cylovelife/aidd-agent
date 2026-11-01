# 第八轮：CheMeleon读出头失效诊断与有限对照

2026-11-01。**找到了原头失效的可干预因素，但新头仍未超过现有基线，不提交。**
确认分区、验证和提交门槛未改变；963分子确认集未评估，没有盲测CSV或平台上传。
第二轮有效提交未被本轮替换。未用公榜选型，未执行无门槛依据的追加微调。

## 诊断证据

[诊断方案](round8-diagnostic-plan.md)先于原头复现；[12组诊断记录](round8-diagnostic-result.json)
覆盖三开发切分、四终点，未新增选型候选。使用第七轮相同2048维冻结向量：
数组有限、范围0–2.066893，113维全零。缓存向量/元数据、SMILES顺序、权重及依赖
哈希通过；逐终点重现原StandardScaler+Ridge(alpha10,lsqr)预测误差<1e-9。
本会话第七轮还已验证真实权重严格加载及小批次编码逐值一致，本轮复用其证据。
这些检查不支持“缓存错位或随机权重导致退步”的解释，但不是对所有模型实现的形式证明。

原头每个终点只有817–1528个fit标签，却拟合2048个输入维度。训练RMSE仅
0.039–0.135，验证RMSE0.973–10.117。训练绝对标准化幅度约29–39，而验证最大值
247–4644；训练折极少激活/低方差维度在新分子上激活时可被严重放大。
在有真实标签的验证分子中，预测最低-43.81、最高103.20，明显超出对应训练标签范围。
这同时体现高维小样本的拟合过度和标准化后的外推不稳定。原始向量自身没有数千倍幅度。
训练/验证差距并不能独自证明原因，故随后使用受控干预检验，而非直接宣布编码器无效。

## 依据诊断冻结的新头

[新头方案](round8-plan.md)在诊断后、新候选拟合前固定；无网格搜索或结果后追加。
编码器、向量、样本分区不变，所有StandardScaler仅在对应fit真实标签行拟合：

| 头 | 标准化后输入 | Ridge alpha | 宏开发ST-RAE↓ |
|---|---|---:|---:|
| replay原头 | 不截断 | 10 | 2.184158 |
| ridge1000 | 不截断 | 1000 | 0.986025 |
| clip5_ridge10 | fit与query均限制[-5,5] | 10 | 1.486926 |
| clip5_ridge1000 | fit与query均限制[-5,5] | 1000 | 0.816015 |
| 当前提交模型重训基线 | 原指纹/描述符、原固定模型 | 原方案 | 0.770835 |

这里截断的是模型输入，不是预测或标签。四种读出头形成2x2对照，三个新候选。
加强正则单独有效，限制极端输入单独也有效，两者组合较原头ST-RAE下降62.64%。
全部查询（含该终点缺失标签行）的组合头预测范围为0.690–7.576；原头同口径为
-58.498–163.249，不与上文仅有标签分子的范围混用。
平均训练RMSE由0.081升到0.548、平均系数L2由1.658降到0.340，符合减少拟合自由度
及外推幅度的机制。这支持读出头配置是原CheMeleon退步的重要原因，不能证明是唯一
原因，也不能从一次固定线性读出评价所有预训练/图模型。

## 剩余差距和门槛

最好的新头仍比原提交模型基线差5.86%。三个切分的逐终点均值：

| 终点 | 原基线ST-RAE | 组合头ST-RAE |
|---|---:|---:|
| CYP1A2 | 0.828106 | 0.902550 |
| CYP2C9 | 0.778837 | 0.775244 |
| CYP2D6 | 0.932629 | 0.978570 |
| CYP3A4 | 0.543767 | 0.607694 |

2C9仅改善约0.46%，不满足3%开发门槛。2D6低层区间外距离从0.804857降至0.651413
（改善19.06%），但高层从0.362003升至0.402163（恶化11.09%），总体也退步。
因此不能以低活性单项改善为由替换提交。复用原select_development的所有条件，
四终点均保留baseline；未打开确认、未追加alpha/clip/微调/集成候选。
现有复用开发集不能证明解决了真实盲测分布差异；未开展编码器微调，因此也不能说
微调没有价值。这轮完成的是诊断与有限读出头对照。

## 验证与复现

两阶段耗时与哈希分别留在state/runs/20261101-round8-diagnostic-01和
state/runs/20261101-round8-heads-01；新头拟合/评估4.133秒，不含代码/诊断工时。
CPU两线程，预算检查4GiB/1800秒通过；无新依赖、GPU、付费资源或外部数据写入。

- 54项pytest通过，含极端新激活维度的真实对照、query不影响fit变换、加强正则缩小
  系数、非法/非有限输入拒绝；原确认和开发门槛测试沿用。
- Ruff check/format、mypy22源文件、wheel/sdist构建通过。
- [结构化结果与出处](round8-result.json)包含60项开发评估、训练诊断和产物哈希。
  逐分子预测复算ST-RAE/MAE/低高层距离最大误差8.881784197001252e-16。
- 第七轮全部已锁定运行产物哈希未变；基线与新预测的身份/顺序吻合；新实验源码、
  uv.lock、新方案哈希吻合。诊断源码用运行时快照单独校验，未冒充后续追加代码版本。
- 原确认SHA256仍为f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a；
  无confirmation-opened、无regression.csv。未刷新线上规则或validator，因为不具备
  本轮提交条件；软件检查和本地开发下降不冒充官方提升。

```bash
uv sync --frozen --group representation
uv run --group representation python scripts/run_readout.py diagnose \
  --output-dir state/runs/my-readout-diagnosis
uv run --group representation python scripts/run_readout.py heads \
  --output-dir state/runs/my-readout-controls
uv run --group representation python scripts/summarize_readout.py \
  state/runs/20261101-round8-heads-01 --output state/my-readout-summary.json
```

复现依赖已保存的第七轮向量、元数据、开发分区和逐分子预测（均留state，来源锁见
round7-sources-lock.json）；不向Git发布分子数据/权重。最终源码保留诊断函数并追加
新头，原诊断源码快照哈希记录在结构化结果。本轮代码、诊断方案、结果及负结果同步GitHub。

机制依据：[StandardScaler官方定义](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html)、
[Ridge目标与正则定义](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)。
这些文档只证明变换/目标的语义，上述效应大小来自本轮实测。

路由与已读规则见两个方案。Harness adequate，只增加本轮独立模块和入口说明，
没有修改第七轮模型/门槛实现。GitHub使用已核对的个人Git身份和专用SSH映射。
