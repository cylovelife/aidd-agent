# 结构整理验收

2026-11-02。按[架构计划](architecture-plan.md)完成可演进主线的职责拆分、测试/脚本
分组和文档导航；设计边界见[工程架构](architecture.md)。本次不重做模型选型或学习验收。

## 已交付

- 分子体检分为domain/application/adapters/entrypoints；原225行全功能模块变为
  薄兼容API，核心规则不读写文件、不导入RDKit/ML框架。化学能力用函数类型注入，
  没有给每个值对象增加空接口。
- 新增已安装命令aidd-checkup；旧Python API、原脚本参数及aidd比赛命令保持兼容。
  新manifest为schema2，记录五个参与计算/输出的模块哈希；数据记录合同保持一致。
- 测试分为纯规则、用例、真实集成、CYP实验；原CYP测试仅移动。六个CYP脚本
  原件进入scripts/cyp，旧位置保留runpy包装，三个代表性旧命令--help已实际验证。
- 学习计划进入docs/learning/plan.md，旧链接入口保留；根README精简为导航和最小
  命令。学习、工程、CYP历史索引分开，个人练习保持待验收，不伪造完成状态。

## 行为与证据保留

[分子体检对账](checkup-refactor-result.json)记录两个新运行：
state/learning/20261102-architecture-plain-01与20261102-architecture-chiral-01。
各自20条记录与56317e8的checkup-02/chiral-02逐项完全相同，包含描述符、错误、
身份、近邻及排序。两份molecules.json哈希分别仍为
98eb0abff0ede18177d0c4862621bb08c4edee51420e5554234fec4a32a258c8和
41b27d636ab12235d0b543560577c7e8fbc1e5adc09652846f021cc097295c76；PNG字节也相同。
新运行源码与全部产物哈希通过；旧运行、旧JSON摘要不覆盖、不改写。

[冻结保留清单](cyp-preservation.json)核验76份原路径CYP源码/协议/证据、19份逐字节
迁移的脚本/测试，共95份文件。源文件不因整理而放宽校验。最佳预测与原回执SHA256
分别仍为f6b1987532b0d2469e5527f8702d6017f04dc5a65c32cebd6c4f16d50fc49b28、
359269d7ed1984cc0f7ee5cf65766c885a4f7357281d56bc934b92d4fb47c9f1。
本轮没有网络比赛上传、没有重新训练CYP/ESOL，也没有打开确认分区。

## 软件验证

- `uv run --group representation --group submission pytest`：81项通过。
  含纯Tanimoto规则、相同指纹不同身份、逐行失败与意外后端错误区分、重复ID
  在计算前拒绝、兼容入口对账、JSON边界校验和冻结文件保护。
- 架构测试检查四层依赖方向；子进程仅导入domain/application，未加载
  rdkit/torch/sklearn/httpx/pandas。旧CYP脚本神经依赖缺失时明确skip，不使其成为
  普通学习命令的前置依赖；本次完整测试安装了相应可选组。
- Ruff check/format通过；mypy35源文件通过；wheel/sdist构建通过。
- 新旧报告数据与PNG一致，是行为回归证据；单元测试/构建不作为药效或学习掌握证据。

独立安装包验证也已通过，见[安装包验收摘要](package-smoke.json)。首次离线安装因
本机缺少registry缓存而未完成；随后按uv.lock导出的基础依赖正常安装，未放宽版本。
在仓库外创建独立venv，安装构建出的wheel；确认aidd_agent来自该venv而非源码目录，
纯用例导入不加载RDKit/torch。已安装aidd-checkup成功计算CCO/OCC/COC三例，
原aidd --help也成功；临时环境验证后自动清理。没有训练或比赛提交。

所有本地Markdown引用已核对，Ruff最终检查109份文件格式通过，git diff --check通过。
交付按用户授权快进main并推送，远端SHA与公开核心文件的回读在交付消息中确认。

## 已读规则与流程

实际加载：brainstorming、writing-plans、executing-plans、test-driven-development、
git-workflow、finishing-a-development-branch、verification-before-completion。
已读：AGENTS、skills-index、engineering-workflow、python/code-style、python/data-runtime、
shared-code-change-safety、anti-hallucination、clean-code-architecture的通用依赖/职责原则。
调用方核查覆盖脚本、Python API、测试和讲义；未套Java专用框架或引入新依赖。
Harness既有研究/学习约束adequate，本轮补足分层、兼容区和验证命令说明。
