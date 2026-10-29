# 第六轮：姜黄素原件缺口、多骨架界限与实测

2026-10-29。**新增4条来源原生删失界限，但仍无可信提升，不提交。** 合并上轮后6父体、
3来源、3保守骨架；CYP2D6开发ST-RAE改善0.546%，低活性距离反而恶化4.208%，未达到
总体≥3%且低层≥10%改善门槛。确认集未评估，未生成盲测CSV，未替换第二轮官方提交。

## 姜黄素：准确定位了原PDF，视觉与响应缺口尚未关闭

已定位[作者公开上传的正确期刊PDF](https://www.researchgate.net/profile/Regina-Appiah-Opong/publication/5603864_Structure-activity_relationships_for_the_inhibition_of_recombinant_human_cytochromes_P450_by_curcumin_analogues/links/5c2646da92851c22a34b5dd0/Structure-activity-relationships-for-the-inhibition-of-recombinant-human-cytochromes-P450-by-curcumin-analogues.pdf)，
原生网页缓存识别为application/pdf、完整11页，DOI/题名/作者/页码吻合。之前网页工具的
相对链接错误解析为`/publication/profile/`，本轮纠正到`/profile/`后能读出PDF正文。
本地直接下载仍为403 HTML，Chrome显示安全检查；未绕过或解CAPTCHA。

这次**没有取得真实PDF二进制，也没有收到可目视的原始页图**。截图接口只返回文本占位，
不能声称看过Scheme2/3或µ字形；原PDF SHA256保持null。保存的是工具正文转录的哈希。
[作者博士论文机构条目](https://hdl.handle.net/1871/13256)也已正确定位，其p99 Table8
重复出现相同六个数值/log配对和mM表头，但属于同一实验再呈现，不能算独立测量。

原PDF文字与前轮转录一致，继续支持“Table6 log按mM参照、换成molar pIC50需加3”的
算术判断；原图单位/结构映射、2D6的0.39–200范围单位、B14正文111.7与表118.7µM
冲突及每条曲线50%夹逼仍未解决。SI未找到/获得，不宣称不存在。6个校正候选虽均通过
5656个官方主/辅助/盲测结构排除（2个骨架家族），仍全部隔离，不由可检索正文升级准入。

详细可得性、失败响应与转录存放`state/sources/round6/curcumin_audit/`及
`curcumin_visual/`；本轮没有新的姜黄素训练标签。[证据锁](round6-evidence-lock.json)
明确区分可读原PDF正文、真实二进制、视觉证据与SI。

## 新增可靠界限及条件差异

| 证据 | 新父体/新骨架家族 | 来源原生监督 | 准入依据与限制 |
|---|---:|---|---|
| PMDA XT175053：E1245/E1246/E1247 | 3 /1 | IC50>600µM，即pIC50≤3.221849 | 直接零分钟预孵育表；实际600µM上限；最大观测抑制5.7/3.0/10% |
| Molecules2016 compound3 | 1 /1 | IC50>100µM，即pIC50≤4 | Table3/Fig3和方法支持；100µM仍约58%活性；底物浓度单位存在冲突，单独来源 |
| 继承ACS2020 compound6/7 | 2 /1（已有） | pIC50≤4 | 原SI直接曲线，保守界限；不恢复精确IC50 |

[PMDA原始CTD](https://www.pmda.go.jp/drugs/2020/P20200629001/620023000_30200AMX00513_I100_1.pdf)
真实PDF已下载并目视：p31–32结构/分子式映射，p164–166方法/单位/表格。E1245/46/47
是SNAC及其链缩短代谢物的O-glucuronides；3个化合物共1个骨架家族。糖立体未绘，
仅用已核实连通性SMILES，不编手性；本轮指纹和排除键均不使用立体。酶为200供者池
HLM、≤0.1mg/mL、右美沙芬约Km/S50、LC-MS/MS。完整剂量网格、精确底物浓度、
反应温度/时长和NADPH具体加料次序未在摘要列明，保持unknown。直接零分钟列与
30min±NADPH列分开；最大抑制是**所有剂量中的最大值**，不能写成600µM单点数值。
实际测试上限600由原方法明确写出，不是从`>600`反推。p59–60数千µM的竞争模型
外推估计全部不用。旧研究`>100`不再作为独立观测加入。

[Molecules原PDF](https://mdpi-res.com/d_attachment/molecules/molecules-21-01488/article_deploy/molecules-21-01488.pdf)
及[SI](https://mdpi-res.com/d_attachment/molecules/molecules-21-01488/article_deploy/molecules-21-01488-s001.pdf)
已取得。主流程目视Scheme1、Table3/Fig3及p10方法；compound3侧链与PubChem
pleuromutilin母核逐图映射，图分子式与HRMS的C29H39N3O4S相符。抑制剂实际剂量
0.05/0.1/0.5/1/10/50/100µM由Fig3及方法分别确认；HLM0.3mg/mL、37°C无NADPH
预孵育10min，再NADPH1mM启动15min、LC-MS/MS、三次实验。原文正文和底物表确实
印mM、右美沙芬数值10；**不擅改10µM**，也不借被引论文的另一个浓度补齐。仅将
有独立测试化合物剂量证据的界限作为单独实验域辅助约束，不能声称同于官方条件。

总计20个唯一候选：2个继承、6个姜黄素、7个监管、5个论文；6准入、5骨架排除、9隔离。
原始SMILES/数值/逐条裁决留在`state/sources/round6/locked-audit/`，Git只保存必要汇总/哈希。

| 排除或隔离对象 | 处理依据 |
|---|---|
| SNAC/E494/E506 | 标准父体未重叠，但保守苯环骨架与官方重叠，排除 |
| Thymoquinone | 实测最高100µM，原文`>500`没有测试范围支持；并有官方保守骨架重叠，排除 |
| Chloramphenicol | 原精确375.9µM超250µM测试上限；并有官方保守骨架重叠，排除，不用Ki代IC50 |
| Bictegravir | 结构排除通过；目标表原始页图及PDF二进制/hash缺失，隔离 |
| Ivosidenib | 原文缓存表`>50µM`/直接臂可读，但原PDF/页图仍未取得，隔离 |
| Treosulfan | 原文有40–10000µM及“未抑制”描述；取得SI后确认S13/14只有2C19/3A4，没有2D6数值曲线，不构造`>10000` |
| 姜黄素6个候选 | 原图及响应缺口仍在，继续隔离 |

监管Agent最初实际仅做4905主数据+750盲测初筛，曾误称含辅助独有分子，已更正元数据。
**主流程独立重算完整4906+750=5656**，6个准入父体与保守骨架重叠均0。文献、原PDF、
SI、数据库和监管转引不是多个独立实验；没有将同一来源重复加权。

## 原预算内的固定实验

[拟合前方案](round6-plan.md)保持上轮4候选/正则/权重/阈值，未按结果放宽。唯一代码变化
为CLI的`--plan-file`选择当前协议哈希；模型数学不变。各来源单独正则偏移，不把外部
低响应变成官方精确标签。基线/官方区间各半只作诊断，不参与候选选择。

| 模型 | 平均ST-RAE↓ | 低层距离↓ | 高层距离↓ | 总体相对基线改善 |
|---|---:|---:|---:|---:|
| 基线SVR | 0.932629 | 0.804857 | 0.362003 | — |
| 仅官方区间监督 | 0.928247 | 0.839334 | 0.355894 | 0.470% |
| 官方区间+6条外部界限 | 0.927534 | 0.838723 | 0.355557 | 0.546% |
| 基线/外部模型各半 | 0.929020 | 0.821790 | 0.358265 | 0.387% |
| 诊断：基线/官方区间各半 | 0.929333 | 0.822096 | 0.358415 | 0.353% |

外部界限相对相同区间损失对照，ST-RAE仅改善0.07682%，低层距离仅改善0.07285%。
这没有独立确认或统计/数值稳定性证据，不能称可信的数据收益；相对原SVR，低层仍恶化
4.2077%。三个开发切分外部ST-RAE分别为0.915592/0.967470/0.899540；相应基线为
0.916110/0.970782/0.910994。两个骨架切分骨架交叉0，analog压力切分交叉32组；
均为复用开发集，绝不是新的独立盲测。

本轮路径`state/runs/20261029-round6-censored-01/`，runner耗时9.985s、峰值RSS
1,107,755,008bytes（1.032GiB）、2线程，低于1800s/4GiB预算；不含文献核验/工程耗时。
6次区间拟合按L-BFGS-B停止条件成功、90–145迭代，梯度范数最高0.01115，部分以
目标变化容差停止；不把极小差异当作优化精度已证明的改进，不改参数追分。

没有合格开发候选，因此没有打开963分子确认集、没有全量盲测重训、没有CSV，亦未
执行本轮官方validator/规则刷新/平台上传/评分查询。平台动作属于未执行，不以本地
软件检查代替。现有有效官方结果没有被本轮替换。

## 验证、路由与复现

- pytest47通过（新增方案文件缺失须先失败且不得创建运行目录）；Ruff check/format通过；
  mypy20源文件通过；wheel/sdist构建及仓库外安装包`--plan-file`/preflight smoke通过。
- 15行开发指标由已保存逐分子预测复算，误差<1e-12；源码/方案/数据/产物哈希吻合。
  外层父体交叉0，开发训练/查询均无确认分子；确认分区原SHA不变，无打开标记或盲测CSV。
- 实际研究路由deep-research及evidence/framework/output引用、PDF只读、web-access、
  dispatching-parallel-agents；计划writing-plans；测试test-driven-development；收尾
  verification-before-completion、git-workflow、finishing-a-development-branch。规则实际读取
  索引/AGENTS、engineering-workflow、Python code-style/data-runtime、research/deep-research、
  anti-hallucination，共享修改规则复用前轮已读内容。Harness adequate，最小补本轮事实入口。

```bash
uv run aidd censored --audit-dir state/sources/round6/locked-audit \
  --plan-file docs/round6-plan.md --output-dir state/runs/my-round6-run
```

需保留本地人工审计卡片/证据，原始数据不随Git发布。关键SHA256：

- 审计锁：`f95634f3194676ae24cde1227e014153ccad2a3af678743fe598c70e788b718a`
- 方案：`58981629d6520a65e73480296a866ef10c11d09d6eb6d51798c12a847e61b4ed`
- 协议：`ed3265aaee499caf3176a551db975fbfc2b9ff3a8386594d312ab9d8b90c0fd6`
- 实测报告：`59fc766492ff4bc9e07be3b2f38d6c170fe1c730a1edb49b269ac04d0e623d30`

本轮补到了两个新骨架家族的实验界限，仍远非足够的目标分布覆盖；不能由这次失败推断
删失学习普遍无效，也不能由新增记录数推断排名潜力。姜黄素原始像素、结构与响应缺口
仍是具体待补证据；没有因此改用外推值、伪标签或降低验证门槛。
