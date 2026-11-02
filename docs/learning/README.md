# 学习实践索引

当前主线：分子体检工具→ESOL溶解度预测。每次先解释现象，再运行/修改代码，
最后记录自己的结论；工程完成与个人掌握分别验收。

1. [任务、验收与ESOL拟合前协议](plan.md)。
2. [第一课：从SMILES看见分子](01-molecular-checkup.md)。
3. [个人练习记录](answers.md)：尚待学习者作答。
4. [首个学习节点的原件与验收](01-verification.md)、[原运行摘要](01-run-summary.json)：对应56317e8。
5. [结构整理后的行为对账](../engineering/architecture-verification.md)。

规范入口为`uv run aidd-checkup`；旧脚本与aidd_agent.molecular_checkup保留兼容。
ESOL后续用例放application、数据/模型接口实现放adapters，实验协议与结果在本目录
分开保存；不要把数据下载、拟合、报告和讲义写回一个全功能脚本。
