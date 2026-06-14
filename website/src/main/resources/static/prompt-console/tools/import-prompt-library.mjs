import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const outputPath = path.resolve("website/src/main/resources/static/prompt-console/data/prompt-library.json");
const workDir = path.resolve("target/prompt-library-import");
const execFileAsync = promisify(execFile);

const sources = [
  {
    id: "prompt123",
    name: "Prompt123",
    url: "https://prompt123.cn/?utm_source=novatools.cn",
    license: "User-provided authorization",
    summary: "用户已授权的中文 AI 提示词站点，已解析公开 JSON 数据。",
    categories: ["中文提示词", "写作", "效率", "创意"]
  },
  {
    id: "awesome-chatgpt-prompts",
    name: "prompts.chat",
    url: "https://github.com/f/prompts.chat",
    license: "CC0-1.0",
    summary: "经典 ChatGPT 角色提示词合集，来自 prompts.csv；原仓库主要为英文原文。",
    categories: ["角色", "写作", "编程", "学习"]
  },
  {
    id: "awesome-prompts",
    name: "awesome-prompts",
    url: "https://github.com/ai-boost/awesome-prompts",
    license: "GPL-3.0",
    summary: "提示词工程、智能体角色和专业工作流提示词合集；原仓库主要为英文原文。",
    categories: ["提示词工程", "智能体", "专业角色"]
  },
  {
    id: "youmind-awesome-gpt-image-2",
    name: "YouMind GPT Image 2",
    url: "https://github.com/YouMind-OpenLab/awesome-gpt-image-2",
    license: "CC-BY-4.0",
    summary: "GPT Image 2 创意图片提示词案例，优先导入中文 README。",
    categories: ["图片生成", "视觉风格", "案例"]
  },
  {
    id: "freestylefly-awesome-gpt-image-2",
    name: "freestylefly GPT Image 2",
    url: "https://github.com/freestylefly/awesome-gpt-image-2",
    license: "MIT",
    summary: "GPT Image 2 风格库与案例，来自中文 data/cases.json。",
    categories: ["图片生成", "结构化模板", "风格库"]
  },
  {
    id: "evolink-awesome-gpt-image-2-prompts",
    name: "EvoLinkAI GPT Image 2 Prompts",
    url: "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts",
    license: "Apache-2.0",
    summary: "商业视觉、海报、UI、电商和人物摄影提示词案例，优先导入中文 cases。",
    categories: ["图片生成", "商业视觉", "摄影"]
  }
];

const importers = [
  { sourceId: "prompt123", run: importPrompt123 },
  { sourceId: "awesome-chatgpt-prompts", run: importPromptsChat },
  { sourceId: "awesome-prompts", run: importAwesomePrompts },
  { sourceId: "youmind-awesome-gpt-image-2", run: importYouMindImagePrompts },
  { sourceId: "freestylefly-awesome-gpt-image-2", run: importFreestyleImagePrompts },
  { sourceId: "evolink-awesome-gpt-image-2-prompts", run: importEvoLinkImagePrompts }
];

async function main() {
  const entries = [];
  const sourceUpdates = new Map();

  for (const importer of importers) {
    const source = byId(importer.sourceId);
    try {
      const result = await importer.run();
      entries.push(...result.entries);
      sourceUpdates.set(source.id, result);
    } catch (error) {
      sourceUpdates.set(source.id, result(source, [], `${source.summary} 导入失败：${error.message}`));
      console.warn(`${source.name} import failed: ${error.message}`);
    }
  }

  const nextSources = sources.map((source) => {
    const update = sourceUpdates.get(source.id);
    const count = entries.filter((entry) => entry.sourceId === source.id).length;
    return {
      ...source,
      status: count > 0 ? "imported" : "pending",
      summary: update && update.note ? update.note : `${source.summary} 已导入 ${count} 条。`,
      entryCount: count
    };
  });

  const payload = {
    generatedAt: new Date().toISOString(),
    authorizedByUser: true,
    sources: nextSources,
    entries
  };

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(payload, null, 2), "utf8");
  console.log(`Imported ${entries.length} prompts into ${outputPath}`);
}

async function importPrompt123() {
  const source = byId("prompt123");
  const meta = await prompt123Json("/data/prompts-meta.json");
  const summary = await prompt123Json("/data/prompts-regular.summary.compact.json");
  const hot = await prompt123Json("/data/prompts-hot.compact.json");
  const detailChunks = meta.regularDetailChunks || 32;
  const detailMap = new Map();

  for (let index = 0; index < detailChunks; index += 1) {
    const chunk = await prompt123Json(`/data/prompt-content/regular-${String(index).padStart(2, "0")}.json`);
    (chunk.prompts || []).forEach((row) => {
      detailMap.set(String(row[0]), row[1]);
    });
  }

  const entries = dedupeEntries([
    ...unpackPrompt123Summary(summary, detailMap, source),
    ...unpackPrompt123Hot(hot, source)
  ]);
  return result(source, entries, `${source.summary} 已导入公开 JSON 数据 ${entries.length} 条。`);
}

async function importPromptsChat() {
  const source = byId("awesome-chatgpt-prompts");
  const text = await cdnText("f/prompts.chat", "prompts.csv");
  const rows = parseCsv(text);
  const header = rows.shift() || [];
  const actIndex = header.findIndex((name) => /act/i.test(name));
  const promptIndex = header.findIndex((name) => /prompt/i.test(name));
  const typeIndex = header.findIndex((name) => /type/i.test(name));
  const entries = rows
    .filter((row) => row[promptIndex] && row[promptIndex].trim())
    .map((row, index) => toEntry(source, {
      sourceItemId: slugify(row[actIndex] || `prompt-${index + 1}`),
      title: row[actIndex] || `Prompt ${index + 1}`,
      category: normalizeCategory(row[typeIndex] || "角色"),
      prompt: row[promptIndex],
      tags: ["ChatGPT", normalizeCategory(row[typeIndex] || "角色")]
    }));
  return result(source, entries, `${source.summary} 已导入 ${entries.length} 条。`);
}

async function importAwesomePrompts() {
  const source = byId("awesome-prompts");
  const repoDir = await downloadRepoZip("ai-boost/awesome-prompts", "main");
  const promptRoot = path.join(repoDir, "prompts");
  const promptPaths = (await listLocalFiles(promptRoot))
    .filter((filePath) => /\.(txt|md)$/i.test(filePath))
    .sort();
  const entries = [];
  for (const promptPath of promptPaths) {
    const prompt = await fs.readFile(promptPath, "utf8");
    const title = titleFromPath(path.relative(promptRoot, promptPath));
    entries.push(toEntry(source, {
      sourceItemId: path.relative(repoDir, promptPath).replace(/\\/g, "/"),
      title,
      category: inferWorkCategory(title, prompt),
      prompt,
      tags: ["专业角色", ...inferTags(`${title}\n${prompt}`, source.categories)]
    }));
  }
  return result(source, entries, `${source.summary} 已导入 prompts/ 目录 ${entries.length} 个文件。`);
}

async function importYouMindImagePrompts() {
  const source = byId("youmind-awesome-gpt-image-2");
  const text = await cdnText("YouMind-OpenLab/awesome-gpt-image-2", "README_zh.md");
  const cases = parseCasePromptSections(text, {
    titlePattern: /^###\s+No\.\s*(\d+):\s*(.+)$/gm,
    promptHeadingPattern: /^####\s+.*(?:Prompt|提示词)\s*$/m,
    category: "GPT Image 2"
  });
  const entries = cases.map((item) => toEntry(source, {
    sourceItemId: `case-${item.number || slugify(item.title)}`,
    title: item.title,
    category: item.category,
    prompt: item.prompt,
    tags: ["图片生成", "GPT Image 2", ...inferTags(item.prompt, source.categories)],
    sourceUrl: `${source.url}#no-${item.number}`
  }));
  return result(source, entries, `${source.summary} 已导入中文 README 中 ${entries.length} 个案例。`);
}

async function importFreestyleImagePrompts() {
  const source = byId("freestylefly-awesome-gpt-image-2");
  const payload = JSON.parse(await cdnText("freestylefly/awesome-gpt-image-2", "data/cases.json"));
  const entries = payload.cases
    .filter((item) => item.prompt && item.prompt.trim())
    .map((item) => toEntry(source, {
      sourceItemId: `case-${item.id}`,
      title: item.title || `Case ${item.id}`,
      category: translateImageCategory(item.category || "GPT Image 2"),
      prompt: item.prompt,
      tags: [...(item.styles || []), ...(item.scenes || [])].map(translateTag).slice(0, 8),
      sourceUrl: item.githubUrl || item.sourceUrl || source.url
    }));
  return result(source, entries, `${source.summary} 已导入 data/cases.json 中 ${entries.length} 个案例。`);
}

async function importEvoLinkImagePrompts() {
  const source = byId("evolink-awesome-gpt-image-2-prompts");
  const casePaths = [
    "cases/ad-creative_zh-CN.md",
    "cases/character_zh-CN.md",
    "cases/comparison_zh-CN.md",
    "cases/ecommerce_zh-CN.md",
    "cases/portrait_zh-CN.md",
    "cases/poster_zh-CN.md",
    "cases/ui_zh-CN.md"
  ];
  const entries = [];
  for (const casePath of casePaths) {
    const text = await cdnText("EvoLinkAI/awesome-gpt-image-2-API-and-Prompts", casePath);
    const category = translateEvoLinkCategory(casePath);
    const cases = parseCasePromptSections(text, {
      titlePattern: /^###\s+Case\s+(\d+):\s*(.+)$/gm,
      promptHeadingPattern: /^\*\*(?:Prompt|提示词)：?\*\*\s*$/m,
      category
    });
    entries.push(...cases.map((item) => toEntry(source, {
      sourceItemId: `${casePath}#case-${item.number || slugify(item.title)}`,
      title: item.title,
      category,
      prompt: item.prompt,
      tags: ["图片生成", category, ...inferTags(item.prompt, source.categories)],
      sourceUrl: `${source.url}/blob/main/${casePath}#case-${item.number}`
    })));
  }
  return result(source, entries, `${source.summary} 已导入中文 cases 下 ${casePaths.length} 个分类文件，共 ${entries.length} 个案例。`);
}

async function prompt123Json(filePath) {
  return JSON.parse(await fetchText(`https://prompt123.cn${filePath}`));
}

async function cdnText(repo, filePath) {
  return fetchText(`https://cdn.jsdelivr.net/gh/${repo}@main/${filePath}`);
}

async function fetchText(url) {
  const response = await fetchWithRetry(url, {
    headers: {
      "User-Agent": "love5000-prompt-library-importer"
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.text();
}

async function fetchWithRetry(url, options, attempts = 4) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      if (response.status === 429 || response.status >= 500) {
        lastError = new Error(`${response.status} ${response.statusText}`);
      } else {
        return response;
      }
    } catch (error) {
      lastError = error;
    } finally {
      clearTimeout(timeout);
    }
    await sleep(750 * attempt);
  }
  throw lastError;
}

async function downloadRepoZip(repo, branch) {
  await fs.mkdir(workDir, { recursive: true });
  const safeName = `${repo.replace(/[\\/]/g, "__")}-${branch}`;
  const zipPath = path.join(workDir, `${safeName}.zip`);
  const extractPath = path.join(workDir, safeName);
  const markerPath = path.join(extractPath, ".complete");
  try {
    await fs.access(markerPath);
    const children = await fs.readdir(extractPath, { withFileTypes: true });
    const root = children.find((child) => child.isDirectory() && child.name !== ".complete");
    if (root) {
      return path.join(extractPath, root.name);
    }
  } catch (error) {
    // Continue with a fresh download.
  }
  try {
    await fs.access(zipPath);
  } catch (error) {
    const response = await fetchWithRetry(`https://codeload.github.com/${repo}/zip/refs/heads/${branch}`, {
      headers: {
        "User-Agent": "love5000-prompt-library-importer"
      }
    }, 3);
    if (!response.ok) {
      throw new Error(`codeload ${repo}: ${response.status} ${response.statusText}`);
    }
    await fs.writeFile(zipPath, Buffer.from(await response.arrayBuffer()));
  }
  await fs.rm(extractPath, { recursive: true, force: true });
  await fs.mkdir(extractPath, { recursive: true });
  await execFileAsync("tar", ["-xf", zipPath, "-C", extractPath]);
  await fs.writeFile(markerPath, "ok", "utf8");
  const children = await fs.readdir(extractPath, { withFileTypes: true });
  const root = children.find((child) => child.isDirectory());
  if (!root) {
    throw new Error(`No extracted root for ${repo}`);
  }
  return path.join(extractPath, root.name);
}

async function listLocalFiles(root) {
  const entries = [];
  const items = await fs.readdir(root, { withFileTypes: true });
  for (const item of items) {
    const itemPath = path.join(root, item.name);
    if (item.isDirectory()) {
      entries.push(...await listLocalFiles(itemPath));
    } else if (item.isFile()) {
      entries.push(itemPath);
    }
  }
  return entries;
}

function unpackPrompt123Summary(payload, detailMap, source) {
  const topicTable = payload.topicTable || [];
  const facetTable = payload.facetTable || [];
  return (payload.prompts || [])
    .map((row) => {
      const id = String(row[0]);
      const prompt = detailMap.get(id) || row[4] || row[3] || "";
      return toEntry(source, {
        sourceItemId: `regular-${id}`,
        title: row[1] || `Prompt123 ${id}`,
        category: decodePrompt123Category(row[2], topicTable),
        prompt,
        tags: decodePrompt123Tags(row[2], topicTable, row[9], facetTable),
        sourceUrl: `https://prompt123.cn/prompt/${id}`
      });
    })
    .filter((entry) => entry.prompt);
}

function unpackPrompt123Hot(payload, source) {
  const topicTable = payload.topicTable || [];
  const facetTable = payload.facetTable || [];
  return (payload.prompts || [])
    .map((row) => {
      const id = String(row[0]);
      return toEntry(source, {
        sourceItemId: `hot-${id}`,
        title: row[1] || `Prompt123 ${id}`,
        category: decodePrompt123Category(row[3], topicTable),
        prompt: row[2] || "",
        tags: decodePrompt123Tags(row[3], topicTable, row[9], facetTable),
        sourceUrl: `https://prompt123.cn/prompt/${id}`
      });
    })
    .filter((entry) => entry.prompt);
}

function parseCasePromptSections(text, options) {
  const sections = [];
  const headings = Array.from(text.matchAll(options.titlePattern));
  for (let index = 0; index < headings.length; index += 1) {
    const heading = headings[index];
    const start = heading.index + heading[0].length;
    const end = index + 1 < headings.length ? headings[index + 1].index : text.length;
    const block = text.slice(start, end);
    const promptHeading = block.match(options.promptHeadingPattern);
    if (!promptHeading || promptHeading.index === undefined) {
      continue;
    }
    const afterHeading = block.slice(promptHeading.index + promptHeading[0].length);
    const fence = afterHeading.match(/```(?:json|text|[a-zA-Z-]+)?\s*\n([\s\S]*?)```/);
    if (!fence || !fence[1].trim()) {
      continue;
    }
    sections.push({
      number: heading[1],
      title: cleanMarkdown(heading[2]),
      category: options.category,
      prompt: fence[1].trim()
    });
  }
  return sections;
}

function toEntry(source, item) {
  return {
    id: `${source.id}-${slugify(item.sourceItemId || item.title)}`,
    sourceId: source.id,
    sourceName: source.name,
    sourceUrl: item.sourceUrl || source.url,
    license: source.license,
    status: "imported",
    title: String(item.title || "Untitled Prompt").trim(),
    category: String(item.category || "未分类").trim(),
    tags: Array.from(new Set((item.tags || []).filter(Boolean).map((tag) => String(tag).trim()))).slice(0, 10),
    prompt: String(item.prompt || "").trim()
  };
}

function result(source, entries, note) {
  return {
    sourceId: source.id,
    entries,
    note
  };
}

function byId(id) {
  const source = sources.find((item) => item.id === id);
  if (!source) {
    throw new Error(`Unknown source: ${id}`);
  }
  return source;
}

function decodePrompt123Category(topicIndexes, topicTable) {
  const topics = Array.isArray(topicIndexes)
    ? topicIndexes.map((index) => topicTable[index]).filter(Boolean)
    : [];
  return topics[0] || "Prompt123";
}

function decodePrompt123Tags(topicIndexes, topicTable, facetMask, facetTable) {
  const topics = Array.isArray(topicIndexes)
    ? topicIndexes.map((index) => topicTable[index]).filter(Boolean)
    : [];
  const facets = [];
  if (typeof facetMask === "number" && Number.isFinite(facetMask)) {
    for (let index = 0; index < facetTable.length; index += 1) {
      if (facetMask & (1 << index)) {
        facets.push(facetTable[index]);
      }
    }
  }
  return ["Prompt123", ...facets, ...topics].slice(0, 10);
}

function dedupeEntries(entries) {
  const seen = new Set();
  return entries.filter((entry) => {
    if (seen.has(entry.id)) {
      return false;
    }
    seen.add(entry.id);
    return true;
  });
}

function normalizeCategory(category) {
  const map = {
    TEXT: "文本",
    text: "文本",
    DEV: "开发",
    IMAGE: "图片",
    VIDEO: "视频"
  };
  return map[category] || category || "未分类";
}

function inferWorkCategory(title, prompt) {
  const text = `${title}\n${prompt}`.toLowerCase();
  if (/code|software|developer|engineer|api|cloud|security|devops/.test(text)) return "技术与编程";
  if (/writing|content|brand|marketing|community|creative/.test(text)) return "创意与写作";
  if (/agent|prompt|llm|ai|model|eval/.test(text)) return "AI 与智能体";
  if (/finance|legal|clinical|research|academic|compliance/.test(text)) return "专业领域";
  return "专业角色";
}

function inferTags(text, fallbackTags) {
  const lower = text.toLowerCase();
  const tags = [];
  const rules = [
    ["video", "视频"],
    ["image", "图片"],
    ["poster", "海报"],
    ["ui", "UI"],
    ["ecommerce", "电商"],
    ["character", "角色"],
    ["portrait", "人像"],
    ["agent", "智能体"],
    ["code", "编程"],
    ["security", "安全"],
    ["writing", "写作"],
    ["marketing", "营销"]
  ];
  rules.forEach(([needle, tag]) => {
    if (lower.includes(needle)) tags.push(tag);
  });
  return tags.length ? tags : fallbackTags.slice(0, 2);
}

function translateImageCategory(category) {
  const map = {
    "Architecture & Spaces": "建筑与空间",
    "Brand & Logos": "品牌与 Logo",
    "Characters & People": "角色与人物",
    "Charts & Infographics": "图表与信息图",
    "Documents & Publishing": "文档与出版",
    "History & Classical Themes": "历史与古典主题",
    "Illustration & Art": "插画与艺术",
    "Other Use Cases": "其他用途",
    "Photography & Realism": "摄影与真实感",
    "Posters & Typography": "海报与字体",
    "Products & E-commerce": "产品与电商",
    "Scenes & Storytelling": "场景与叙事",
    "UI & Interfaces": "UI 与界面"
  };
  return map[category] || category;
}

function translateEvoLinkCategory(filePath) {
  const map = {
    "ad-creative": "广告创意",
    character: "角色",
    comparison: "对比图",
    ecommerce: "电商",
    portrait: "人像摄影",
    poster: "海报",
    ui: "UI"
  };
  const name = path.basename(filePath).replace(/_zh-CN\.md$/i, "");
  return map[name] || titleFromPath(name);
}

function translateTag(tag) {
  const map = {
    "3D": "3D",
    Architecture: "建筑",
    Brand: "品牌",
    Character: "角色",
    Characters: "角色",
    Charts: "图表",
    Classical: "古典",
    Documents: "文档",
    History: "历史",
    Illustration: "插画",
    Infographic: "信息图",
    Photography: "摄影",
    Poster: "海报",
    Product: "产品",
    Products: "产品",
    Realistic: "真实感",
    Scenes: "场景",
    UI: "UI",
    Commerce: "商业",
    Creative: "创意",
    Education: "教育",
    Fashion: "时尚",
    Food: "美食",
    Social: "社交",
    Story: "叙事",
    Tech: "科技",
    Travel: "旅行"
  };
  return map[tag] || tag;
}

function titleFromPath(filePath) {
  return path.basename(filePath, path.extname(filePath))
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function slugify(value) {
  return String(value || "item")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "item";
}

function cleanMarkdown(value) {
  return String(value || "")
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/[`*_>#]/g, "")
    .trim();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (quoted && char === '"' && next === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (!quoted && char === ",") {
      row.push(cell);
      cell = "";
    } else if (!quoted && (char === "\n" || char === "\r")) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(cell);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  row.push(cell);
  if (row.some((value) => value.trim())) rows.push(row);
  return rows;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
