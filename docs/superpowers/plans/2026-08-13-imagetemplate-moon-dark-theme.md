# ImageTemplate 月夜深色主题适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 imagetemplate 页面从浅色绿系切换为深色月夜玻璃拟态（冷蓝月银强调），适配本地 moon-wallpaper.mp4 深色背景视频。

**Architecture:** 全部改动集中在 `imagetemplate/src/main/resources/static/css/app.css`（`:root` token + 硬编码颜色）、测试断言 `ImageTemplateHomepageStaticAssetsTest` 和文档。不修改 HTML 结构、JS 行为、API 与模板数据。

**Tech Stack:** 原生 CSS（无构建工具）、JUnit 5 / AssertJ。

## Global Constraints

- 沿用现有 CSS 变量名（`--gold`、`--ink`、`--muted` 等），只改值，不新增/删除变量名。
- 新色板（方案 A 中性月夜）：`--page-bg: #0e1418;`、`--ink: #e6edf5;`、`--muted: #8fa3b5;`、`--gold: #9cc0e8;`、`--gold-bright: #cfe3f8;`、`--gold-deep: #5d7fa8;`、`--line: rgba(180,205,235,.16);`、`--line-strong: #7fa3c8;`、`--accent: #8fb0d8;`、`--danger: #f28585;`、`--success: #6cdb9a;`、`--warning: #e8c170;`、`--ink-soft: #aebed0;`、`--surface: rgba(190,215,235,.06);`、`--surface-strong: #16202a;`、`--surface-hover: #1d2a36;`。
- 视频可见性优先：面板/卡片玻璃 40%-60% 不透明，色调为冷蓝 `rgba(13,20,27,.55~.85)`。
- 金色系 `rgba(214, 179, 106, *)` 全部替换为月银蓝 `rgba(156, 192, 232, *)`（alpha 不变）。
- 保留 `prefers-reduced-motion` 降级与所有响应式断点。
- 背景视频引用为本地 `media/moon-wallpaper.mp4`（已在 index.html:13-16 完成，本次不动）。
- 不提交 `target/`、`.playwright-cli/`、截图文件。

---

### Task 1: 替换 `:root` 色板 token

**Files:**
- Modify: `imagetemplate/src/main/resources/static/css/app.css:1-26`

**Interfaces:**
- Consumes: 无
- Produces: 新的 `:root` 变量值；Task 2 依赖这些变量名保持存在

- [ ] **Step 1: 替换 `:root` 块**

将 `app.css` 第 1-26 行 `:root { ... }` 的内容整体替换为：

```css
:root {
    --deep-woods-ink: #182c41;
    --ink: #e6edf5;
    --ink-soft: #aebed0;
    --surface: rgba(190, 215, 235, .06);
    --surface-strong: #16202a;
    --surface-hover: #1d2a36;
    --gold: #9cc0e8;
    --gold-bright: #cfe3f8;
    --gold-deep: #5d7fa8;
    --ivory: #e6edf5;
    --muted: #8fa3b5;
    --line: rgba(180, 205, 235, .16);
    --line-strong: #7fa3c8;
    --page-bg: #0e1418;
    --soft-bg: rgba(190, 215, 235, .06);
    --accent: #8fb0d8;
    --danger: #f28585;
    --success: #6cdb9a;
    --warning: #e8c170;
    --topbar-height: 76px;
    --dock-height: 92px;
    --workflow-rail-width: 118px;
    --minimum-target: 44px;
    --ease-cinematic: cubic-bezier(.22, 1, .36, 1);
}
```

- [ ] **Step 2: 验证 token 替换**

运行: `Select-String -Path "imagetemplate/src/main/resources/static/css/app.css" -Pattern "--page-bg: #0e1418|--ink: #e6edf5|--gold: #9cc0e8"`
Expected: 三个 token 均出现一次

- [ ] **Step 3: 提交**

```bash
git add imagetemplate/src/main/resources/static/css/app.css
git commit -m "style(imagetemplate): switch root tokens to moon night palette"
```

---

### Task 2: 替换浅色玻璃背景与绿色渐变按钮（硬编码）

**Files:**
- Modify: `imagetemplate/src/main/resources/static/css/app.css`（按行号）

**Interfaces:**
- Consumes: Task 1 的新 token
- Produces: 深色玻璃面板视觉；Task 4 测试断言依赖新值

- [ ] **Step 1: 逐行替换以下硬编码颜色**

使用编辑工具精确替换（每处一个 edit，oldString 需唯一，替换失败时用更大上下文）：

| 行号 | 现值 | 新值 |
|---|---|---|
| 90 | `background: #cbd5e1;` | `background: #3a4a5a;` |
| 246 | `background: rgba(242, 247, 239, .72);` | `background: rgba(12, 18, 24, .72);` |
| 267 | `linear-gradient(145deg, #547c69, #214f42)` | `linear-gradient(145deg, #5d7fa8, #2c3d52)` |
| 328 | `rgba(249, 252, 247, .82)` | `rgba(13, 20, 27, .82)` |
| 342 | `rgba(21, 128, 61, .12)` | `rgba(108, 219, 154, .15)` |
| 348 | `background: #edf5ee;` | `background: #1d2a36;` |
| 495 | `rgba(247, 250, 244, .82)` | `rgba(13, 20, 27, .72)` |
| 539 | `linear-gradient(135deg, #214f42, #477562)` | `linear-gradient(135deg, #2c3d52, #5d7fa8)` |
| 578 | `rgba(249, 252, 247, .9)` | `rgba(13, 20, 27, .85)` |
| 585 | `background: #edf5ee;` | `background: #1d2a36;` |
| 1133 | `rgba(239, 247, 239, .06)` | `rgba(190, 215, 235, .06)` |
| 1134 | `rgba(255, 255, 255, .38)` | `rgba(255, 255, 255, .08)` |
| 1145 | `rgba(239, 247, 239, .18)` | `rgba(190, 215, 235, .12)` |
| 1924 | `rgba(249, 252, 247, .62)` | `rgba(13, 20, 27, .6)` |
| 1933 | `border-color: #76a087;` | `border-color: var(--line-strong);` |
| 1935 | `background: #e7f1e8;` | `background: #1d2a36;` |
| 1949 | `border-color: #7f9489;` | `border-color: #7fa3c8;` |
| 1956 | `border-color: #fda29b;` | `border-color: rgba(242, 133, 133, .5);` |
| 1958 | `color: #7f321f;` | `color: #fca5a5;` |
| 1959 | `background: #fff5ed;` | `background: rgba(120, 40, 35, .25);` |
| 2038 | `color: #111815;` | `color: #aebed0;` |
| 2039 | `rgba(249, 252, 247, .34)` | `rgba(13, 20, 27, .4)` |
| 2040 | `rgba(54, 83, 73, .15)` | `rgba(160, 190, 220, .12)` |
| 2073 | `border-color: #76a087;` | `border-color: var(--line-strong);` |
| 2075 | `background: #e7f1e8;` | `background: #1d2a36;` |
| 2082 | `border: 1px dashed #9fb0a6;` | `border: 1px dashed #7fa3c8;` |
| 2085 | `rgba(249, 252, 247, .3)` | `rgba(13, 20, 27, .4)` |
| 2138 | `border: 1px solid #aebdb4;` | `border: 1px solid #22303e;` |
| 2141 | `background: #f9fcf7;` | `background: #16202a;` |
| 2174 | `rgba(54, 83, 73, .16)` | `rgba(180, 205, 235, .14)` |
| 2177 | `rgba(249, 252, 247, .16)` | `rgba(13, 20, 27, .55)` |
| 2178 | `rgba(24, 44, 65, .06)` | `rgba(0, 0, 0, .3)` |
| 2190 | `border-color: #76a087;` | `border-color: var(--line-strong);` |
| 2191 | `rgba(244, 249, 242, .42)` | `rgba(29, 42, 54, .6)` |
| 2192 | `rgba(33, 79, 66, .14)` | `rgba(0, 0, 0, .3)` |
| 2196 | `rgba(53, 111, 90, .15)` | `rgba(156, 192, 232, .2)` |
| 2200 | `border-color: #d7e0d7;` | `border-color: #22303e;` |
| 2201 | `linear-gradient(105deg, #f5f8f3 30%, #e7eee7 48%, #f5f8f3 66%)` | `linear-gradient(105deg, #16202a 30%, #1d2a36 48%, #16202a 66%)` |
| 2213 | `color: #202925;` | `color: #aebed0;` |
| 2218 | `color: #34413b;` | `color: #8fa3b5;` |
| 2223 | `border-color: #c9ddcd;` | `border-color: #22303e;` |
| 2224 | `color: #101713;` | `color: #cfe3f8;` |
| 2225 | `background: #edf5ee;` | `background: #1d2a36;` |
| 2229 | `border-color: #cbdde1;` | `border-color: #22303e;` |
| 2230 | `color: #101713;` | `color: #cfe3f8;` |
| 2231 | `background: #edf5f5;` | `background: #1d2a36;` |
| 2235 | `border-color: #e8c9af;` | `border-color: #5d4a3a;` |
| 2236 | `color: #101713;` | `color: #e8c170;` |
| 2237 | `background: #fff5ea;` | `background: #2a2113;` |
| 2241 | `border-color: #aebdb4;` | `border-color: #22303e;` |
| 2251 | `border-color: #a6c4ad;` | `border-color: #22303e;` |
| 2254 | `rgba(239, 247, 239, .06)` | `rgba(190, 215, 235, .06)` |
| 2259 | `rgba(239, 247, 239, .18)` | `rgba(190, 215, 235, .12)` |
| 2269 | `rgba(238, 244, 238, .08)` | `rgba(190, 215, 235, .06)` |
| 2280 | `rgba(255, 255, 255, .66)` | `rgba(160, 190, 220, .25)` |
| 2281 | `rgba(244, 249, 242, .68)` | `rgba(13, 20, 27, .68)` |
| 2282 | `rgba(255, 255, 255, .82)` | `rgba(255, 255, 255, .08)` |
| 2288 | `color: #2b6451;` | `color: #7fa3c8;` |
| 2290-2291 | `rgba(53, 111, 90, .05)`（两处） | `rgba(156, 192, 232, .05)`（两处） |
| 2296 | `background: #ffffff;` | `background: #16202a;` |
| 2303 | `rgba(249, 252, 247, .86)` | `rgba(13, 20, 27, .8)` |
| 2308 | `background-color: #e7ede5;` | `background-color: #0e1418;` |
| 2313 | `rgba(235, 245, 235, .08)` | `rgba(190, 215, 235, .08)` |
| 2324 | `rgba(33, 79, 66, .9)` | `rgba(44, 62, 82, .9)` |
| 2328 | `color: #26332d;` | `color: #aebed0;` |
| 2333 | `background: #f9fcf7;` | `background: #16202a;` |
| 2530 | `rgba(53, 111, 90, .12)` | `rgba(156, 192, 232, .12)` |

- [ ] **Step 2: 验证无残留浅色**

运行: `Select-String -Path "imagetemplate/src/main/resources/static/css/app.css" -Pattern "#edf5ee|#f9fcf7|#e7f1e8|#e7ede5|rgba\(249, 252, 247|rgba\(247, 250, 244|#76a087"`
Expected: 无匹配（`#76a087` 若仍有则改为 `#7fa3c8` 或 `var(--line-strong)`）

- [ ] **Step 3: 提交**

```bash
git add imagetemplate/src/main/resources/static/css/app.css
git commit -m "style(imagetemplate): darken glass surfaces and buttons for moon theme"
```

---

### Task 3: 金色系与输入控件转月银蓝，视频遮罩冷蓝化

**Files:**
- Modify: `imagetemplate/src/main/resources/static/css/app.css`（按行号）

**Interfaces:**
- Consumes: 无新依赖
- Produces: 编导台/生成舱与装饰层统一月银冷调

- [ ] **Step 1: 替换金色系（alpha 不变）**

| 行号 | 现值 | 新值 |
|---|---|---|
| 723 | `color: #71695c;` | `color: #8fa3b5;` |
| 756 | `rgba(8, 6, 4, .86)` | `rgba(10, 16, 22, .86)` |
| 778 | `rgba(214, 179, 106, .1)` | `rgba(156, 192, 232, .1)` |
| 815 | `rgba(214, 179, 106, .1)` | `rgba(156, 192, 232, .1)` |
| 827 | `rgba(214, 179, 106, .1)` | `rgba(156, 192, 232, .1)` |
| 828 | `rgba(214, 179, 106, .1)` | `rgba(156, 192, 232, .1)` |
| 893 | `rgba(214, 179, 106, .08)` | `rgba(156, 192, 232, .08)` |
| 922 | `rgba(8, 6, 4, .72)` | `rgba(10, 16, 22, .72)` |
| 934 | `rgba(255, 255, 255, .025)` | `rgba(190, 215, 235, .04)` |
| 942 | `rgba(214, 179, 106, .08)` | `rgba(156, 192, 232, .08)` |
| 971 | `rgba(214, 179, 106, .13)` | `rgba(156, 192, 232, .13)` |
| 973 | `rgba(6, 5, 3, .42)` | `rgba(10, 16, 22, .42)` |
| 1008 | `rgba(214, 179, 106, .08)` | `rgba(156, 192, 232, .08)` |
| 1010 | `rgba(244, 217, 155, .08)` | `rgba(156, 192, 232, .08)` |
| 1042 | `rgba(214, 179, 106, .06)` | `rgba(156, 192, 232, .06)` |
| 1073 | `rgba(214, 179, 106, .16)` | `rgba(156, 192, 232, .16)` |
| 1075 | `color: #cdbb96;` | `color: #cfe3f8;` |
| 1076 | `rgba(214, 179, 106, .055)` | `rgba(156, 192, 232, .055)` |
| 1082 | `rgba(240, 189, 109, .28)` | `rgba(232, 193, 112, .28)` |
| 1087 | `rgba(244, 240, 228, .16)` | `rgba(180, 205, 235, .16)` |
| 1106 | `color: #7e7464;` | `color: #8fa3b5;` |
| 1120 | `rgba(214, 179, 106, .1)` | `rgba(156, 192, 232, .1)` |
| 1122 | `color: #c4b89f;` | `color: #aebed0;` |
| 1123 | `rgba(214, 179, 106, .05)` | `rgba(156, 192, 232, .05)` |
| 1210 | `rgba(4, 3, 2, .5)` | `rgba(10, 16, 22, .5)` |
| 1236 | `color: #d7cbb4;` | `color: #aebed0;` |
| 1244 | `color: #e4c989;` | `color: #cfe3f8;` |
| 1246 | `rgba(214, 179, 106, .035)` | `rgba(156, 192, 232, .035)` |
| 1247 | `rgba(214, 179, 106, .035)` | `rgba(156, 192, 232, .035)` |
| 1262 | `rgba(214, 179, 106, .4)` | `rgba(156, 192, 232, .4)` |
| 1266 | `rgba(220, 84, 84, .72)` | `rgba(242, 133, 133, .72)` |
| 1310 | `rgba(4, 3, 2, .42)` | `rgba(10, 16, 22, .42)` |
| 1337 | `rgba(214, 179, 106, .2)` | `rgba(156, 192, 232, .2)` |
| 1341 | `rgba(3, 3, 2, .6)` | `rgba(10, 16, 22, .6)` |
| 1377 | `background: #17120b;` | `background: #16202a;` |
| 1386 | `rgba(214, 179, 106, .1)` | `rgba(156, 192, 232, .14)` |
| 1391 | `color: #eee4d2;` | `color: #e6edf5;` |
| 1393 | `rgba(214, 179, 106, .055)` | `rgba(156, 192, 232, .055)` |
| 1394 | `rgba(3, 3, 2, .7)` | `rgba(10, 16, 22, .7)` |
| 1419 | `rgba(4, 3, 2, .44)` | `rgba(10, 16, 22, .44)` |
| 1458 | `rgba(214, 179, 106, .025)` | `rgba(156, 192, 232, .025)` |
| 1486 | `rgba(214, 179, 106, .08)` | `rgba(156, 192, 232, .08)` |
| 1507 | `rgba(255, 255, 255, .025)` | `rgba(190, 215, 235, .04)` |
| 1579-1580 | `rgba(214, 179, 106, .025)`（两处） | `rgba(156, 192, 232, .025)`（两处） |
| 1581 | `#090805` | `#0e1418` |
| 1590 | `rgba(214, 179, 106, .08)` | `rgba(156, 192, 232, .08)` |
| 1595 | `#090805 15%, #2a2113 42%, #090805 68%` | `#0e1418 15%, #1d2a36 42%, #0e1418 68%` |
| 1666 | `rgba(255, 255, 255, .42)` | `rgba(160, 190, 220, .3)` |
| 1670 | `rgba(236, 245, 236, .08)` | `rgba(190, 215, 235, .08)` |
| 1671 | `rgba(17, 40, 42, .16)` | `rgba(0, 0, 0, .35)` |
| 1671 | `rgba(255, 255, 255, .42)` | `rgba(160, 190, 220, .3)` |
| 1703 | `rgba(214, 179, 106, .09)` | `rgba(156, 192, 232, .09)` |
| 1746 | `rgba(53, 111, 90, .2)` | `rgba(156, 192, 232, .2)` |
| 1748 | `color: #5d786b;` | `color: #8fa3b5;` |
| 1749 | `rgba(248, 252, 247, .46)` | `rgba(156, 192, 232, .12)` |
| 1766 | `rgba(33, 79, 66, .9)` | `rgba(44, 62, 82, .9)` |
| 1767 | `rgba(20, 57, 48, .2)` | `rgba(0, 0, 0, .35)` |
| 1791 | `rgba(214, 179, 106, .05)` | `rgba(156, 192, 232, .05)` |
| 1798 | `rgba(214, 179, 106, .12)` | `rgba(156, 192, 232, .12)` |
| 1802 | `color: #6f8178;` | `color: #8fa3b5;` |
| 1850 | `rgba(244, 250, 244, .06)` | `rgba(190, 215, 235, .05)` |
| 1857 | `rgba(255, 255, 255, .82)` | `rgba(160, 190, 220, .35)` |
| 1860 | `rgba(255, 255, 255, .58), rgba(230, 240, 230, .25)` | `rgba(160, 190, 220, .18), rgba(190, 215, 235, .08)` |
| 1861 | `rgba(222, 237, 224, .2)` | `rgba(13, 20, 27, .55)` |
| 1863 | `rgba(255, 255, 255, .86)` | `rgba(160, 190, 220, .12)` |
| 1864 | `rgba(24, 65, 57, .11)` | `rgba(0, 0, 0, .3)` |
| 1877 | `rgba(118, 160, 135, .24), transparent 38%, rgba(218, 190, 139, .16)` | `rgba(156, 192, 232, .16), transparent 38%, rgba(95, 127, 168, .12)` |
| 1900 | `color: #3e4944;` | `color: #8fa3b5;` |
| 1905 | `rgba(53, 111, 90, .68)` | `rgba(156, 192, 232, .5)` |
| 1906 | `rgba(248, 251, 246, .78)` | `rgba(13, 20, 27, .78)` |
| 1908 | `rgba(255, 255, 255, .96)` | `rgba(160, 190, 220, .15)` |
| 1909 | `rgba(53, 111, 90, .14)` | `rgba(156, 192, 232, .2)` |
| 1910 | `rgba(24, 65, 57, .14)` | `rgba(0, 0, 0, .3)` |
| 1974 | `rgba(225, 237, 226, .05)` | `rgba(190, 215, 235, .04)` |
| 2150 | `rgba(244, 250, 244, .03)` | `rgba(190, 215, 235, .03)` |

- [ ] **Step 2: 替换视频遮罩与装饰层（冷蓝化）**

| 行号 | 现值 | 新值 |
|---|---|---|
| 112 | `linear-gradient(145deg, #dce6db 0%, #c8d7cd 46%, #9eb9ad 100%)` | `linear-gradient(145deg, #10161d 0%, #141b24 46%, #1a2430 100%)` |
| 133 | `rgba(235, 242, 232, .12)` | `rgba(10, 18, 28, .1)` |
| 133 | `rgba(19, 42, 42, .18)` | `rgba(8, 16, 28, .28)` |
| 154 | `rgba(200, 224, 200, .28)` | `rgba(156, 192, 232, .2)` |
| 154 | `rgba(200, 224, 200, .07)` | `rgba(156, 192, 232, .06)` |
| 155 | `rgba(121, 163, 139, .22)` | `rgba(95, 127, 168, .16)` |
| 155 | `rgba(121, 163, 139, .06)` | `rgba(95, 127, 168, .05)` |
| 156 | `rgba(244, 237, 203, .16)` | `rgba(206, 227, 248, .12)` |
| 182 | `linear-gradient(135deg, #c9dfc8, #6e9b7e)` | `linear-gradient(135deg, #4a5c72, #1e2a38)` |
| 198 | `linear-gradient(135deg, #e2d7ad, #6f9482)` | `linear-gradient(135deg, #5d7fa8, #1e2a38)` |
| 208 | `rgba(118, 160, 135, .4)` | `rgba(156, 192, 232, .4)` |

- [ ] **Step 3: 验证无金色残留**

运行: `Select-String -Path "imagetemplate/src/main/resources/static/css/app.css" -Pattern "214, 179, 106|214,179,106|53, 111, 90|53,111,90"`
Expected: 无匹配

- [ ] **Step 4: 提交**

```bash
git add imagetemplate/src/main/resources/static/css/app.css
git commit -m "style(imagetemplate): shift gold accents to moon silver and cool the video overlays"
```

---

### Task 4: 同步静态资源测试断言

**Files:**
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

**Interfaces:**
- Consumes: Task 1-3 的最终 CSS/HTML 内容
- Produces: 全绿测试

- [ ] **Step 1: 更新断言**

`homepageDefinesFourScenesDockAndExistingBusinessControls`（第 17-59 行）：
- 第 19 行 `"src=\"js/app.js?v=20260806-runway\""` → `"src=\"js/app.js\""`
- 第 49 行 `"hf_20260702_081042_df7202bf-bd80-4b2b-bbc6-1f09ba2870e9.mp4"` → `"media/moon-wallpaper.mp4"`

`discoverScenePrioritizesTheTemplateSelectionArea`（第 62-78 行）：
- 第 67 行 `"href=\"css/app.css?v=20260806-runway2\""` → `"href=\"css/app.css\""`
- 第 69 行 `"class=\"discover-summary-copy\""` → `"class=\"discover-summary\""`
- 第 70 行 `"class=\"discover-summary-actions\""` → `"class=\"primary-action\""`
- 第 95 行 `.discover-summary .scene-lead` 断言删除（该结构已不存在）

`discoverSceneUsesRunwayVisualSystem`（第 80-96 行）：整体删除 `--runway-*` 相关断言（第 85-93 行），保留 CSS 结构断言。

`cinematicStylesAndSceneControllerHaveAccessibilityFallbacks`（第 98-163 行）：
- 第 105 行 `" --deep-woods-ink: #182c41;"` 保持不变
- 第 106 行 `" --ink: #080d0b;"` → `" --ink: #e6edf5;"`
- 第 107 行 `" --page-bg: #dfe7dd;"` → `" --page-bg: #0e1418;"`
- 第 117 行 `"background: rgba(244, 250, 244, .03);"` → `"background: rgba(190, 215, 235, .03);"`
- 第 118 行 `"background: rgba(239, 247, 239, .06);"` → `"background: rgba(190, 215, 235, .06);"`
- 其余断言（布局、动效、交互、无障碍）保持不变

- [ ] **Step 2: 运行测试**

Run: `mvn -pl imagetemplate -am -Dtest=ImageTemplateHomepageStaticAssetsTest -DfailIfNoTests=false test`
Expected: PASS（4 个用例全绿）

- [ ] **Step 3: 提交**

```bash
git add imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
git commit -m "test(imagetemplate): sync static asset assertions to moon theme"
```

---

### Task 5: 全量回归 + 页面验证

**Files:**
- 无新增/修改（仅验证）

- [ ] **Step 1: 全量测试**

Run: `mvn -pl imagetemplate -am test`
Expected: BUILD SUCCESS，无失败

- [ ] **Step 2: 同步运行中服务并验证页面**

若 `imagetemplate` 服务已在 8082 运行：
`Copy-Item "imagetemplate/src/main/resources/static/css/app.css" "imagetemplate/target/classes/static/css/app.css" -Force`
然后浏览器打开 `http://127.0.0.1:8082/`，检查：四个场景文字可读、玻璃通透、按钮为蓝银渐变、焦点环月银、错误态暗红、视频正常循环播放。

- [ ] **Step 3: 文档同步**

更新以下文件中"背景视频/配色"描述：
- `imagetemplate/AGENTS.md`：背景改为本地 `media/moon-wallpaper.mp4`，配色改为深色月夜玻璃拟态 + 冷蓝月银强调。
- `imagetemplate/README.md`：同上。
- 根 `AGENTS.md`：`imagetemplate` 模块职责段中"亮色 AI 创作工作台""复用 website 首页 03 Deep Woods 视频"相关描述更新。
- 根 `README.md`：如包含同样描述则同步。

- [ ] **Step 4: 提交**

```bash
git add imagetemplate/AGENTS.md imagetemplate/README.md AGENTS.md README.md
git commit -m "docs: sync imagetemplate moon theme and local video description"
```
