# aidd-agent

个人AIDD研究与学习工程：从分子结构理解、数据审计和简单基线出发，逐步练习
可信验证与实验诊断。当前主线为分子体检和ESOL；CYP比赛研究已收尾。

- [文档导航](docs/README.md)：学习、工程与历史研究的入口。
- [学习路线与验收](docs/learning/plan.md) · [第一课](docs/learning/01-molecular-checkup.md) · [个人练习](docs/learning/answers.md)。
- [工程架构与演进约定](docs/engineering/architecture.md)。
- [CYP历史结果与复现](docs/competitions/cyp/README.md)：保留当前最好已评分提交，未重开比赛。

## 本地运行

Python3.12与uv；首次安装需要下载依赖。分子体检在本地计算，不上传结构。

```bash
uv sync --frozen
uv run aidd-checkup --output state/learning/my-checkup
uv run aidd-checkup --smiles CCO OCC COC --output state/learning/my-three-molecules
```

默认示例路径相对仓库根目录；安装包从其他目录运行时使用`--smiles`或`--input`。
输出目录必须不存在。查看输出index.html；原始数据、图像、模型和预测留在ignored state。
旧脚本`python scripts/run_molecular_checkup.py`和原Python API继续兼容。

## 验证

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/aidd_agent
uv build
```

完整可选神经/表示测试使用`uv run --group representation --group submission pytest`。
工程测试通过与个人学习验收分别记录；学习进度不因示例跑通自动完成。
代码采用MIT；vendor保留上游许可证，数据适用各自许可。
