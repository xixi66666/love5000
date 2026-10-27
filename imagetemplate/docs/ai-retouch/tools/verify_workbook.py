# -*- coding: utf-8 -*-
"""校验工作簿结构与公式引用，并输出关键成本数据。"""
import io
import sys

from openpyxl import load_workbook

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PATH = "docs/ai-retouch/AI修图模型对比与成本测算.xlsx"
RATE = 7.10

wb = load_workbook(PATH)
ws = wb["模型对比"]
cs = wb["成本测算"]

errors = []
rows = {}          # name -> row
priced = []        # (cny, name)

# 表头从第 2 行开始，数据从第 3 行
HDR = 2
for r in range(HDR + 1, ws.max_row + 1):
    name = ws.cell(row=r, column=1).value
    if not name:
        continue
    cur = ws.cell(row=r, column=8).value
    price = ws.cell(row=r, column=9).value
    j = ws.cell(row=r, column=11).value
    if name in rows:
        errors.append("重复模型名: %s (row %d 与 %d)" % (name, rows[name], r))
    rows[name] = r

    if price is None:
        if j != "未公开":
            errors.append("J%d (%s): 价格为空但值为 %r" % (r, name, j))
        continue
    expect = "=I%d" % r if cur == "CNY" else "=ROUND(I%d*$F$1,3)" % r
    if j != expect:
        errors.append("J%d (%s): 公式 %r != 期望 %r" % (r, name, j, expect))
    cny = price if cur == "CNY" else price * RATE
    priced.append((cny, name, r))

# 成本测算公式引用校验
calc = []
for r in range(7, cs.max_row + 1):
    name = cs.cell(row=r, column=1).value
    if not name or name.startswith("•") or name == "关键结论":
        continue
    if name not in rows:
        errors.append("成本测算第 %d 行引用了不存在的模型: %r" % (r, name))
        continue
    calc.append(name)
    src = rows[name]
    f4 = cs.cell(row=r, column=4).value
    if f4 != "=模型对比!$K$%d" % src:
        errors.append("D%d (%s): %r 引用错误" % (r, name, f4))
    for j, col in enumerate(["E", "F", "G"]):
        f = cs.cell(row=r, column=5 + j).value
        expect = "=ROUND(模型对比!$K$%d*%s$4,2)" % (src, col)
        if f != expect:
            errors.append("%s%d (%s): %r != %r" % (col, r, name, f, expect))

# 覆盖率：所有有价格的模型都应进入测算表
missing = {n for _, n, _ in priced} - set(calc)
if missing:
    errors.append("成本测算缺少模型: %s" % sorted(missing))

# 汇率与重算设置
rate_cell = ws["F1"].value
if rate_cell != RATE:
    errors.append("F1 汇率 %r != %r" % (rate_cell, RATE))
if not wb.calculation.fullCalcOnLoad:
    errors.append("fullCalcOnLoad 未开启")

print("=" * 62)
print("模型对比数据行: %d" % len(rows))
print("有价格模型数  : %d" % len(priced))
print("成本测算行数  : %d" % len(calc))
print("汇率 F1       : %s" % rate_cell)
print("fullCalcOnLoad: %s" % wb.calculation.fullCalcOnLoad)
print("=" * 62)
print("公式错误: %d" % len(errors))
for e in errors:
    print("  ERR:", e)
if not errors:
    print("  所有公式引用与所在行一致，无错行引用；测算表覆盖全部有价格模型。")

priced.sort()
print("=" * 62)
print("最便宜 8 个 (人民币/张):")
for cny, name, _ in priced[:8]:
    print("   %-40s CNY %.3f" % (name, cny))
print("最贵 5 个 (人民币/张):")
for cny, name, _ in priced[-5:]:
    print("   %-40s CNY %.3f" % (name, cny))

print("=" * 62)
print("50 张单客户成本对照 (人民币):")
for target in ["腾讯混元 极速版", "FLUX.2 [klein] 4B (1MP)", "Seedream 5.0 pro (≤261万px)",
               "FLUX.2 [pro] (1MP)", "Nano Banana 2 (1K)", "Nano Banana Pro (1K-2K)",
               "gpt-image-2 (3840x2160 high)"]:
    for cny, name, _ in priced:
        if name == target:
            print("   %-40s 单张 ¥%-8.3f 50张 ¥%-9.2f 100张 ¥%.2f" % (name, cny, cny * 50, cny * 100))
            break
    else:
        print("   %-40s [未找到]" % target)
print("=" * 62)
sys.exit(1 if errors else 0)
