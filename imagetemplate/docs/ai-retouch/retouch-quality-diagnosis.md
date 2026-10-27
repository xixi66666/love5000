# AI 修图「违和感」诊断与工程解法

> 回答一个决定副业能否成立的问题：**为什么 AI 修图看起来假，怎么解决。**
> 可信度标记：`[核实]` = 有公开来源；`[推断]` = 基于核实材料的推理；`[未核实]` = 无权威来源。

---

## 一、核心结论（先看这个）

### 结论 1：在「修图」场景，工作流是主因，模型能力只占约 30%

客户说"不自然"，八成不是因为模型不行，而是**把「生成」当成了「修图」**。

依据（三条互相独立）：
1. 职业修图师与 Retouch4me 官方一致认为：塑料感来自**方法而非工具**——过度强度、用修图救烂原片、只在大屏 100% 看而不在交付尺寸看。`[核实]`
2. 专用小模型已证明难点可解：AAAI-26 用 **6MB U-Net 预测逐像素亮度增量**（不重建图像），纹理保留率 100%。难点可解，缺的是流程。`[核实]`
3. 通用大模型走的是"重画"路线，**天然丢纹理**；换成"只输出增量"的工具链，问题大半消失。`[推断]`

### 结论 2：违和感的底层是「信息被删除」，不是「信息被生成」

这是一个反直觉但极重要的判断。皮肤变塑料，是因为**毛孔、绒毛、次表面散射的高频信息被抹掉了**，而不是因为模型画得不好。

所以解法的方向不是"让模型画得更好"，而是**别让它重画**。

### 结论 3：三条不可逾越的能力边界（不要接单）

| 做不到客户级无痕 | 原因 |
|---|---|
| **AI 换脸 / 换头** | 几何不一致 + 语义不一致，双重难题 |
| **大幅改姿态** | 人体结构约束 |
| **整图重绘的"完美婚纱照"** | 这正是客户投诉"假"的重灾区 `[核实]` |
| 复杂首饰 / 文字 / 眼镜结构 | 高频结构生成不可靠 |
| 多人合影里每个人的一致性 | 身份一致性未解决 |

---

## 二、成因分类框架

SJTU 深度图像合成综述把所有"不真实"归为**三类不一致** `[核实]`——你的所有违和感投诉都能归入其中：

| 类别 | 具体表现 |
|---|---|
| **外观不一致** | 边界、光照统计、阴影反射、分辨率/锐度/噪点差异 |
| **几何不一致** | 尺度、悬浮、遮挡、透视错误 |
| **语义不一致** | 位置与交互不合理 |

---

## 三、七大成因 → 解法对照表

### A. 皮肤（最致命）

**成因**：模糊式磨皮不分青红皂白抹掉毛孔与纹理 → 塑料/蜡像。`[核实]`
另一层：扩散模型在低 denoise 下只重建低频，高频（毛孔、绒毛、皮肤次表面散射 SSS 的暖色透光）被"重新想象"成均匀色块 → 蜡感。`[推断]` SSS 是让皮肤"活着"的物理机制，通用生成模型**没有显式 SSS 约束**。`[核实]`

**解法**：
1. **频率分离**（Adobe 官方步骤）`[核实]`
   - Low Frequency 层：Gaussian Blur 5px
   - High Frequency 层：Apply Image → Subtract，Scale 2，Offset 128
   - 混合模式 Linear Light
2. **低 denoise（0.25–0.45）+ 只覆盖斑点的 mask** `[核实]`
3. **★ 2026 关键突破：加性混合图（additive blend map）**
   - AAAI-26：6MB U-Net **只预测逐像素亮度增量，不重建图像** → 纹理 100% 保留 `[核实]`
   - 这是"别让模型重画像素，只让它预测一张增益图"的直接答案
4. ICCV 2025 FSR+MRF：频域量化 + 拉普拉斯金字塔融合，解决"全局一致 vs 局部细节"两难，**放出 25,000 对修图前后基准数据** `[核实]`

### B. 光影

**成因**：前景/背景光照统计不兼容、缺阴影或阴影方向错、前景未受背景环境光染色（color bleeding 缺失）、拼接处黑位/对比度不同源。`[核实]`

**解法**：
- **IC-Light**（可控光方向的重打光）`[核实]`
- **libcom** 工具箱：blending / harmonization / shadow generation / object placement 等 10+ 函数，`pip install libcom` `[核实]`
- ⚠️ Poisson blending 会让背景色渗入前景导致前景失真，注意副作用 `[核实]`
- **【重要推断】影楼场景最有效的不是生成式 relight，而是「先统一拍摄光位」（棚拍固定主光），再只做 harmonization 微调。** 这直接呼应 Retouch4me 的第一条结论："不要用修图救烂原片，AI 只会放大问题"。`[核实]`

### C. 边缘与融合

**成因**：锯齿边界、发丝半透明、运动模糊导致边界色晕；分辨率/锐度/噪点前后景不一致。`[核实]`

**解法**：严格按 **matting → blending → harmonization** 顺序 `[核实]`；**噪声/颗粒匹配是最后一步硬要求**（按目标区域采样颗粒）`[核实]`。

### D. 几何与比例

**成因**：头身比/肩宽失调、手指畸形、耳齿崩坏。`[核实]`

**解法**：ControlNet（tile / softedge 锁结构，depth 锁几何）+ 人体关键点约束。`[推断]`

### E. 色彩与色调（影楼交付的硬伤）

**成因**：同一次拍摄的多张图肤色/色温漂移 = **交付级事故**。`[核实]`

**解法**：
- ΔE00 是标准度量 `[核实]`
- **参考图驱动的批量色调一致性引擎**（如开源 ECHO：本地运行、参考标准驱动色彩视觉一致性）`[核实]`

### F. 细节崩坏

眼睛高光/瞳孔不对称、牙齿数量、首饰眼镜结构、文字乱码。`[核实]`

**解法**：必须**局部重绘 + 人工点检**，绝不整图重生成。`[推断]`

### G. AI 味

过度锐化 / HDR 感（AI upscaling 的光晕与过度锐化已被明确讨论 `[核实]`）、对称性过强、过度饱和、同模型千人一面。`[核实/推断混合]`

---

## 四、为什么商业修图软件比通用大模型自然

| 工具 | 技术路线 | 关键点 |
|---|---|---|
| **Retouch4me** | 专用小模型按任务拆分（Heal / Dodge&Burn / Face Make / Portrait Volumes） | 算法由职业修图师定义"**纹理不是瑕疵**"；频率分离的 AI 化 |
| **Evoto** | 人像修饰模块 + 蒙版/局部调整，分区处理 | 分区而非全局 |
| **Aftershoot** | **加性混合图**：6MB U-Net 预测 Dodge&Burn 增量，不重建图像 | 纹理保真是其核心卖点（AAAI-26） |
| **Luminar Neo** | 生成式工具（GenErase/GenSwap）作为独立功能，不接管全图 | 不整图重绘 |
| **Topaz Photo AI** | 分任务模型（降噪/放大/**面部恢复是独立小模型**） | 面部恢复不全局重绘 |
| **美图云修 / 百度网盘 AI 修图** | 商业摄影流水线：1 小时精修 1000 张 | 已验证量产形态 |

### ★ 它们的共同点（这就是答案）

> **窄任务监督模型 + 面部区域分割 + 只输出增量而非重建 + 强度默认低于 100%**

强度共识 `[核实]`：Retouch4me 专家建议跑 **60–70%**；Dodge&Burn 跑 100% 后把混合不透明度**降到 50%**。

**这一条比选哪个大模型重要得多。** 你的技术栈重心应该是「专用小模型 + 增量式调整」，而不是「通用大模型一句话修图」。

---

## 五、可直接执行的参数清单

生成式编辑保质感的硬参数 `[核实/推断]`：

1. **denoise strength 0.25–0.45** —— 只修斑点，不重画皮肤
2. **mask 只覆盖目标区域**，feather 3–8px，**避免 mask 跨过面部轮廓线**
3. **ControlNet tile + softedge** 锁结构；**depth** 锁几何
4. **CFG 降到 4–6**（过高会过饱和、过锐）
5. **refiner / 二段低 denoise** 细化
6. **全程 tiled / regional，禁止整图 img2img**
7. **最后一步：噪点匹配 + 降回真实锐度**
8. **强度默认 60–70%**，不要 100%

### 修图专用 LoRA（开源，效果未亲测）`[核实存在]`
- `qwen-edit-apps/qwen-image-edit-plus-lora-skin`（Replicate）
- `tlennon-ie/qwen-edit-skin`
- `PrunaAI/p-image-edit-skin-retouching-lora`（HuggingFace）

---

## 六、客观质检：把"自然不自然"变成可测量的指标

这是把副业做成**可交付**的关键——不靠肉眼争论。

| 指标 | 用途 | 阈值建议 |
|---|---|---|
| **肤色 ΔE00** | 同组图两两对比 + 对参考图 | 组内漂移应 < 2 `[推断]` |
| **面部区域 SSIM / LPIPS** | 对原图，防结构漂移 | 需保留结构相似度 |
| **高频层纹理熵** | 频率分离后 HF 层熵值**不得显著低于原图** → 防塑料化 | `[推断]` |
| **噪点功率谱一致性** | 前景 vs 背景 | `[核实]` |
| **BRISQUE / NIQE** | 无参考质量分 | `[核实]` |

**落地建议**：写一个自动质检脚本，出图后自动跑这几项，超阈值就报警。这一条能挡掉大部分"过度修图"投诉——Retouch4me 明确指出**在交付尺寸上验收**这一步能挡掉大多数投诉。`[核实]`

---

## 七、影楼交付：AI 能替代什么，必须人工做什么

| 环节 | AI 可替代 | 说明 |
|---|---|---|
| 初选 / 挑片（culling） | ✅ | |
| 基础曝光色彩 | ✅ | |
| 批量磨皮祛斑 | ✅ | 但必须用频率分离 + 纹理回注 |
| 背景清理 | ✅ | |
| 尺寸输出 | ✅ | |
| 同组色调统一 | ✅ | 需 ΔE00 质检兜底 |
| **光位设计与原片质量把关** | ❌ **人工** | **决定上限** |
| **Dodge&Burn 塑形** | ⚠️ 半自动 | AI 能预测增量，但强度与意图需人定 |
| **五官 / 形体微调** | ❌ 人工 | |
| **细节崩坏修复** | ❌ 人工 | |
| **交付尺寸上的最终验收** | ❌ 人工 | 最能挡投诉的一步 |

### 可落地的商业模式（结论）

> **不是"AI 替代影楼"，而是「专业软件做 80% 批处理 + 人做 20% 关键帧精修 + 客观质检脚本兜底」。**

---

## 八、给你的行动优先级

按"1–2 周内能落地、改观最大"排序：

1. **立刻换掉"一句话整图重生成"的做法** —— 这是当前违和感的最大来源，也是唯一零成本就能改的。
2. **强度默认降到 60–70%**，denoise 0.25–0.45，mask 只覆盖斑点。
3. **引入频率分离**（先用 PS 手动流程验证效果，再考虑自动化）。
4. **上客观质检脚本**（ΔE00 + 纹理熵 + 噪点一致性），把验收标准化。
5. **评估 Retouch4me / Evoto 这类专用工具**，与你的 AI 流水线组合，而不是试图用大模型替代它们。
6. **最后才考虑自研增量预测模型**（加性混合图路线，AAAI-26 已开源思路）。

---

## 关键来源

- [Retouch4me：为什么修过的皮肤看起来假](https://retouch4.me/blog/why-retouched-skin-looks-fake-and-how-to-avoid-it)
- [Adobe：频率分离官方步骤](https://www.adobe.com/products/photoshop/frequency-separation.html)
- [AAAI-26：加性混合图纹理保真修图](https://ojs.aaai.org/index.php/AAAI/article/view/41481)
- [ICCV 2025：Face Retouching with Spectral Restorement](https://openaccess.thecvf.com/content/ICCV2025/html/Xu_Face_Retouching_with_Diffusion_Data_Generation_and_Spectral_Restorement_ICCV_2025_paper.html)
- [深度图像合成综述（三类不一致）](https://arxiv.org/abs/2106.14490)
- [IC-Light 重打光](https://github.com/lllyasviel/IC-Light)
- [libcom 合成工具箱](https://pypi.org/project/libcom/)
- [ComfyUI denoise strength](https://theneuralbase.com/comfyui/learn/intermediate/denoise-strength/)
- [Qwen 修图 LoRA](https://replicate.com/qwen-edit-apps/qwen-image-edit-plus-lora-skin)
- [Evoto 皮肤修饰](https://support.evoto.ai/skin-retouching/)
- [Topaz 分任务模型](https://docs.topazlabs.com/topaz-photo/release-summary)
- [Luminar 生成式工具](https://support.skylum.com/luminar-neo-tips/generative-tools-in-luminar-neo-everything-you-need-to-know)
- [美图云修](https://yunxiu.meitu.com/home)
- [百度网盘 AI 修图工作流](https://www.geekpark.net/news/368016)
- [常见 AI 伪影与修复](https://www.cliprise.app/learn/guides/best-practices/common-ai-image-artifacts-fixes)
- [AI 放大为何更糟](https://letsenhance.io/blog/all/ai-upscaling-makes-images-worse/)
- [ECHO 色调一致性引擎](https://github.com/x9c4gqtpv4-coder/ECHO)
- [生成图人体畸形评估](https://arxiv.org/abs/2503.00811)
- [ΔE00 度量实践](https://www.imatest.com/wp-content/uploads/2026/04/IQSP-247_EI2026_Paper_FINAL.pdf)
