# 第三轮 Stage B：在封存确认集上检验联合任务学习

Stage A完成后、Stage B训练前登记。Stage A的门槛/负结果不更改，未打开的963分子
确认分区原样保留。新假设：两阶段辅助预测的噪声与稀疏已测标签的低活性占比，
限制了线性迁移；直接联合优化共享表示并平衡训练层，可能减少低活性偏差。
反证：只有低活性变好而总体/高活性变坏，或联合任务不胜相同结构的直接任务控制。

## 固定候选与训练

共三个候选：同分区的第二轮参考 `baseline`，`direct_mlp`，`joint_mlp`。
后两者均由seed=17/29的两个网络等权平均，不按开发或榜单另选种子/权重。

- CPU、最多2线程，无GPU、无付费资源。新增可选 `neural` 依赖组并锁定实际
  PyTorch版本；不改变普通CLI/首两轮的依赖需求。
- 输入为log1p Morgan count的2048维加217描述符。描述符只在当前训练分区标准化，
  转换后截到[-5,5]；指纹不做全局标准化。共享MLP：2265→128 ReLU Dropout(.1)
  →64 ReLU→输出。direct输出4个pIC50，joint另输出4个单浓度readout。
- 只在当前fit分区计算每终点的均值/标准差。缺失标签保持NaN，在索引已测位置
  之后才计算loss；不把缺失目标当零，也不构造伪pIC50。
- 两网络的直接目标损失相同：.5 SmoothL1(point) + .5 SmoothL1(interval-distance)，
  beta=.5，先按各已测任务计算再平均。低/高活性按训练样本数各给予半权，权重
  上限5；某层不存在则保持该终点等权。测试/验证标签不参与训练权重。
- joint额外加 .5×四个已测单浓度任务的平均SmoothL1，尺度来自训练分区；辅助
  值只作独立目标，推理仍只输入分子结构。direct与joint采用相同初始共享层、
  数据顺序、优化器与直接目标权重。
- AdamW(lr=.001, weight_decay=.0001)，batch256，最多200 epochs。外层训练池
  内用15% GroupShuffleSplit(seed101)做早停，且其所有辅助观测一并排除。
  每10epochs计算inner的官方宏平均ST-RAE，连续3次未改善且至少30epochs则停；
  取最佳epoch数后，从相同seed重新在完整外层训练分区拟合该epoch数。
  每步gradient norm上限5，防止数值发散；数值失败留证据，不自动改学习率重试。

## 验证与提交

完全复用Stage A的开发与确认分区，核对确认split SHA256相同，不重新选有利切分。
确认分区SHA256固定为 `f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a`。
每个外层验证分子在神经网络的全部直接/辅助训练、标准化、权重计算和早停数据中排除。
复用Stage A的逐终点开发门槛与确认门槛，包括CYP2D6低/高层及bootstrap。
若开发选型的CYP2D6仍为baseline则不打开确认集。不得凭该阶段重新宣称分布一致；
结构相似度失配继续作为限制报告。

Stage B最多1700秒，总训练预算与Stage A合计不超过约1800秒，RSS<4GiB。
不根据中途分数追加网络、层数、loss或权重搜索。全部门槛通过才允许生成盲测文件；
任何失败都不上传，保留第二轮现有提交。本阶段不是用公榜挑选前两轮历史预测。

参考：同赛道作者的masked/joint multi-assay思路见[调研记录](round3-research.md)；
损失、优化器与确定性设置按[PyTorch文档](https://docs.pytorch.org/docs/stable/notes/randomness.html)
与安装版本API核验。本轮实测才是是否有效的证据，不预称神经网络优于核方法。
