# 第八轮：CheMeleon失效诊断（先于新增对照）

2026-11-01。用户授权诊断并依据证据执行有限回归头或微调对照；保持第七轮全部
验证分区、开发/确认门槛不变。旧实验、数据、预测和确认分区不覆盖。

首先仅复现第七轮StandardScaler+Ridge(alpha10,lsqr)，不新增选型候选：校验缓存
权重/源码/依赖/SMILES顺序/向量哈希；逐split/endpoint复算保存预测、训练与验证
误差、预测范围、拟合样本数、标准化尺度、验证激活幅度和线性系数范数。
只使用原三个开发切分的fit/valid，禁止确认标签评估和盲测拟合。
检查假设：编码/标签错位或实现错误；高维小样本过拟合；标准化放大稀有维度；
输入分布差异。训练/验证差距仅支持过拟合症状，不能单独证明唯一原因。
诊断只复现原头并作数值/结构统计；有限新头的候选、预算、归因对照和参数在诊断
完成后另写round8-plan.md，再拟合新头。不按新头结果追加参数；确认仍至多一次。
若读出头已有可检验原因，优先有限读出头对照，不把微调当必选步骤。

资源：CPU两线程、4GiB、1800秒；不联网训练/上传分子、不用付费资源或GPU。
计划、缓存出处、代码和原实验产物哈希在运行前记录。新增模块，不改第七轮行为。
GitHub同步代码、诊断、正负结果及哈希，state保留向量/预测。提交仅在原门槛全通过后。
路由：systematic-debugging、deep-research(SCIENCE)、writing-plans、executing-plans、
test-driven-development、verification-before-completion、git-workflow、finishing-a-development-branch。
规则：skills-index、AGENTS、engineering-workflow、Python code-style/data-runtime、
anti-hallucination、shared-code-change-safety、research/deep-research。相关正文本轮读取
或复用本会话已读且未变版本。Harness adequate，不改变历史提交与研究合同。
