# 工程结构整理计划

2026-11-02。用户授权整理代码与文档、验证、合并main并同步GitHub。

## 设计与边界

1. 分子体检按变化原因分为domain（数据与结构近邻规则）、application（用例）、
   adapters（RDKit和静态报告）、entrypoints（命令解析与依赖装配）。内层仅依赖
   标准库与domain；使用函数类型注入唯一化学计算边界，不为每个类造接口。
2. 原molecular_checkup公开函数和脚本保留薄兼容入口；新增aidd-checkup命令，
   让安装包可直接使用。保持输入、描述符、近邻语义及非法输入报告合同。
3. CYP源码及根级冻结方案/证据保持原字节与路径，保存哈希清单；它们是已有研究
   兼容区，不伪称已全部改造成整洁架构。新功能不得反向依赖此区；已有学习结果
   仍归属于56317e8，重构后运行另存，不改写旧摘要来匹配新源码。
4. 测试按domain/application/integration/experiments-cyp分组；CYP脚本集中到
   scripts/cyp，原路径保留执行包装。所有旧CYP源码、实验门槛和state保持不变。
5. docs/README作为入口；engineering记录架构与验证，learning集中学习计划、
   讲义和验收，competitions/cyp建立历史索引。冻结CYP文件不机械移动，避免破坏
   运行器中的路径与哈希。学习计划迁移后保留旧链接入口。
6. 根README只介绍目标、导航、最小运行/验证命令；CYP历史进度在专门索引查阅。

## 执行顺序与验收

- 先锁定原CYP文件和输出哈希，确认无未提交用户改动；基于学习分支继续工作。
- 拆分分子计算与报告边界，保留兼容API；补纯用例、分层/导入与新旧入口回归验证。
- 整理测试、脚本、文档和Harness，核对调用方与全部本地文档链接。
- 实际运行20例的普通/手性报告，与56317e8的两份molecules.json逐项对账；
  旧运行原件留存。新增运行记录全部参与计算的模块哈希，不只记录薄包装源码。
- pytest、Ruff check/format、mypy、wheel/sdist及安装包命令冒烟；纯领域/用例
  导入不加载RDKit/torch/sklearn，不访问文件/网络。冻结文件与最佳CYP预测/回执
  哈希保持一致。未训练ESOL，未重新提交比赛。
- 明确文件提交并推送；无冲突时快进main，回读远端SHA及公开文档/代码。

## 路由清单

本轮实际加载brainstorming、writing-plans、executing-plans、test-driven-development、
git-workflow、finishing-a-development-branch、verification-before-completion。
规则：AGENTS、skills-index、engineering-workflow、python/code-style、python/data-runtime、
shared-code-change-safety、anti-hallucination；clean-code-architecture仅采用通用的
依赖方向与职责原则，不套Java/Spring分层。未进行ML模型选型，不加载比赛实验流程。
Harness已有研究与学习约束adequate，本轮补充可演进代码的分层和历史兼容区说明。
无需新依赖、付费服务或子Agent。结果另记architecture-verification.md。
