# ImageTemplate 月夜深色主题适配设计

## 背景

`imagetemplate` 首页背景视频已由 CloudFront 的 `03 Deep Woods`（亮度约 165/255）替换为本地 `media/moon-wallpaper.mp4`（亮度约 54/255，RGB ≈ 53,53,56 中性偏冷灰蓝）。当前 UI 仍是浅色系：`--page-bg: #dfe7dd` 浅灰绿底、近黑文字、雾白玻璃。深色视频与浅色 UI 明度冲突，页面大面积"发白"，文字与背景割裂。

经确认，本次目标为：**深色玻璃拟态 + 冷蓝月银强调色 + 视频可见性优先**，采用中性月夜配色方案，让布局与月亮视频融为一体。

## 目标

- 将四个场景统一为深色月夜视觉，消除浅色 UI 与深色视频的亮度冲突。
- 视频作为氛围背景柔和透出：外层膜约 6% 通明，卡片/面板玻璃 40%-60% 不透明，文字在任何视频帧下可读。
- 强调色从苔藓绿 + 树皮橙切换为月银蓝系。
- 不改变页面结构、交互、API、模板数据与场景行为。

## 设计方案

### 设计 token（`:root` 替换）

沿用现有变量名，整体替换 `imagetemplate/src/main/resources/static/css/app.css` 的 `:root` 色板：

| 变量 | 现值 | 新值（月夜） |
|---|---|---|
| `--page-bg` | `#dfe7dd` | `#0e1418` |
| `--ink` / `--ivory` | `#080d0b` | `#e6edf5`（月白主文字） |
| `--ink-soft` | `#121a17` | `#aebed0` |
| `--muted` | `#2b3631` | `#8fa3b5`（次级文字） |
| `--surface` | `rgba(239,247,239,.06)` | `rgba(190,215,235,.06)` |
| `--surface-strong` | `#f9fcf7` | `#16202a` |
| `--surface-hover` | `#edf5ee` | `#1d2a36` |
| `--gold` | `#356f5a` | `#9cc0e8`（月银主强调） |
| `--gold-bright` | `#2d6955` | `#cfe3f8`（亮银） |
| `--gold-deep` | `#214f42` | `#5d7fa8`（深蓝灰） |
| `--line` | `rgba(44,73,66,.19)` | `rgba(180,205,235,.16)` |
| `--line-strong` | `#76a087` | `#7fa3c8` |
| `--accent` | `#a85f35` | `#8fb0d8` |
| `--danger` | `#b42318` | `#f28585` |
| `--success` | `#15803d` | `#6cdb9a` |
| `--warning` | `#b45309` | `#e8c170` |

### 硬编码颜色适配

CSS 中约 60 处硬编码浅色/绿金色需逐处替换为月夜系：

- **浅色玻璃背景**：`rgba(249,252,247,.82)`、`rgba(247,250,244,.82)`、`rgba(249,252,247,.9)`、`#f9fcf7` 等 → 深色玻璃 `rgba(13,20,27,.72~.85)`，hover `#1d2a36`。
- **浅色边框/选中态**：`#e7f1e8`、`#f5f8f3`、`#fff5ed`、`#edf5ee`、`#e7ede5` → `#1d2a36` / `#22303e`。
- **说明文字**：`#71695c`、`#5d786b`、`#3e4944`、`#202925`、`#6f8178` → `#8fa3b5` 系列。
- **错误/警告底色**：`#fff5ed`、`rgba(91,28,20,.28)` → 深色红玻璃 `rgba(120,40,35,.25)`，文字 `#fca5a5`。
- **绿色渐变按钮**：brand-mark、primary-action、generate 的 `linear-gradient(145deg,#547c69,#214f42)` → 蓝银渐变 `linear-gradient(145deg,#5d7fa8,#2c3d52)`，白字不变。
- **滚动条**：`#cbd5e1` → `#3a4a5a`。
- **视频遮罩与装饰层**：`deep-woods-shade` 绿调、`backdrop-orb` 绿渐变、`grain`、`golden-trace` 金调 → 冷蓝调（shade `rgba(8,16,28,.28)`，orb 渐变 `#4a5c72` → `#1e2a38`，golden-trace 蓝银）。
- **编导台/生成舱金色系**：`rgba(214,179,106,*)` → 月银蓝 `rgba(156,192,232,*)`；`#eee4d2` → `#e6edf5`；`#17120b` → `#16202a`；focus 环 `rgba(214,179,106,.1)` → `rgba(156,192,232,.14)`。
- **状态焦点环**：`rgba(21,128,61,.12)` → `rgba(108,219,154,.15)`。

### 玻璃透明策略（视频可见性优先）

- 外层场景膜保持约 6% 通明，色调从雾白改为冷蓝。
- 卡片/面板玻璃 40%-60% 不透明：面板 `rgba(13,20,27,.55)`，卡片 hover `rgba(29,42,54,.6)`。
- 落在视频上的直接文字依赖深色遮罩保证对比度，不额外增加文字阴影层。
- 保留 `prefers-reduced-motion` 降级，装饰动画不变。

### 范围约束

- 只改 `imagetemplate/src/main/resources/static/css/app.css` 与测试断言；`index.html` 仅视频源已切换为 `media/moon-wallpaper.mp4`，本次不再改结构。
- 不改 API、模板数据、分类逻辑、交互脚本 `app.js`。
- 移动端断点、`prefers-reduced-motion`、四场景行为全部保留。

## 测试同步

`ImageTemplateHomepageStaticAssetsTest` 目前 4 个用例全部失败（遗留旧断言：runway 视觉系统、浅色 token、旧 CloudFront 视频 URL）。本次同步修正：

- 删除 runway 相关断言（CSS 已无 `--runway-*` 变量）。
- 浅色 token 断言改为新 token：`--page-bg: #0e1418;`、`--ink: #e6edf5;`、`--muted: #8fa3b5;`、`--gold: #9cc0e8;` 等。
- 旧视频 URL 断言改为 `media/moon-wallpaper.mp4`。
- 保留结构、交互、无障碍相关断言不动。

## 文档同步

更新 `imagetemplate/AGENTS.md`、`imagetemplate/README.md`、根 `AGENTS.md` / `README.md` 中背景视频与配色描述：

- 背景视频：本地 `media/moon-wallpaper.mp4`，不再复用 website 首页远程视频。
- 配色：深色月夜玻璃拟态，冷蓝月银强调，视频可见性优先。
- 测试命令与结构描述不变。

## 验证

- `mvn -pl imagetemplate -am test` 全绿。
- 启动 `imagetemplate` 访问 `http://127.0.0.1:8082/`，检查四个场景：文字可读、玻璃通透、按钮/焦点环为月银蓝、错误态为暗红。
- 检查视频加载：`http://127.0.0.1:8082/media/moon-wallpaper.mp4` 返回 200。
- 移动端（900px 以下）与 `prefers-reduced-motion` 降级正常。
