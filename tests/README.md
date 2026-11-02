# 测试布局

- domain：无框架规则。
- application：注入类型化分析函数，检查身份、失败和近邻决策。
- integration：真实RDKit、报告与命令入口；神经脚本兼容测试在缺依赖时显式skip。
- experiments/cyp：原CYP研究测试，仅移动位置，源码不变。
- test_architecture.py：内层依赖、导入边界和冻结源/协议的哈希。

运行项目默认`uv run pytest`；需要完整可选依赖时使用
`uv run --group representation --group submission pytest`。所有单元/集成测试不访问网络，
本机state原件的真实运行对账在工程验收中单独记录。
