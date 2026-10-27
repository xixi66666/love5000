# 主流图片大模型横向对比与成本测算

> 服务于「AI 修图副业」的选型与定价决策。
> **读取时点**：2026-10-21　**汇率**：1 USD = 7.10 CNY（阿里云计费页换算约 7.27，此处保守取 7.10）
> **可信度**：`[核实]` 有公开来源页｜`[估算]` 由已核实单价折算或工程推断｜`[未核实]` 无可靠来源，**不得当事实引用**
> ⚠️ 该领域迭代极快：FLUX.1 Kontext 已进 Legacy、Seedream 5.0 取代 4.5、GPT Image 2.5 有模型无公开价。**落地前必须重新核价。**
>
> 配套工作簿：[AI修图模型对比与成本测算.xlsx](AI修图模型对比与成本测算.xlsx)（改汇率/张数自动重算）

---

## 一、先纠正型号认知（直接影响选型）

对比早期版本，有 9 处需要修正，其中 4 处会导致你选到已淘汰的模型：

| 早期认知 | 实际情况 | 结论 |
|---|---|---|
| Google「Gemini 3 Pro Image / gemini-3-flash-image」 | 现役为 **Nano Banana Pro = Gemini 3 Pro Image**、**Nano Banana 2 = Gemini 3.1 Flash Image**，另有 2.1 / 2 Lite | 已换代 |
| OpenAI「gpt-image-2.5」 | fal 目录有 **GPT Image 2.5**，但**无公开单价**；可核实的是 **GPT Image 2** 全档价目 | ⚠️ **2.5 报价【未核实】，别写进报价单** |
| BFL「FLUX.1 Kontext [pro]/[max]」 | **已进 Legacy Models，无现役报价** | ❌ **新项目别选** |
| 字节「Seedream 4.5」 | 现役旗舰是 **Seedream 5.0 pro/flash/lite** | 4.5 已非旗舰但仍划算 |
| 阿里「qwen-image-3.0-pro」 | 存在，官方计费页确认；`qwen-image-edit` 仍属 2.0 世代 | 建议直接用 3.0 二合一 |
| 「Imagen 系列」 | Firebase 有 Imagen→Nano Banana 迁移文档 | **视为停产/迁移中** |
| 「可图 Kolors」 | 快手主线已转可灵 Kling，无现役报价 | **停更/边缘化，不建议接入** |
| 「Midjourney v7/v8」 | 官方页 403 / Cloudflare 拦截 | 订阅价【未核实】 |
| 开源可自建「FLUX.1 Kontext [dev]」 | 权重仍在，但官方已转 API 优先 | 自建可行性下降 |

---

## 二、主对比表

### 2.1 Google / OpenAI

| 模型 | 指令编辑 | mask | 多图参考 | 分辨率 | 单价 | 折人民币 | 一句话 |
|---|---|---|---|---|---|---|---|
| **Nano Banana Pro (1K–2K)** | ✅ | ✅ | **≤14 张** | 1K/2K/4K | **$0.15** `[核实]` | **¥1.07** | 人像一致性天花板，可跨代保持 **5 人身份**；带 SynthID 水印 |
| Nano Banana Pro (4K) | ✅ | ✅ | ≤14 张 | 4K | $0.30 `[核实]` | ¥2.13 | web search 另加 $0.015 |
| Nano Banana 2 (512²) | ✅ | ✅ | ≤14 张 | 0.5K–4K | $0.06 `[核实]` | ¥0.43 | 廉价草稿档 |
| **Nano Banana 2 (1K)** | ✅ | ✅ | ≤14 张 | 0.5K–4K | **$0.08** `[核实]` | **¥0.57** | ★**主力首选**：性价比与质量的平衡点 |
| Nano Banana 2 (2K) | ✅ | ✅ | ≤14 张 | 0.5K–4K | $0.12 `[核实]` | ¥0.85 | |
| **Nano Banana 2 (4K)** | ✅ | ✅ | ≤14 张 | 4K | **$0.16** `[核实]` | **¥1.14** | ★4K 比 Pro 便宜一半 |
| Nano Banana 2.1 / 2 Lite | ✅ | 【未】 | 【未】 | 【未】 | ≈$0.03 `[估算]` | ≈¥0.21 | OpenRouter 按 token 折算，议价空间大 |
| **gpt-image-2 (1024 low)** | ✅ | ✅ | image_urls | 最大边 3840 | **$0.006** `[核实]` | **¥0.04** | ★试稿档，最便宜 |
| gpt-image-2 (1024 medium) | ✅ | ✅ | 同上 | 最大边 3840 | $0.053 `[核实]` | ¥0.38 | 定稿档 |
| gpt-image-2 (1920×1080 high) | ✅ | ✅ | 同上 | 最大边 3840 | $0.158 `[核实]` | ¥1.12 | |
| gpt-image-2 (2560×1440 high) | ✅ | ✅ | 同上 | 最大边 3840 | $0.222 `[核实]` | ¥1.58 | |
| gpt-image-2 (3840×2160 high) | ✅ | ✅ | 同上 | 3840×2160 | $0.401 `[核实]` | ¥2.85 | |
| gpt-image-2 (1024 high 编辑) | ✅ | ✅ | 同上 | 最大边 3840 | $0.219 `[核实]` | ¥1.56 | 编辑另加一张输入图费 |
| GPT Image 2.5 | 【未】 | 【未】 | 【未】 | 【未】 | **【未核实】** | — | ⚠️ 需登录 fal 控制台确认 |

> **gpt-image-2 是唯一支持像素级 mask 的模型**（白=可改 / 黑=保留）。
> 价格来自 fal 档位表——OpenAI 官方页对本网络 403，**这是当前唯一完整可核实的 gpt-image-2 价格表**（标注为 token 换算投影值）。

### 2.2 Black Forest Labs（官方价）

| 模型 | 多图参考 | 计费 | 1MP 折算 | 一句话 |
|---|---|---|---|---|
| **FLUX.2 [pro]** | ≤8 张 | 首 MP **$0.0375**、后续 $0.005；参考 $0.005/MP `[核实]` | **¥0.27** | ★**批量修图性价比极佳** |
| FLUX.2 [max] | **≤10 张**（`@image1` 语法） | 首 MP $0.07、后续 $0.03；参考 $0.03/MP `[核实]` | ¥0.50 | 品牌色/JSON 提示词强；实测多图编辑易漏改 |
| FLUX.2 [flex] | 【未】 | 生成/参考均 $0.05/MP `[核实]` | ¥0.36 | 单档定价，预算可预测 |
| **FLUX.2 [klein] 4B** | 【未】 | 首 MP **$0.014**、后续 $0.001 `[核实]` | **¥0.10** | ★**廉价量产档**，另有自托管授权 |
| FLUX.2 [klein] 9B | 【未】 | 首 MP $0.03、后续 $0.015 `[核实]` | ¥0.21 | |
| **FLUX 3 Image** | 【未】 | fal $0.024/MP `[核实]` | **¥0.17** | 新代，**低于 FLUX.2 [pro] 官方价** |
| **FLUX Eraser** | — | 首 MP $0.03；参考 $0.004/MP `[核实]` | ¥0.21 | ★去水印/去杂物，老照片修复主力 |
| FLUX Deblur / Outpainting | — | 扩图首 MP $0.045 `[核实]` | ¥0.32 | 模糊修复 / 扩图 |
| ~~FLUX.1 Kontext [pro]/[max]~~ | — | **已 Legacy，无现役报价** | — | ❌ 存量兼容，新项目别选 |

> **FLUX 授权要点**：非商用许可限制的是**模型本身**，**生成结果（Outputs）可用于商业目的**。
> 自托管商用必须买 Self-Hosted 授权，且该授权**明确禁止以 API 形式转售**。详见 §五。

### 2.3 国内可直连（成本优势明显）

| 模型 | 指令编辑 | mask | 多图参考 | 分辨率 | 官方价 | 折人民币 | 限流 | 一句话 |
|---|---|---|---|---|---|---|---|---|
| **Seedream 5.0 pro (≤261万px)** | ✅ 坐标/框选/箭头标注 | ✅ 标注框 | **2–10 张** | 1K/1.5K/2K | **¥0.30** `[核实]` | **¥0.30** | 【未】 | ★**国内链路最强**；14 语言文字 + 图层拆分；输入图首张免费，第 2 张起 ¥0.02 |
| Seedream 5.0 pro (>261万px) | ✅ | ✅ | 2–10 张 | 1K/1.5K/2K | ¥0.60 `[核实]` | ¥0.60 | 【未】 | |
| Seedream 5.0 pro (图层拆分) | ✅ | ✅ | 2–10 张 | — | ¥0.15 `[核实]` | ¥0.15 | 【未】 | 图层级编辑 |
| Seedream 5.0 flash | ✅ | 【未】 | 【未】 | 【未】 | ¥0.12 `[核实]` | ¥0.12 | 【未】 | 廉价量产 |
| Seedream 5.0 lite | ✅ | 【未】 | 【未】 | 2K/3K/4K | ¥0.22 `[核实]` | ¥0.22 | 【未】 | |
| Seedream 4.5 | ✅ | 【未】 | ≤14 张 | 2K/4K | ¥0.25 `[核实]` | ¥0.25 | 【未】 | 已非旗舰但仍划算 |
| Seedream 4.0 | ✅ | 【未】 | ≤10 张 | 1K/2K/4K | ¥0.20 `[核实]` | ¥0.20 | 【未】 | |
| **qwen-image-3.0-pro (1K)** | ✅ 生成+编辑二合一 | 【未】 | 【未】 | 512²–2048² | ¥0.25 生成 + ¥0.02 输入 `[核实]` | ¥0.27 | ⚠️ **RPM 5** | ❌ **RPM 5 是致命瓶颈**（≈300 张/小时），**无法批量** |
| qwen-image-3.0-pro (2K) | ✅ | 【未】 | 【未】 | 512²–2048² | ¥0.50 + ¥0.02 `[核实]` | ¥0.52 | ⚠️ RPM 5 | 无 4K |
| **wan2.7-image-pro** | ✅ 交互编辑 | 【未】 | 支持 | 【未】 | ¥0.50 `[核实]` | ¥0.50 | ✅ **RPM 300** | 高并发场景比 Qwen 稳得多 |
| 腾讯混元生图 3.0 | ✅ 风格化/消除/扩图 | ✅ | 【未】 | 【未】 | **¥0.20** `[核实]` | ¥0.20 | ⚠️ **默认并发 1** | |
| **腾讯混元 极速版** | ✅ 风格化 | ✅ | 【未】 | 【未】 | **¥0.066** `[核实]` | **¥0.066** | 默认并发 3 | ★**最便宜的可用档** |
| 腾讯混元 AI 写真 | ✅ | 【未】 | 【未】 | 【未】 | ¥0.24 `[核实]` | ¥0.24 | 默认并发 1 | 人像专用线 |
| 腾讯混元 模特换装 | ✅ | 【未】 | 【未】 | 【未】 | ¥0.50 `[核实]` | ¥0.50 | 默认并发 1 | 电商换装专用 |
| **腾讯混元 商品背景** | ✅ | 【未】 | 【未】 | 【未】 | **¥0.07** `[核实]` | **¥0.07** | 默认并发 1 | ★电商白底/场景图 |
| 腾讯混元 百变头像 | ✅ | 【未】 | 【未】 | 【未】 | ¥0.099 `[核实]` | ¥0.099 | 默认并发 1 | |

> ⚠️ **腾讯混元的默认并发是 1** —— 想批量必须买并发叠加包（**¥500/并发/天** 或 **¥10,000/并发/月**）。
> 混元正迁移至 TokenHub，原平台不再新增能力。

### 2.4 其他与订阅制工具

| 服务 | 单价 | 说明 |
|---|---|---|
| Recraft V4.1 Flash | **$0.007** `[核实]` | ★最便宜的栅格档 |
| Recraft V4.1 / V4 栅格 | $0.035–0.04 `[核实]` | 图生图/修补/扩图 $0.04，老照片修复性价比高 |
| Recraft 2K Pro 栅格 | $0.21–0.25 `[核实]` | |
| flux-schnell (Replicate) | **$3.00/千张 = $0.003** `[核实]` | ★廉价档标杆 |
| Z Image Turbo (fal) | $0.005/MP `[核实]` | |
| Replicate flux-1.1-pro / flux-dev | $0.04 / $0.025 `[核实]` | |
| **Topaz Photo/Web** | **$12/月**（$19 折后）`[核实]` | ★**本地渲染无限**，32MP/100MP 导出，2–4 并发；修图副业最划算的保底工具 |
| Magnific | €10.5/月起（24 万 credits/年）`[核实]` | 订阅制放大/精修，**不用你的数据训练** |
| Ideogram v3 quality | $0.09 `[核实]` | 仅 Replicate 可核 |
| Photoshop API v2 | **【未核实】** | 企业 rate card 有登录墙 |
| Midjourney / Krea / Remini / 美图 | **【未核实】** | 站点 403 或无公开价目页，**不要凭印象写价** |

---

## 三、性价比分层

| 档次 | 单张成本 | 代表 | 适用零售价位 |
|---|---|---|---|
| **顶级画质** | ¥1.07–2.85 | Nano Banana Pro（¥1.07 / 4K ¥2.13）、gpt-image-2 high（¥1.12–2.85）、FLUX.2 [max]（¥0.50 起） | 单张零售 ≥¥30：写真、婚纱、商业人像、封面级 |
| **性价比主力** | ¥0.25–1.14 | **Nano Banana 2（¥0.43–1.14）**、**Seedream 5.0 pro（¥0.30–0.60）**、FLUX.2 [pro]（¥0.27）、gpt-image-2 medium（¥0.38）、FLUX 3 Image（¥0.17）、Seedream 4.5（¥0.25） | 单张零售 ¥5–30：证件照、电商图、批量精修 |
| **廉价量产** | ¥0.02–0.22 | **腾讯混元极速版（¥0.066）**、flux-schnell（¥0.02）、FLUX.2 [klein] 4B（¥0.10）、Recraft Flash（¥0.05）、gpt-image-2 low（¥0.04）、Seedream 5.0 flash（¥0.12） | 单张零售 <¥5：预览图、缩略图、AI 初筛、海选返图 |

**选型结论**：**主体交付走「主力档」+ 顶级档点缀（20 张里 3–5 张进顶级档），是毛利最优结构。**

---

## 四、副业定价测算

假设：1 张图 = 1 次生成，不含重试。**实际务必乘 1.3–1.8 重试系数（估算）**。

| 模型 | 单张 | 20 张 | 50 张 | 100 张 | 建议零售/张 | 零售÷成本 |
|---|---|---|---|---|---|---|
| 腾讯混元极速版 | ¥0.066 | ¥1.3 | ¥3.3 | ¥6.6 | ¥5 | **≈76×** |
| flux-schnell | ¥0.021 | ¥0.4 | ¥1.1 | ¥2.1 | ¥5 | ≈235× |
| FLUX.2 [klein] 4B | ¥0.099 | ¥2.0 | ¥5.0 | ¥9.9 | ¥5 | **≈50×** |
| **FLUX.2 [pro]** | **¥0.266** | ¥5.3 | **¥13.3** | ¥26.6 | ¥15 | **≈56×** |
| **Seedream 5.0 pro** | **¥0.30** | ¥6.0 | **¥15.0** | ¥30.0 | ¥15 | **≈50×** |
| qwen-image-3.0-pro 1K | ¥0.27 | ¥5.4 | ¥13.5 | ¥27.0 | ¥15 | ≈56%（但 RPM 5 限速） |
| gpt-image-2 medium | ¥0.38 | ¥7.5 | ¥18.8 | ¥37.6 | ¥20 | ≈53× |
| **Nano Banana 2 @1K** | **¥0.57** | ¥11.4 | **¥28.4** | ¥56.8 | ¥25 | **≈44×** |
| Nano Banana Pro | ¥1.07 | ¥21.3 | ¥53.3 | ¥106.5 | ¥60 | ≈56× |
| Nano Banana Pro @4K | ¥2.13 | ¥42.6 | ¥106.5 | ¥213.0 | ¥120 | ≈56× |
| gpt-image-2 high 4K | ¥2.85 | ¥57.0 | ¥142.4 | ¥284.7 | ¥180 | ≈63× |

### 四条关键结论

1. **API 成本占零售价仅 2%–5%（廉价档）到 5%–12%（顶级档）** —— **API 成本绝不是瓶颈。**
2. **真正的成本是人工挑图与返修**：一单 2 小时人工（时薪 ¥50 = ¥100）已经超过 **100 张顶级档 API 总额（¥213）的 47%**。
3. **不要为省 API 钱牺牲画质。** 降本点在**减少无效生成**：用 `low` 档试稿 + `high` 档定稿的两段式，比 3 次直接 `high` 重试便宜约 3 倍`[估算]`。
4. **限流比价格更容易卡死业务**（见 §六）。

---

## 五、⚠️ 授权陷阱（比价格更重要）

### FLUX 系列的反直觉规则 `[核实]`
- 非商用许可限制的是**模型本身**，**生成结果（Outputs）可用于商业目的**。
- 自托管商用必须购买 Self-Hosted 授权，且该授权**明确禁止以 API 形式转售**。

| 情形 | 合规性 |
|---|---|
| 调 BFL 官方 API 出图，卖给客户 | ✅ 合规（产出物可商用） |
| 自建服务跑 FLUX 权重，内部修图卖给客户 | ⚠️ 需购买 Self-Hosted 授权 |
| 自建服务跑 FLUX 权重，**包装成 API 转售** | ❌ 即使买了授权，也**禁止 API 转售** |
| 当前 `base-url` 指向第三方代理，在其上再包一层对外 | ⚠️ **需确认该代理的授权链与转售条款** |

### 开源可商用编辑模型（若走自建）
| 模型 | 许可 | 可商用 |
|---|---|---|
| **Qwen-Image-Edit-2509** | Apache-2.0 | ✅ **首选** |
| BAGEL-7B-MoT（字节 7B） | Apache-2.0 | ✅ |

### 专用小模型许可审计
| 模型 | 许可 | 可商用 | 任务 |
|---|---|---|---|
| **Real-ESRGAN** | BSD-3-Clause | ✅ | 超分 / 老照片修复 |
| **BiRefNet** | MIT | ✅ | 抠图（软 Alpha，发丝最优） |
| **SAM 2** | Apache-2.0 | ✅ | 分割（硬掩码，交互式点选） |
| LaMa | Apache-2.0 | ✅ | 规则化 inpainting |
| **GFPGAN** | Apache-2.0 **但含 DFDNet 等 CC BY-NC-SA 4.0 组件** | ⚠️ **需逐组件审计** | 人脸修复 |
| **CodeFormer** | S-Lab License 1.0 | ❌ **非商用** | 人脸修复 |
| **RMBG-2.0** | bria-rmbg-2.0 自定义 | ❌ **非商用** | 抠图 |

> **审计方法**：`GET https://api.github.com/repos/{owner}/{repo}/license` 返回 SPDX ID，比读 README 可靠。

---

## 六、限流与工程约束（比价格更容易卡死业务）

| 服务 | 限制 | 对业务的影响 |
|---|---|---|
| **qwen-image-3.0-pro** | **RPM 5**（各区域一致）`[核实]` | 天花板 **≈300 张/小时** → **无法批量**，直接排除 |
| **腾讯混元** | **默认并发 1**（风格化 3）`[核实]` | 想批量必须买叠加包：**¥500/并发/天** 或 **¥10,000/并发/月** |
| wan2.7-image-pro | RPM 300 `[核实]` | 高并发场景的唯一国内稳妥选择 |
| BFL 多数端点 | 24 并发 | 可用但需节流 |
| FLUX `kontext-max` | 仅 6 并发 | 已 Legacy，不再考虑 |
| Google / OpenAI | 【未核实】 | — |

**其他必踩的坑** `[核实]`：
1. **返回形态分裂**：OpenAI 返回 `b64_json`（响应体极大，String 接收会 OOM）；BFL/WaveSpeed/阿里返回**短时效签名 URL**——**BFL 仅 10 分钟有效、无 CORS、禁止直连终端用户**，必须服务端立即下载转存。
2. **异步是常态**：BFL/WaveSpeed/腾讯/火山均为 submit + poll；BFL 支持 webhook + 签名头。
3. **分辨率注水**：Kontext 输出恒约 1MP；很多标称「4K」的实际是 2048²。
4. **审核双向误杀且无申诉通道**：prompt 与输出都会被拦，**不可承诺「指定明星换装」**。
5. **水印**：Google 生成图带 **SynthID**；腾讯混元 `LogoAdd` 默认 = 1，会自动加「AI生成」水印——**合规上反而省事**。
6. **Adobe Photoshop API v1 已于 2026-07-31 EOL**，新集成必须直接上 v2。

---

## 七、聚合平台价差

| 模型 | 官方 | fal.ai | Replicate | OpenRouter | 判断 |
|---|---|---|---|---|---|
| FLUX.2 [pro] | $0.0375/MP | 未见独立表价 | 需登录 | — | fal 文章称「$0.03/首 MP」，略低（口径差异）`[估算]` |
| **FLUX 3 Image** | 官方有计算器 | **$0.024/MP** | 【未】 | 【未】 | ★**换新代可降本**：低于 FLUX.2 [pro] 官方价 |
| Nano Banana Pro | 官方页不可达 | **$0.15 / 4K $0.30** | 需登录 | $0.00012/token | OpenRouter 单张约 $0.12–0.24（随 token 浮动）`[估算]` |
| gpt-image-2 | 官方页 403 | **高/中/低全表** | 【未】 | 【未】 | fal 是**当前唯一公开可核实**的档位表 |
| recraft-v3 | $0.04/栅格 | 【未】 | $0.04/张 | — | **一致，无加价** |
| ideogram-v3-quality | 官网不可达 | 有端点 | $0.09/张 | — | 仅 Replicate 可核 |
| flux-schnell | — | — | $3.00/千张 | — | 廉价档标杆 |

**价差结论**
1. **fal.ai 基本按官方价转售**，FLUX 3 甚至更便宜；价格透明度最高（机器可读 + 公开定价页）。
2. **Replicate** 对开源/第三方模型与官方一致，但**闭源旗舰（Nano Banana Pro / GPT Image 2 / Seedream）要求自带 Key（BYOK）**，不补贴。
3. **OpenRouter 图像按 token 而非按张计费**，同模型不同分辨率成本漂移 → **不适合固定单价报价**，适合容灾。
4. **统一接入建议**：**fal.ai 为主 + 火山方舟/腾讯混元 为辅（成本低一个数量级）+ OpenRouter 兜底**。

---

## 八、按场景推荐

| 场景 | 首选 | 备选 | 不要用 |
|---|---|---|---|
| **① 老照片修复**（划痕/模糊/上色） | **FLUX.2 [pro] + FLUX Eraser / Deblur / Outpainting**（¥0.21–0.32） | Recraft 图生图/修补 ¥0.28；混元局部消除/扩图（限时免费） | 纯文生图大模型（脸会漂移）；MJ（无 mask） |
| **② 证件照**（换底/换装/合规） | **混元 模特换装 ¥0.5 + 百变头像 ¥0.099 + 商品背景 ¥0.12** | Seedream 5.0 pro 图层拆分 ¥0.15；gpt-image-2 mask 编辑 | Midjourney、Recraft（规格与肤色一致性不可控） |
| **③ 人像精修 / 写真** | **Nano Banana Pro**（¥1.07，5 人 ID 保持，≤14 参考） | Seedream 5.0 pro ¥0.30（国内链路）；混元 AI 写真 ¥0.24 | gpt-image-1 老接口；qwen-3.0-pro（RPM 5 撑不住一组） |
| **④ 婚纱照风格化** | **Nano Banana 2**（¥0.57，4K 仅 ¥1.14，快 2–3×） | FLUX.2 [max]（品牌色强）；Seedream 4.5 ¥0.25 | 廉价档（klein 4B / 混元极速版）会丢脸 |
| **⑤ 电商白底图 / 换背景** | **FLUX.2 [pro]**（¥0.27，≤8 参考）或 **混元商品背景 ¥0.07** | gpt-image-2 低/中质量（¥0.04–0.38，唯一能分级压价） | 高价 4K 高质量（¥2.85 纯浪费） |
| **⑥ 批量出片（100+ 张/单）** | **FLUX.2 [klein] 4B（¥0.10）+ 混元极速版 ¥0.066** | Seedream 5.0 flash ¥0.12；NB2 @512² ¥0.43 | qwen-3.0-pro（RPM 5）；混元默认并发 1（不买叠加包无法批量） |

> ⚠️ **证件照是硬规格场景**：官方明文要求护照照片「不得对照片进行修改，不得使用合成照片」，
> 多地报名系统已禁用精修证件照。**价值在「合规裁切 + 换底色」，不在美颜。**

---

## 九、立刻排除的选项

| 排除对象 | 原因 |
|---|---|
| **qwen-image-3.0-pro** | RPM 5，约 300 张/小时天花板，无法批量 |
| **FLUX.1 Kontext [pro]/[max]** | 已进 Legacy，无现役报价 |
| **可图 Kolors** | 快手主线转可灵，停更/边缘化 |
| **gpt-image-1 系列** | 已被 2 代取代，仅兼容 |
| **Imagen 系列** | 有迁移文档，视为停产/迁移中 |
| **GPT Image 2.5 报价** | 有模型无公开单价，**不得写进报价单** |

---

## 十、待核实清单（对外引用前必须补）

- [ ] OpenAI 官方 gpt-image-2 / 2.5 原始单价（当前 403）
- [ ] Google 官方 Nano Banana Pro/2 原始单价（当前不可达，仅 fal 可核）
- [ ] Midjourney 订阅价、Adobe Firefly / Photoshop API v2 按量价（均需登录）
- [ ] Krea / Remini / 美图开放平台（无公开按量价目页）
- [ ] Qwen-Image-Edit-2509 量化后实际显存与速度
- [ ] 混元迁移至 TokenHub 后的价格与能力变化
- [ ] 各服务的实际并发上限与 SLA（Google/OpenAI 均未核实）

---

## 关键来源 URL

**定价**
- [fal.ai 定价表](https://fal.ai/pricing)｜[Nano Banana Pro](https://fal.ai/models/fal-ai/nano-banana-pro)｜[gpt-image-2](https://fal.ai/models/openai/gpt-image-2)
- [BFL 官方定价](https://bfl.ai/pricing)｜[BFL 文档定价](https://docs.bfl.ai/quick_start/pricing)
- [火山方舟模型价格](https://www.volcengine.com/docs/82379/1544106)
- [阿里云 qwen-image-3.0-pro 计费](https://help.aliyun.com/zh/model-studio/qwen-image-3-0-pro)｜[wan2.7-image-pro](https://www.alibabacloud.com/help/en/model-studio/wan2-7-image-pro)
- [腾讯混元生图计费](https://cloud.tencent.com/document/product/1668/90896)
- [Recraft API 定价](https://www.recraft.ai/docs/api-reference/pricing)｜[Replicate 定价](https://replicate.com/pricing)｜[OpenRouter models](https://openrouter.ai/api/v1/models)
- [Topaz 定价](https://www.topazlabs.com/pricing)｜[Magnific 定价](https://magnific.ai/pricing)

**对比与迁移**
- [GPT Image 2 vs FLUX 2 Max](https://fal.ai/learn/tools/gpt-image-2-vs-flux-2-max)｜[GPT Image 2 vs Nano Banana 2](https://fal.ai/learn/tools/gpt-image-2-vs-nano-banana-2)
- [Seedream 5.0 Pro vs GPT Image 2](https://fal.ai/learn/devs/seedream-5-0-pro-vs-gpt-image-2)｜[Nano Banana Pro vs 2](https://fal.ai/learn/tools/nano-banana-pro-vs-nano-banana-2)
- [Imagen→Nano Banana 迁移](https://firebase.google.cn/docs/ai-logic/imagen-models-migration)

**许可**
- [FLUX 非商用许可 v2.0](https://bfl.ai/legal/non-commercial-license-terms)｜[FLUX 自托管商用授权](https://bfl.ai/legal/self-hosted-commercial-license-terms)
- [CodeFormer LICENSE（非商用）](https://github.com/sczhou/CodeFormer/blob/master/LICENSE)｜[BiRefNet LICENSE](https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE)
- [NVIDIA NIM 支持矩阵](https://docs.nvidia.com/nim/visual-genai/1.5.1/support-matrix.html)
