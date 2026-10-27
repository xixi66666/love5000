# -*- coding: utf-8 -*-
"""生成「AI 修图模型对比与成本测算」工作簿。

数据来源：四路调研核实项（读取时点 2026-10-21，汇率 1 USD = 7.10 CNY）。
设计要点：
  - 汇率集中在「模型对比」F1，改一处即可全表重算。
  - 「模型对比」H 列(原币单价)为静态值；J 列(人民币/张)为公式，引用 H 列 × 汇率（人民币行除外）。
  - 成本测算表 = 张数 × 人民币单价，改张数即重算，无循环引用。
  - P 列写 Python 独立复算的参考值，供公式重算前核对（本沙箱 LibreOffice 重算不可用）。
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = "docs/ai-retouch/AI修图模型对比与成本测算.xlsx"
RATE = 7.10

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
TITLE_FONT = Font(bold=True, size=11, color="1F3864")
NOTE_FONT = Font(size=9, italic=True, color="808080")
WARN_FILL = PatternFill("solid", fgColor="FCE4D6")
OK_FILL = PatternFill("solid", fgColor="E2EFDA")
LEGACY_FILL = PatternFill("solid", fgColor="D9D9D9")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

wb = Workbook()

# ============================================================================
# Sheet 1: 模型对比
# ============================================================================
ws = wb.active
ws.title = "模型对比"

headers = [
    "模型", "厂商", "指令式编辑", "mask", "多图参考", "多轮", "分辨率上限",
    "币种", "原币单价", "报价说明", "人民币/张", "限流", "商用授权", "核实状态", "备注",
]
NCOL = len(headers)

# 字段顺序: 模型, 厂商, 指令编辑, mask, 多图参考, 多轮, 分辨率,
#           币种, 原币单价, 报价说明, 限流, 商用授权, 核实状态, 备注
DATA = [
    # ---------- Google ----------
    ("Nano Banana Pro (1K-2K)", "Google", "是", "是", "≤14张", "是", "1K/2K/4K",
     "USD", 0.15, "fal 官方定价 $0.15/张(1K-2K)", "未核实", "commercial-use", "核实",
     "人像一致性天花板, 可跨代保持5人身份; SynthID水印"),
    ("Nano Banana Pro (4K)", "Google", "是", "是", "≤14张", "是", "4K",
     "USD", 0.30, "fal 官方定价 $0.30/张(4K)", "未核实", "commercial-use", "核实",
     "web search 另加 $0.015"),
    ("Nano Banana 2 (512²)", "Google", "是", "是", "≤14张", "是", "0.5K-4K",
     "USD", 0.06, "fal $0.06", "未核实", "commercial-use", "核实", "廉价草稿档"),
    ("Nano Banana 2 (1K)", "Google", "是", "是", "≤14张", "是", "0.5K-4K",
     "USD", 0.08, "fal $0.08", "未核实", "commercial-use", "核实",
     "★主力首选: 性价比与质量平衡点"),
    ("Nano Banana 2 (2K)", "Google", "是", "是", "≤14张", "是", "0.5K-4K",
     "USD", 0.12, "fal $0.12", "未核实", "commercial-use", "核实", ""),
    ("Nano Banana 2 (4K)", "Google", "是", "是", "≤14张", "是", "4K",
     "USD", 0.16, "fal $0.16", "未核实", "commercial-use", "核实",
     "4K 仅 ¥1.14, 比 Pro 便宜一半"),
    ("Nano Banana 2.1 / 2 Lite", "Google", "是", "未核实", "未核实", "是", "未核实",
     "USD", 0.03, "OpenRouter image_output $0.00003/token 折算", "未核实", "未核实", "估算",
     "新代 Flash 档, 议价空间大"),
    # ---------- OpenAI ----------
    ("gpt-image-2 (1024 low)", "OpenAI", "是", "是", "image_urls 未标上限", "是", "最大边3840",
     "USD", 0.006, "fal 档位表(low)", "未核实", "是(BYOK可行)", "核实", "试稿档"),
    ("gpt-image-2 (1024 medium)", "OpenAI", "是", "是", "同上", "是", "最大边3840",
     "USD", 0.053, "fal 档位表(medium)", "未核实", "是", "核实", "定稿档"),
    ("gpt-image-2 (1920x1080 high)", "OpenAI", "是", "是", "同上", "是", "最大边3840",
     "USD", 0.158, "fal 档位表(high)", "未核实", "是", "核实", ""),
    ("gpt-image-2 (2560x1440 high)", "OpenAI", "是", "是", "同上", "是", "最大边3840",
     "USD", 0.222, "fal 档位表(high)", "未核实", "是", "核实", ""),
    ("gpt-image-2 (3840x2160 high)", "OpenAI", "是", "是", "同上", "是", "3840x2160",
     "USD", 0.401, "fal 档位表(high 4K)", "未核实", "是", "核实",
     "★唯一支持像素级mask(白=可改/黑=保留); 编辑另加输入图费"),
    ("gpt-image-2 (1024 high 编辑)", "OpenAI", "是", "是", "同上", "是", "最大边3840",
     "USD", 0.219, "fal 含一张输入图", "未核实", "是", "核实", "编辑含输入图"),
    ("GPT Image 2.5", "OpenAI", "未核实", "未核实", "未核实", "未核实", "未核实",
     "USD", None, "fal 有模型但无公开单价", "未核实", "未核实", "未核实",
     "⚠需登录 fal 控制台确认, 勿写进报价单"),
    # ---------- BFL ----------
    ("FLUX.2 [pro] (1MP)", "BFL", "是", "否", "≤8张", "是", "至4MP",
     "USD", 0.0375, "首MP $0.0375, 后续$0.005; 参考$0.005/MP", "未核实",
     "产出可商用/模型非商用", "核实", "★批量修图性价比极佳"),
    ("FLUX.2 [max] (1MP)", "BFL", "是", "否", "≤10张", "是", "至4MP",
     "USD", 0.07, "首MP $0.07, 后续$0.03; 参考$0.03/MP", "未核实", "同上", "核实",
     "品牌色/JSON提示词强; 多图编辑易漏改"),
    ("FLUX.2 [flex] (1MP)", "BFL", "是", "否", "未核实", "是", "至4MP",
     "USD", 0.05, "生成/参考均 $0.05/MP", "未核实", "同上", "核实", "单档定价,预算可预测"),
    ("FLUX.2 [klein] 4B (1MP)", "BFL", "是", "否", "未核实", "是", "至4MP",
     "USD", 0.014, "首MP $0.014, 后续$0.001", "未核实", "同上", "核实",
     "★廉价量产档, 另有自托管授权"),
    ("FLUX.2 [klein] 9B (1MP)", "BFL", "是", "否", "未核实", "是", "至4MP",
     "USD", 0.03, "首MP $0.03, 后续$0.015", "未核实", "同上", "核实", ""),
    ("FLUX 3 Image (1MP)", "BFL", "是", "否", "未核实", "是", "至4K/16MP",
     "USD", 0.024, "fal $0.024/MP", "未核实", "同上", "核实", "新代, 低于 FLUX.2 [pro] 官方"),
    ("FLUX Eraser (1MP)", "BFL", "否", "是", "不适用", "否", "按输入",
     "USD", 0.03, "生成首MP $0.03; 参考$0.004/MP", "未核实", "同上", "核实",
     "去水印/去杂物; 老照片修复主力"),
    ("FLUX Deblur / Outpainting (1MP)", "BFL", "否", "是", "不适用", "否", "按输入",
     "USD", 0.045, "扩图首MP $0.045", "未核实", "同上", "核实", "模糊修复/扩图"),
    ("FLUX.1 Kontext [pro]", "BFL", "是", "否", "未核实", "是", "恒约1MP",
     "USD", None, "⚠ 已归 Legacy Models, 无现役报价", "未核实", "同上", "已淘汰",
     "❌ 存量兼容, 新项目别选"),
    # ---------- 字节 ----------
    ("Seedream 5.0 pro (≤261万px)", "字节", "是(坐标/框选)", "是(标注框)", "2-10张", "是", "1K/1.5K/2K",
     "CNY", 0.30, "火山方舟 ¥0.30/张", "未核实", "明确", "核实",
     "★国内链路最强; 输入图首张免费, 第2张起¥0.02"),
    ("Seedream 5.0 pro (>261万px)", "字节", "是", "是", "2-10张", "是", "1K/1.5K/2K",
     "CNY", 0.60, "火山方舟 ¥0.60/张", "未核实", "明确", "核实", ""),
    ("Seedream 5.0 pro (图层拆分)", "字节", "是", "是", "2-10张", "是", "1K/1.5K/2K",
     "CNY", 0.15, "火山方舟 ¥0.15/张", "未核实", "明确", "核实", "图层级编辑"),
    ("Seedream 5.0 flash", "字节", "是", "未核实", "未核实", "是", "未核实",
     "CNY", 0.12, "火山方舟 ¥0.12/张", "未核实", "明确", "核实", "廉价量产"),
    ("Seedream 5.0 lite", "字节", "是", "未核实", "未核实", "是", "2K/3K/4K",
     "CNY", 0.22, "火山方舟 ¥0.22/张", "未核实", "明确", "核实", ""),
    ("Seedream 4.5", "字节", "是", "未核实", "≤14张", "是", "2K/4K",
     "CNY", 0.25, "火山方舟 ¥0.25/张", "未核实", "明确", "核实", "已非旗舰但仍划算"),
    ("Seedream 4.0", "字节", "是", "未核实", "≤10张", "是", "1K/2K/4K",
     "CNY", 0.20, "火山方舟 ¥0.20/张", "未核实", "明确", "核实", ""),
    # ---------- 阿里 ----------
    ("qwen-image-3.0-pro (1K)", "阿里", "是(生成+编辑二合一)", "未核实", "未核实", "是", "512-2048",
     "CNY", 0.25, "北京 ¥0.25 生成 + ¥0.02 输入", "RPM 5", "明确", "核实",
     "⚠ RPM 5 是致命瓶颈(≈300张/小时), 无法批量"),
    ("qwen-image-3.0-pro (2K)", "阿里", "是", "未核实", "未核实", "是", "512-2048",
     "CNY", 0.50, "北京 ¥0.50 生成 + ¥0.02 输入", "RPM 5", "明确", "核实", "无 4K"),
    ("wan2.7-image-pro", "阿里", "是(交互编辑)", "未核实", "支持(数量未核实)", "是", "未核实",
     "CNY", 0.50, "北京 ¥0.50/张", "RPM 300", "明确", "核实",
     "高并发场景比 Qwen 稳"),
    # ---------- 腾讯 ----------
    ("腾讯混元生图 3.0", "腾讯", "是(风格化/消除/扩图)", "是(局部消除/扩图)", "未核实", "是", "未核实",
     "CNY", 0.20, "后付费 ¥0.2/张", "默认并发 1", "明确", "核实",
     "⚠ 默认并发1, 批量必须买叠加包(¥500/并发/天)"),
    ("腾讯混元 极速版", "腾讯", "是(风格化)", "是", "未核实", "是", "未核实",
     "CNY", 0.066, "¥0.099→0.066", "默认并发 3", "明确", "核实", "★影楼场景最便宜"),
    ("腾讯混元 AI 写真", "腾讯", "是", "未核实", "未核实", "是", "未核实",
     "CNY", 0.24, "¥0.28→0.24", "默认并发 1", "明确", "核实", "人像专用线"),
    ("腾讯混元 模特换装", "腾讯", "是", "未核实", "未核实", "是", "未核实",
     "CNY", 0.50, "¥0.5/张", "默认并发 1", "明确", "核实", "电商换装专用"),
    ("腾讯混元 商品背景", "腾讯", "是", "未核实", "未核实", "是", "未核实",
     "CNY", 0.07, "¥0.12→0.07", "默认并发 1", "明确", "核实", "★电商白底/场景图"),
    ("腾讯混元 百变头像", "腾讯", "是", "未核实", "未核实", "是", "未核实",
     "CNY", 0.099, "¥0.099/张", "默认并发 1", "明确", "核实", ""),
    # ---------- 其他 ----------
    ("Recraft V4.1 Flash", "Recraft", "是", "是", "未核实", "否", "未核实",
     "USD", 0.007, "官方 API $0.007/张", "未核实", "明确", "核实", "★最便宜栅格档"),
    ("Recraft V4.1 / V4 (栅格)", "Recraft", "是", "是", "风格参考", "否", "2K",
     "USD", 0.04, "图生图/修补/扩图 $0.04", "未核实", "明确", "核实",
     "老照片修复+扩图性价比高"),
    ("Recraft 2K Pro (栅格)", "Recraft", "是", "是", "风格参考", "否", "2K",
     "USD", 0.21, "2K Pro $0.21-0.25", "未核实", "明确", "核实", ""),
    ("flux-schnell (Replicate)", "Replicate", "是", "否", "未核实", "否", "未核实",
     "USD", 0.003, "Replicate $3.00/千张", "未核实", "Apache-2.0", "核实", "廉价档标杆"),
    ("Z Image Turbo (fal)", "fal", "是", "未核实", "未核实", "否", "未核实",
     "USD", 0.005, "fal $0.005/MP", "未核实", "未核实", "核实", ""),
    ("Photoshop API v2", "Adobe", "是(Generative Fill)", "是", "不适用", "不适用", "不限",
     "USD", None, "企业 rate card 登录墙, 无公开单价", "企业额度", "企业合同", "未核实",
     "唯一能做 PSD 模板确定性批量换图"),
]

# 汇率输入行
ws["A1"] = "汇率 (USD→CNY)"
ws["A1"].font = TITLE_FONT
ws["F1"] = RATE
ws["F1"].fill = INPUT_FILL
ws["F1"].border = BORDER
ws["F1"].number_format = "0.00"
ws["G1"] = "← 可修改，全表随此汇率重算"
ws["G1"].font = NOTE_FONT

HDR = 2
for c, h in enumerate(headers, start=1):
    cell = ws.cell(row=HDR, column=c, value=h)
    cell.fill = HEAD_FILL
    cell.font = HEAD_FONT
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws.row_dimensions[HDR].height = 30

r = HDR + 1
for d in DATA:
    (model, vendor, instr, mask, refs, multi, res,
     cur, price, pricedesc, limit, lic, status, note) = d
    vals = [model, vendor, instr, mask, refs, multi, res, cur, price, pricedesc,
            None, limit, lic, status, note]
    for c, v in enumerate(vals, start=1):
        ws.cell(row=r, column=c, value=v)
    # J 列: 人民币/张（公式）
    if price is None:
        ws.cell(row=r, column=11, value="未公开")
    elif cur == "CNY":
        ws.cell(row=r, column=11, value=f"=I{r}")
    else:
        ws.cell(row=r, column=11, value=f"=ROUND(I{r}*$F$1,3)")
    r += 1
LAST = r - 1

for i in range(HDR + 1, LAST + 1):
    for c in range(1, NCOL + 1):
        cell = ws.cell(row=i, column=c)
        cell.border = BORDER
        cell.font = Font(size=10)
        cell.alignment = Alignment(vertical="center", wrap_text=(c in (10, 15)))
    ws.cell(row=i, column=9).number_format = "$0.00000"
    ws.cell(row=i, column=11).number_format = "¥0.000"
    status = ws.cell(row=i, column=14).value or ""
    lic = ws.cell(row=i, column=13).value or ""
    if status in ("已淘汰", "未核实"):
        ws.cell(row=i, column=1).fill = LEGACY_FILL
    if "非商用" in lic or "企业合同" in lic:
        ws.cell(row=i, column=13).fill = WARN_FILL
    elif lic == "明确":
        ws.cell(row=i, column=13).fill = OK_FILL

widths = [28, 10, 20, 18, 18, 8, 14, 7, 12, 32, 11, 12, 22, 10, 34]
for idx, w in enumerate(widths, start=1):
    ws.column_dimensions[get_column_letter(idx)].width = w
ws.freeze_panes = f"A{HDR + 1}"
ws.auto_filter.ref = f"A{HDR}:O{LAST}"

# ============================================================================
# Sheet 2: 成本测算
# ============================================================================
cs = wb.create_sheet("成本测算")
cs["A1"] = "单客户 API 成本测算"
cs["A1"].font = Font(bold=True, size=13, color="1F3864")
cs["A2"] = ("黄底为输入项：改 F4/G4/H4 张数即按公式重算；J–M 列为 Python 独立复算的参考值，"
            "不随张数变化（本沙箱 LibreOffice 重算不可用）。")
cs["A2"].font = NOTE_FONT

cs["A4"] = "张数"
cs["A4"].font = TITLE_FONT
for j, n in enumerate([20, 50, 100], start=1):
    c = cs.cell(row=4, column=5 + j, value=n)
    c.font = Font(bold=True, size=10)
    c.fill = INPUT_FILL
    c.border = BORDER
    c.alignment = Alignment(horizontal="center")

HDR2 = 6
cs.cell(row=HDR2, column=1, value="模型 (按人民币单张成本升序)").font = HEAD_FONT
cs.cell(row=HDR2, column=1).fill = HEAD_FILL
cs.cell(row=HDR2, column=4, value="单张(¥)").font = HEAD_FONT
cs.cell(row=HDR2, column=4).fill = HEAD_FILL
cs.cell(row=HDR2, column=4).alignment = Alignment(horizontal="center")
for j, label in enumerate(["20 张", "50 张", "100 张"], start=1):
    c = cs.cell(row=HDR2, column=4 + j, value=label)
    c.font = HEAD_FONT
    c.fill = HEAD_FILL
    c.alignment = Alignment(horizontal="center")
for j, label in enumerate(["20张(参考)", "50张(参考)", "100张(参考)", "单张(参考)"], start=1):
    c = cs.cell(row=HDR2, column=9 + j, value=label)
    c.font = HEAD_FONT
    c.fill = HEAD_FILL
    c.alignment = Alignment(horizontal="center")

pick = []
for i in range(HDR + 1, LAST + 1):
    name = ws.cell(row=i, column=1).value
    cur = ws.cell(row=i, column=8).value
    price = ws.cell(row=i, column=9).value
    if price is None:
        continue
    cny = price if cur == "CNY" else price * RATE
    pick.append((cny, i, name))
pick.sort()

r = HDR2 + 1
for cny, src, name in pick:
    cs.cell(row=r, column=1, value=name).font = Font(size=10)
    cs.cell(row=r, column=4, value=f"=模型对比!$K${src}")
    cs.cell(row=r, column=4).number_format = "¥0.000"
    cs.cell(row=r, column=4).alignment = Alignment(horizontal="right")
    for j in range(1, 4):
        col = get_column_letter(4 + j)
        cs.cell(row=r, column=4 + j).value = f"=ROUND(模型对比!$K${src}*{col}$4,2)"
        cs.cell(row=r, column=4 + j).number_format = "¥#,##0.00"
        cs.cell(row=r, column=4 + j).alignment = Alignment(horizontal="right")
    for j, n in enumerate([20, 50, 100]):
        c = cs.cell(row=r, column=9 + j, value=round(cny * n, 2))
        c.number_format = "¥#,##0.00"
        c.font = Font(size=10)
        c.border = BORDER
        c.alignment = Alignment(horizontal="right")
    c = cs.cell(row=r, column=13, value=round(cny, 3))
    c.number_format = "¥0.000"
    c.font = Font(size=10)
    c.border = BORDER
    c.alignment = Alignment(horizontal="right")
    for c2 in range(1, 14):
        cs.cell(row=r, column=c2).border = BORDER
    r += 1

cs.column_dimensions["A"].width = 30
for col in ["B", "C"]:
    cs.column_dimensions[col].width = 3
for col in ["D", "E", "F", "G", "H"]:
    cs.column_dimensions[col].width = 13
for col in ["I", "J", "K", "L", "M"]:
    cs.column_dimensions[col].width = 13

concl = r + 1
cs.cell(row=concl, column=1, value="关键结论").font = Font(bold=True, size=12, color="1F3864")
points = [
    "API 成本占零售价仅 2%–5%（廉价档）到 5%–12%（顶级档）——API 成本绝不是瓶颈。",
    "真正成本是人工挑图/返修与客户沟通：一单 2 小时人工（时薪 ¥50 = ¥100）已超过 100 张顶级档 API 总额（¥213）的 47%。",
    "不要为省 API 钱牺牲画质。降本点在减少无效生成：用 low 档试稿 + high 档定稿的两段式，比 3 次直接 high 重试便宜约 3 倍（估算）。",
    "主体交付走「主力档」+ 顶级档点缀：20 张里 3–5 张进顶级档，是毛利最优结构。",
    "⚠ 实际务必乘 1.3–1.8 重试系数（估算）——图片生成有失败率，报价要留余量。",
    "⚠ 立刻排除：qwen-image-3.0-pro（RPM 5，无法批量）、FLUX.1 Kontext（已 Legacy）、可图 Kolors（停更）、gpt-image-1（已被 2 代取代）。",
]
for i, p in enumerate(points):
    rr = concl + 1 + i
    cell = cs.cell(row=rr, column=1, value="• " + p)
    cell.font = Font(size=10)
    cs.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=13)
    cell.alignment = Alignment(vertical="center")

# ============================================================================
# Sheet 3: 场景推荐
# ============================================================================
sc = wb.create_sheet("场景推荐")
sc.append(["场景", "首选", "备选", "不要用", "说明"])
scenarios = [
    ("① 老照片修复(划痕/模糊/上色)", "FLUX.2 [pro] + FLUX Eraser/Deblur/Outpainting", "Recraft 图生图 $0.04; 混元局部消除/扩图(限时免费)",
     "纯文生图大模型(脸会漂移); MJ(无mask)", "保底可叠加 Topaz Web $12/月 本地无限渲染"),
    ("② 证件照(换底/换装/合规)", "混元 模特换装 ¥0.5 + 百变头像 ¥0.099", "Seedream 5.0 pro 图层拆分 ¥0.15; gpt-image-2 mask 编辑",
     "Midjourney、Recraft(规格与肤色一致性不可控)", "⚠ 官方禁止修改照片, 只做抠图/换底/规格裁切, 严禁改五官"),
    ("③ 人像精修/写真", "Nano Banana Pro ($0.15, 5人ID保持, ≤14参考)", "Seedream 5.0 pro ¥0.30; 混元 AI 写真 ¥0.24",
     "gpt-image-1 老接口; qwen-3.0-pro(RPM5撑不住一组)", "身份一致性是核心指标"),
    ("④ 婚纱照风格化", "Nano Banana 2 ($0.08, 4K仅$0.16)", "FLUX.2 [max]; Seedream 4.5 ¥0.25",
     "廉价档(klein 4B/混元极速版)会丢脸", "严禁整图重绘——客户投诉「假」的重灾区"),
    ("⑤ 电商白底图/换背景", "FLUX.2 [pro] ($0.0375/MP)", "混元 商品背景 ¥0.07; gpt-image-2 低/中质量",
     "高价 4K 高质量($0.401 纯浪费)", "抠图建议走 BiRefNet 小模型, 只有换背景才调大模型"),
    ("⑥ 批量出片(100+张/单)", "FLUX.2 [klein] 4B ($0.014) + 混元极速版 ¥0.066", "Seedream 5.0 flash ¥0.12; NB2 @512² $0.06",
     "qwen-3.0-pro(RPM5); 混元默认并发1(不买叠加包无法批量)", "先解决限流, 再谈价格"),
]
for s in scenarios:
    sc.append(list(s))
for c in range(1, 6):
    cell = sc.cell(row=1, column=c)
    cell.fill = HEAD_FILL
    cell.font = HEAD_FONT
    cell.alignment = Alignment(horizontal="center", vertical="center")
for i in range(2, len(scenarios) + 2):
    for c in range(1, 6):
        cell = sc.cell(row=i, column=c)
        cell.border = BORDER
        cell.font = Font(size=10)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    sc.row_dimensions[i].height = 40
for idx, w in enumerate([24, 40, 40, 34, 40], start=1):
    sc.column_dimensions[get_column_letter(idx)].width = w
sc.freeze_panes = "A2"

# ============================================================================
# Sheet 4: 说明与来源
# ============================================================================
nt = wb.create_sheet("说明与来源")
notes = [
    ("AI 修图模型对比与成本测算", "title"),
    ("读取时点：2026-10-21　汇率：1 USD = 7.10 CNY（阿里云计费页换算约 7.27，此处保守取 7.10）", "note"),
    ("⚠ 该领域迭代极快：FLUX.1 Kontext 已进 Legacy、Seedream 5.0 取代 4.5、GPT Image 2.5 有模型无公开价。落地前必须重新核价。", "note"),
    ("", ""),
    ("可信度约定", "head"),
    ("[核实]   有公开来源页，见下方 URL", ""),
    ("[估算]   由已核实单价折算或工程推断", ""),
    ("[未核实] 未找到可靠公开来源，不得当作事实对外引用", ""),
    ("灰底行 = 已淘汰或未核实，不应进入选型", ""),
    ("", ""),
    ("本次相对早期版本的修正（重要）", "head"),
    ("1. FLUX.1 Kontext [pro]/[max] 已归入 Legacy Models，无现役报价 → 从推荐中移除", ""),
    ("2. Seedream 现役旗舰是 5.0 pro/flash/lite，4.5 已非旗舰", ""),
    ("3. Google 现役为 Nano Banana Pro (Gemini 3 Pro Image) 与 Nano Banana 2 (Gemini 3.1 Flash Image)", ""),
    ("4. GPT Image 2.5 在 fal 有模型但无公开单价 → 不得写进报价单", ""),
    ("5. gpt-image-2 价格以 fal 档位表为准（OpenAI 官方页对本网络 403）", ""),
    ("6. 腾讯混元生图 3.0 实际 ¥0.2/张（早期口径 ¥0.5 是 2.0 世代）", ""),
    ("7. 阿里 qwen-image-3.0-pro 北京价 ¥0.25(1K)/¥0.50(2K)，RPM 5 一致", ""),
    ("8. 可图 Kolors 已边缘化（快手主线转可灵），不建议新接入", ""),
    ("9. Imagen 系列有 Firebase 迁移文档，视为停产/迁移中", ""),
    ("", ""),
    ("重要授权提醒（比价格更重要）", "head"),
    ("FLUX 系列：非商用许可限制的是「模型本身」，生成结果(Outputs)可用于商业目的。", ""),
    ("但自托管商用必须购买 Self-Hosted 授权，且该授权明确禁止以 API 形式转售。", ""),
    ("  调 BFL 官方 API 出图卖客户 = 合规", ""),
    ("  自建跑 FLUX 权重内部使用   = 需购买 Self-Hosted 授权", ""),
    ("  自建跑权重再包装成 API 转售 = 禁止（即使买了授权）", ""),
    ("", ""),
    ("开源可商用编辑模型：Qwen-Image-Edit-2509 (Apache-2.0)、BAGEL-7B-MoT (Apache-2.0)", ""),
    ("可商用小模型：Real-ESRGAN (BSD-3)、BiRefNet (MIT)、SAM 2 (Apache-2.0)、LaMa (Apache-2.0)", ""),
    ("非商用勿用：CodeFormer (S-Lab 1.0)、RMBG-2.0 (Bria 自定义)", ""),
    ("需逐组件审计：GFPGAN (Apache-2.0 但含 DFDNet 等 CC BY-NC-SA 4.0 组件)", ""),
    ("审计方法：GET https://api.github.com/repos/{owner}/{repo}/license 返回 SPDX ID", ""),
    ("", ""),
    ("工程坑位提醒", "head"),
    ("返回形态分裂：OpenAI 返回 b64_json（响应体极大，String 接收会 OOM）；", ""),
    ("BFL/WaveSpeed/阿里返回短时效签名 URL —— BFL 仅 10 分钟有效、无 CORS、禁止直连终端用户，", ""),
    ("必须服务端立即下载转存。", ""),
    ("异步是常态：BFL/WaveSpeed/腾讯/火山均为 submit + poll。", ""),
    ("分辨率注水：FLUX.1 Kontext 输出恒约 1MP；很多标称 4K 的实际是 2048²。", ""),
    ("审核双向误杀且无申诉通道：不可承诺「指定明星换装」。", ""),
    ("Google 生成图带 SynthID 水印；腾讯混元 LogoAdd 默认=1 会自动加「AI生成」水印（合规上省事）。", ""),
    ("Adobe Photoshop API v1 已于 2026-07-31 EOL，新集成必须直接上 v2。", ""),
    ("", ""),
    ("聚合平台价差结论", "head"),
    ("fal.ai 基本按官方价转售，FLUX 3 甚至更便宜；价格透明度最高（机器可读 + 公开定价页）", ""),
    ("Replicate 对开源/第三方模型与官方一致，但闭源旗舰要求自带 Key(BYOK)，不补贴", ""),
    ("OpenRouter 图像按 token 计费，同模型不同分辨率成本漂移 → 不适合固定单价报价，适合容灾", ""),
    ("统一接入建议：fal.ai 为主 + 火山方舟/腾讯混元 为辅（成本低一个数量级）+ OpenRouter 兜底", ""),
    ("", ""),
    ("待核实清单（对外引用前必须补）", "head"),
    ("OpenAI 官方 gpt-image-2 / 2.5 原始单价（当前 403）", ""),
    ("Google 官方 Nano Banana Pro/2 原始单价（当前不可达，仅 fal 可核）", ""),
    ("Midjourney 订阅价、Adobe Firefly/Photoshop API v2 按量价（均需登录）", ""),
    ("Krea / Remini / 美图开放平台（无公开按量价目页）", ""),
    ("Qwen-Image-Edit-2509 量化后实际显存与速度", ""),
    ("混元迁移至 TokenHub 后的价格与能力变化", ""),
    ("", ""),
    ("关键来源 URL", "head"),
    ("https://fal.ai/pricing", ""),
    ("https://fal.ai/models/fal-ai/nano-banana-pro", ""),
    ("https://fal.ai/models/openai/gpt-image-2", ""),
    ("https://bfl.ai/pricing", ""),
    ("https://docs.bfl.ai/quick_start/pricing", ""),
    ("https://www.volcengine.com/docs/82379/1544106", ""),
    ("https://help.aliyun.com/zh/model-studio/qwen-image-3-0-pro", ""),
    ("https://www.alibabacloud.com/help/en/model-studio/wan2-7-image-pro", ""),
    ("https://cloud.tencent.com/document/product/1668/90896", ""),
    ("https://www.recraft.ai/docs/api-reference/pricing", ""),
    ("https://replicate.com/pricing", ""),
    ("https://openrouter.ai/api/v1/models", ""),
    ("https://www.topazlabs.com/pricing", ""),
    ("https://magnific.ai/pricing", ""),
    ("https://firebase.google.cn/docs/ai-logic/imagen-models-migration", ""),
    ("https://bfl.ai/legal/non-commercial-license-terms", ""),
    ("https://bfl.ai/legal/self-hosted-commercial-license-terms", ""),
    ("https://github.com/sczhou/CodeFormer/blob/master/LICENSE", ""),
    ("https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE", ""),
]
for i, (text, kind) in enumerate(notes, start=1):
    cell = nt.cell(row=i, column=1, value=text)
    if kind == "title":
        cell.font = Font(bold=True, size=14, color="1F3864")
    elif kind == "head":
        cell.font = Font(bold=True, size=11, color="C00000")
    elif kind == "note":
        cell.font = NOTE_FONT
    else:
        cell.font = Font(size=10)
nt.column_dimensions["A"].width = 118

wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("saved:", OUT)
print("sheets:", wb.sheetnames)
print("模型对比 rows:", LAST - HDR, "| 成本测算 model rows:", len(pick))
print("cheapest 5:")
for cny, src, name in pick[:5]:
    print("   %-38s ¥%.3f" % (name, cny))
print("most expensive 3:")
for cny, src, name in pick[-3:]:
    print("   %-38s ¥%.3f" % (name, cny))
