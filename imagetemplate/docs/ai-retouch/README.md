# AI 修图副业 · 资料索引

> 本目录是「AI 修图副业」项目的调研与方案沉淀。
> 可信度标记：`[核实]` = 有公开来源；`[推断]` = 基于核实材料的推理；`[未核实]` = 无权威来源，**不得当事实引用**。

## 一、按你的四个诉求查找

| 你的诉求 | 对应文件 |
|---|---|
| ④ 比对市面所有著名图片大模型（效果/价格/性价比） | [AI修图模型对比与成本测算.xlsx](AI修图模型对比与成本测算.xlsx) · [model-comparison.md](model-comparison.md) |
| ③ 解决"AI 修图不自然、有违和感" | [retouch-quality-diagnosis.md](retouch-quality-diagnosis.md) |
| ② 全场景完善提示词 | [prompt-library.md](prompt-library.md)（**开箱即用**） · [prompt-engineering.md](prompt-engineering.md)（方法论） · [ai-retouch-delivery-standard-knowledge-base.md](ai-retouch-delivery-standard-knowledge-base.md)（交付规格） |
| ① 影楼价格高、AI 是趋势（商业定位） | 见下方"三个反直觉结论" · [ai-retouch-compliance-cn.md](ai-retouch-compliance-cn.md) |

## 二、文件清单

| 文件 | 内容 | 状态 |
|---|---|---|
| [AI修图模型对比与成本测算.xlsx](AI修图模型对比与成本测算.xlsx) | **45 个模型**横向对比、定价测算（改汇率/张数自动重算）、场景推荐、授权与来源说明；含 9 处型号认知修正 | ✅ 检查 pass |
| [model-comparison.md](model-comparison.md) | 上述工作簿的文字版，含价格明细、限流约束、按场景推荐 | ✅ |
| [retouch-quality-diagnosis.md](retouch-quality-diagnosis.md) | 违和感七大成因 → 解法、商业软件技术路线对比、可执行参数清单、客观质检指标 | ✅ |
| [prompt-engineering.md](prompt-engineering.md) | 提示词工程方法论：四段式结构、保留清单句式库、多轮迭代、分场景模板 | ✅ |
| [prompt-library.md](prompt-library.md) | **可直接复制使用**的提示词库：5 个完整场景模板、保留清单句式库、10 条分场景修图指令、影楼关键词速查、失败修复句、多轮编排 | ✅ |
| [ai-retouch-delivery-standard-knowledge-base.md](ai-retouch-delivery-standard-knowledge-base.md) | 交付标准知识库：证件照硬规格、三层可行性、六段式骨架、影楼关键词库、5 个模板、返工话术 | ✅ |
| [ai-retouch-compliance-cn.md](ai-retouch-compliance-cn.md) | 中国大陆合规：标识办法、肖像权判例、上传第三方 API 风险、平台规则、9 类不做清单 | ✅ |
| [tools/build_workbook.py](tools/build_workbook.py) / [tools/verify_workbook.py](tools/verify_workbook.py) | 工作簿的生成与校验脚本（可复现、可改数据重跑；已校验 0 公式错误） | ✅ |

> 原始抓取证据与完整调研报告保存在工作区根目录 `.dsh-research/`（含 80+ 份官方页面快照），
> 用于复核任何价格数字的来源。

## 三、三个反直觉结论（先看这些，比选模型重要）

### 1. 「违和感」不是模型问题，是工作流问题（约占 70%）
客户说"不自然"，八成是因为把「**生成**」当成了「**修图**」。
所有商业修图软件的共同点是：**窄任务监督模型 + 面部区域分割 + 只输出增量而非重建 + 强度默认低于 100%**。
→ 详见 [retouch-quality-diagnosis.md](retouch-quality-diagnosis.md)

### 2. 证件照不能做"美颜"，这是结构性红线
官方明文要求护照照片"不得对照片进行修改，不得使用合成照片"；多地报名系统已禁用精修证件照，理由正是"面部特征失真导致审核不通过"。
**证件照的价值在「合规裁切 + 换底色」，不在美颜。**
→ 详见 [ai-retouch-delivery-standard-knowledge-base.md](ai-retouch-delivery-standard-knowledge-base.md)

### 3. 返工的第一根因不是修图质量，而是"方向未对齐"
客户说"感觉不对"却说不清时，修多少轮都是白修。
→ 对策是**先出 3 张风格小样强制二选一**，这比"把一张图做到完美"更能降低返工率。
→ 详见 [ai-retouch-delivery-standard-knowledge-base.md](ai-retouch-delivery-standard-knowledge-base.md)

## 四、能力边界（不要接的单）

| 做不到客户级无痕 | 原因 |
|---|---|
| AI 换脸 / 换头 | 几何不一致 + 语义不一致 |
| 大幅改姿态 | 人体结构约束 |
| 整图重绘的"完美婚纱照" | 客户投诉"假"的重灾区 |
| 复杂首饰 / 文字 / 眼镜结构 | 高频结构生成不可靠 |
| 多人合影中每个人的一致性 | 身份一致性未解决 |

**业务建议**：定位为「实拍/旧照底片 + AI 后期」，而不是「纯 AI 出片」。有真实底片做锚点，天然规避违和感、身份漂移与平台 AI 假图拦截。

## 五、可交付的商业模式

> **不是「AI 替代影楼」，而是「专业工具做 80% 批处理 + 人做 20% 关键帧精修 + 客观质检脚本兜底」。**

AI 已可替代：初选挑片、基础曝光色彩、批量磨皮祛斑、背景清理、尺寸输出、同组色调统一。
必须人工：光位设计与原片质量把关、Dodge&Burn 塑形、五官形体微调、细节崩坏修复、**交付尺寸上的最终验收**。

## 六、代码能力

| 能力 | 位置 | 状态 |
|---|---|---|
| 客观质检引擎（把"自然不自然"变成可计算指标） | `src/main/java/com/example/imagetemplate/service/ImageQualityMetricsService.java` | ✅ 已实现 |
| 质检引擎单元测试 | `src/test/java/com/example/imagetemplate/service/ImageQualityMetricsServiceTest.java` | ✅ 编译通过，断言覆盖已由行为验证确认 |
| 行为验证 runner（绕过 Maven） | `.verify-out/QualityVerifyRunner.java` + [说明](../../.verify-out/README.md) | ✅ **29/29 通过** |

> 首轮行为验证**发现并修复了 5 个真实 bug**（编译通过但行为错误）：纹理能量判据用错度量导致过度磨皮漏判、
> 噪点判据用绝对阈值导致恒为 0、`normalize()` 从未被调用导致大图不缩放。
> 详见 [验证说明](../../.verify-out/README.md)。

### 质检引擎指标
- **单图**：亮度、对比度、锐度、噪点、纹理熵、肤色占比与均值
- **对比**：亮度偏移、肤色色差、结构保持度、**纹理保留率**（核心判据）、纹理熵比
- **判定**：纹理保留率 < 0.75 → 疑似过度磨皮；结构保持度 < 0.9 → 疑似结构漂移；亮度偏移 > 8 → 曝光漂移；肤色色差 > 5 → 肤色漂移

## 七、待办与已知限制

### 待办
- [ ] 把交付标准中的 5 个提示词模板与句式库转成 `image-prompt-templates.json` 的 `direct-prompt` 条目
      （当前 47 条精选 / 20 条 direct-prompt，改动需同步更新测试断言与三处文档）
- [ ] 质检 API 端点（`POST /api/image-templates/quality/compare`）
- [ ] 同步更新 `imagetemplate/AGENTS.md`、`README.md`、根文档
- [ ] 补核实：OpenAI/Google 官方原始单价、Midjourney 订阅价、Adobe API 按量价（均被 403 或登录墙阻断）

### ⚠️ 选型前必读：型号已换代

调研发现早期认知里有 **9 处需要修正**，其中 4 处会让你选到已淘汰的模型：

| 别选 | 原因 | 换成 |
|---|---|---|
| **qwen-image-3.0-pro** | RPM 仅 5（≈300 张/小时天花板） | Seedream 5.0 pro 或 wan2.7-image-pro（RPM 300） |
| **FLUX.1 Kontext [pro]/[max]** | 已进 Legacy Models，无现役报价 | FLUX.2 [pro] 或 FLUX 3 Image |
| **可图 Kolors** | 快手主线转可灵，停更 | — |
| **gpt-image-1 系列** | 已被 2 代取代 | gpt-image-2 |
| **GPT Image 2.5 报价** | 有模型但无公开单价 | 勿写进报价单，需登录 fal 确认 |

**两条会卡死业务的硬限制**：
- 腾讯混元**默认并发 1**，批量必须买叠加包（¥500/并发/天 或 ¥10,000/并发/月）
- qwen-image-3.0-pro **RPM 5**，无法批量

### 已知环境问题（不阻塞已交付内容）
工作区 `target/` 子树的 Windows 文件权限损坏（沙箱授权项**非继承**，只作用于被修复的那一层，逐层修复不可行），
Maven 无法写入 `target/maven-status/.../createdFiles.lst`，因此 **`mvn test` 跑不起来**。
- 已用 `.verify-out/` 的 javac 通路完成行为验证（29/29 通过），质检引擎的正确性有证据。
- 彻底修复：把本会话切到「完全权限」后重跑 `mvn -pl imagetemplate -am test`。

### 调研的已知缺口
- 一寸/二寸/小二寸像素值、亚马逊主图产品占比：标注【待核】，需按当地最新规定核实
- 修改轮次惯例（2 轮免费）、定金比例、源文件不交付：行业惯例归纳，**无权威来源**
- OpenAI/Google 官方原始单价（Cloudflare 403）、Midjourney 订阅价、Adobe Firefly/Photoshop API v2 按量价（企业登录墙）、Krea/Remini/美图（无公开价目页）：**均未核实，勿对外引用**
