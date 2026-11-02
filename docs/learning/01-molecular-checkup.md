# 第一课：从SMILES看见分子

目标：能解释「字符串、分子图、描述符、指纹」四者的关系。工程已实际运行；
个人学习验收等待你自己的解释与修改，不能由程序通过代替。
任务与后续ESOL验收见[学习计划](plan.md)。

## 先预测，再运行

先写下你的直觉：`CCO`和`OCC`是否相同？`CCO`和`COC`是否相同？
暂时不看下方解释。然后在项目根目录执行：

```bash
uv sync --frozen
uv run aidd-checkup \
  --smiles CCO OCC COC --output state/learning/my-first-checkup
```

用浏览器打开输出目录中的index.html。molecules.json保存完整数值与近邻，
report.json记录版本、输入/源码和产物哈希。输出目录必须不存在；第二次运行换新名字。
该命令本地计算结构，不上传、不用活性标签，不需要安装PyTorch或DeepChem。

## 最小代码与本次实测

先理解这几行即可，不要求一次读完报告生成代码：

```python
from rdkit import Chem
from aidd_agent.adapters.rdkit.molecules import describe_smiles

mol = Chem.MolFromSmiles("CCO")
assert mol is not None
print(mol.GetNumAtoms())  # 3，当前图对象中的原子节点
print(Chem.MolToSmiles(mol))  # CCO
print(describe_smiles("CCO"))  # 结构派生的描述符
```

`C-C-O`描述的是连接关系。中性的这个例子中，碳补足四价、氧补足二价，得到
CH3–CH2–OH。默认Mol中通常省略可隐式表示的氢节点，因此GetNumAtoms()为3，
而分子式C2H6O共有9个原子；这两个数量的定义不同。

同一图可以从不同方向遍历。`OCC`与`CCO`经过本版本RDKit规范化后均为CCO。
`COC`则是CH3–O–CH3（二甲醚），氧的连接位置不同，即同分异构体。

本机RDKit2026.09.1实测如下，不是实验测量值：

| 输入 | 规范SMILES | 分子式 | MolWt(g/mol) | HBD | HBA | TPSA(Å²) | 计算logP |
|---|---|---|---:|---:|---:|---:|---:|
| CCO | CCO | C2H6O | 46.069 | 1 | 1 | 20.23 | -0.0014 |
| OCC | CCO | C2H6O | 46.069 | 1 | 1 | 20.23 | -0.0014 |
| COC | COC | C2H6O | 46.069 | 0 | 1 | 9.23 | 0.2626 |

MolWt是原子量加和的平均摩尔质量；它不能区分这一对异构体。HBD/HBA分别为
氢键供体/受体计数：乙醇有O–H可以作供体，二甲醚没有O–H；这里两者的氧都可作
受体。TPSA是基于片段的拓扑极性表面积。MolLogP为计算的辛醇/水分配系数对数，
不是logD，也不是此分子的实测溶解度。这些是模型输入线索，不能直接给出药效。

两个乙醇写法计算logP在浮点数最后几位约差5.6e-17，属于加和顺序的数值精度差异；
身份比较用明确的结构规则，数值比较用适当容差。不要为强行相等而改动化学结构。

## 原子、电荷和盐：为何先保留原输入

20条示例中还包括以下对照：

| 输入 | 例子 | 片段数 | 总形式电荷 | MolWt(g/mol) |
|---|---|---:|---:|---:|
| CC(=O)O | 乙酸 | 1 | 0 | 60.052 |
| CC(=O)[O-] | 乙酸根 | 1 | -1 | 59.044 |
| CC(=O)[O-].[Na+] | 乙酸钠表示 | 2 | 0 | 82.034 |

方括号中`-`/`+`是形式电荷，点号表示不相连的片段。乙酸钠的总电荷为0不代表
图中没有带电原子，也不能简单当作乙酸。自动去盐或中和会改变描述对象，后续
数据集必须先明确标签对应游离体还是具体盐型。本工具仅提示多片段，不擅自处理。
盐的MolLogP虽然能够算出，也不按该盐的真实溶液分配性质解释。

## 一个表示消融：相似度为1是否等于同一分子

运行同一批示例，只改一个条件：

```bash
uv run aidd-checkup \
  --output state/learning/my-example-plain
uv run aidd-checkup --chirality \
  --output state/learning/my-example-chiral
```

两个运行共用20条手工示例：18条有效、2条非法。非法闭环C1CC和空字符串仍在
报告中列出原因，不被悄悄丢弃。两组同一结构为乙醇正反写法和苯的两种写法。

Morgan指纹用原子局部邻域编码结构；本工具固定radius2和2048bits。Tanimoto对
位指纹等于「共同置1位数/至少一方置1位数」，在0至1之间。固定长度哈希会有碰撞，
而表示还可能忽略某些结构信息；它不适合作为唯一身份，也不是活性相同的证明。

本次两个已指定相反手性的乳酸输入，其规范SMILES不同；默认不编码手性时，
指纹相似度为1.000000；打开手性后降为0.692308。`@`/`@@`与SMILES邻居排列有关，
不直接等同固定的R/S标签；例子用a/b命名。未指定手性的乳酸还保留为另一输入，
不据此推断是纯对映体或某个比例的混合物。

结构近邻会排除当前分子及同一规范身份，并对候选身份去重，所以乙醇不会把反向
写法列为“新近邻”。20条样本中乙醇最近的不同结构为丙醇，Tanimoto约0.555556；
这个值依赖指纹设置和候选库，只解释为本次结构比较。

## 你来修改与解释

请在[个人练习记录](answers.md)或对话中给出自己的答案，每题2–4句话即可：

1. 为什么CCO/OCC应在训练和测试划分时放在一起，而CCO/COC不能仅凭分子式合并？
2. 乙酸钠总电荷为0，为什么仍不能当作乙酸的完全相同输入？
3. 两个乳酸规范身份不同，默认指纹Tanimoto却为1，反映了哪一种表示限制？
4. 新增`CCCCO`（1-丁醇），运行到新目录，记录其MolWt/HBD/TPSA与乙醇的差异，
   先解释你预测会变/不变的字段，再检查输出。

前三题关注概念，第四题证明你能独立改变输入和读取结果。Agent不预填你的答案，
也不因示例已跑通而将学习验收勾选为完成。下一课将追踪指纹和近邻代码，再进入
ESOL的logS、数据审计与验证划分。

实现入口：[结构与描述符](../../src/aidd_agent/adapters/rdkit/molecules.py)、
[命令装配](../../src/aidd_agent/entrypoints/checkup.py)、[示例](../../examples/learning/molecules.json)。
原理参考：[RDKit官方入门](https://www.rdkit.org/docs/GettingStartedInPython.html)。
本课运行与验证摘要见[工程记录](01-verification.md)。
