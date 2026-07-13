let stocks = [];
const AI_CHAT_STORAGE_KEY = "ashare-research-ai-chat-v1";
const SPRING_AI_AGENT_BASE_URL = "http://127.0.0.1:8090";

const state = {
  selectedCode: "",
  filter: "全部",
  liveData: false,
  aiConversation: [],
  latestAiAnalysis: "",
  aiGenerating: false,
  professionalReportGenerating: false,
  generatedDimensionAnalysis: "",
  generatedResearchConclusion: "",
  latestProfessionalReport: "",
  research: {
    activeTab: "overview",
    byCode: {},
    loading: {},
    aiSnapshot: null,
  },
};

const tradingState = {
  activeView: "research",
  date: today(),
  dashboard: null,
  loading: false,
};

const $ = (selector) => document.querySelector(selector);

const fallbackStocks = [];

function today() {
  return new Date().toISOString().slice(0, 10);
}

function formatNumber(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";
}

function formatMoney(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  if (Math.abs(value) >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(2)}万`;
  return value.toFixed(2);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function safeExternalUrl(value) {
  const allowedHosts = new Set([
    "pdf.dfcfw.com",
    "www.cninfo.com.cn",
    "disc.static.szse.cn",
    "np-anotice-stock.eastmoney.com",
  ]);
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" && allowedHosts.has(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}

function signedPercent(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function selectedStock() {
  return stocks.find((stock) => stock.code === state.selectedCode) || stocks[0] || null;
}

function classifyDirection(value) {
  return typeof value === "number" && value >= 0 ? "up" : "down";
}

function normalizeStock(stock) {
  return {
    ...stock,
    pool: stock.pool || "核心自选",
    watch_note: stock.watch_note || stock.note || "等待补充关注原因",
  };
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

async function requestForm(url, formData) {
  const response = await fetch(url, { method: "POST", body: formData });
  const payload = await response.json();
  if (!response.ok || payload.ok === false || payload.success === false) {
    throw new Error(payload.message || payload.error || "请求失败");
  }
  return payload;
}

async function loadTradingDashboard() {
  const date = $("#tradingDate").value || today();
  tradingState.date = date;
  const payload = await requestJson(`/api/trading/dashboard?date=${encodeURIComponent(date)}`, { cache: "no-store" });
  tradingState.dashboard = payload;
  renderTradingDashboard();
}

async function loadWatchlist(force = false) {
  if (window.location.protocol === "file:") {
    stocks = fallbackStocks;
    state.liveData = false;
    $("#sourceStatus").textContent = "离线示例，需 npm run start 启用真实数据";
    state.selectedCode = stocks[0]?.code || "";
    renderAll();
    return;
  }

  try {
    $("#sourceStatus").textContent = "正在拉取自选股真实行情";
    const payload = await requestJson(`/api/watchlist${force ? "?force=1" : ""}`, { cache: "no-store" });
    stocks = payload.stocks.map(normalizeStock);
    state.liveData = true;
    state.selectedCode = stocks.some((stock) => stock.code === state.selectedCode) ? state.selectedCode : stocks[0]?.code || "";
    $("#sourceStatus").textContent =
      payload.source.mode === "fallback"
        ? `行情暂不可用：已加载 ${payload.source.count} 只自选股档案`
        : `真实数据：${payload.source.provider} · ${payload.source.count} 只自选股`;
    renderAll();
    if (payload.errors?.length) {
      showToast(`有 ${payload.errors.length} 只股票行情暂时失败，已保留可用数据`);
    }
  } catch (error) {
    stocks = fallbackStocks;
    state.liveData = false;
    state.selectedCode = stocks[0].code;
    $("#sourceStatus").textContent = "真实数据连接失败，使用离线示例";
    renderAll();
    showToast(error.message || "真实数据连接失败");
  }
}

function renderAll() {
  renderMarketSummary();
  renderWatchlist();
  renderSelectedStock();
  renderResearchSection();
  renderAiChat();
  renderReviewDraft();
  if (selectedStock() && window.location.protocol !== "file:") {
    loadResearchSection("overview").catch((error) => showToast(error.message));
  }
}

function renderTradingDashboard() {
  const payload = tradingState.dashboard || {};
  const account = payload.account || {};
  const snapshot = account.snapshot || {};
  const metrics = [
    ["总资产", snapshot.total_assets],
    ["本金", account.principal],
    ["账户收益", snapshot.account_profit],
    ["收益率", typeof snapshot.account_profit_rate === "number" ? `${(snapshot.account_profit_rate * 100).toFixed(2)}%` : "--"],
    ["当日盈亏", snapshot.daily_profit],
    ["浮动盈亏", snapshot.floating_profit],
    ["总市值", snapshot.market_value],
    ["可用资金", snapshot.available_cash],
  ];
  $("#accountSummary").innerHTML = metrics
    .map(([label, value]) => `<div class="metric-item"><span>${label}</span><strong>${value ?? "--"}</strong></div>`)
    .join("");

  $("#capitalFlowList").innerHTML =
    (account.capital_flows || [])
      .map((flow) => `<div class="list-row">${flow.date} · ${flow.type} · ${flow.amount} · ${flow.note || ""}</div>`)
      .join("") || `<div class="list-row">当日暂无本金流水。</div>`;

  $("#tradeList").innerHTML =
    (payload.trades || [])
      .map((trade) => `<div class="list-row">${trade.trade_datetime} · ${trade.stock_code || "待补"} ${trade.stock_name} · ${trade.side} · ${trade.price} x ${trade.quantity} · ${trade.amount}</div>`)
      .join("") || `<div class="list-row">当日暂无确认交易。</div>`;

  $("#parseDraftList").innerHTML =
    (payload.parse_drafts || [])
      .map((draft) => `<div class="list-row"><strong>${draft.type}</strong> · ${draft.trade_date} · ${draft.status}<pre>${JSON.stringify(draft.parsed, null, 2)}</pre></div>`)
      .join("") || `<div class="list-row">暂无待确认解析结果。</div>`;
}

function switchMainView(view) {
  tradingState.activeView = view;
  document.querySelectorAll(".main-tab").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  $("#researchView").hidden = view !== "research";
  $("#tradingView").hidden = view !== "trading";
  if (view === "trading") {
    loadTradingDashboard().catch((error) => showToast(error.message));
  }
}

function renderMarketSummary() {
  const up = stocks.filter((stock) => (stock.pct_change || 0) >= 0).length;
  const down = stocks.length - up;
  const turnovers = stocks.map((stock) => stock.turnover_rate).filter((value) => typeof value === "number");
  const avgTurnover = turnovers.length ? turnovers.reduce((sum, value) => sum + value, 0) / turnovers.length : null;
  $("#marketBreadth").textContent = `${up} / ${down}`;
  $("#avgTurnover").textContent = avgTurnover === null ? "--" : `${avgTurnover.toFixed(2)}%`;
}

function renderWatchlist() {
  const rows = stocks.filter((stock) => state.filter === "全部" || stock.pool === state.filter);
  $("#selfStockList").innerHTML = rows
    .map((stock) => {
      const direction = classifyDirection(stock.pct_change);
      return `
        <button class="stock-row ${stock.code === state.selectedCode ? "active" : ""}" data-code="${stock.code}" type="button">
          <span>
            <strong>${stock.name}</strong>
            <small>${stock.code} · ${stock.pool} · ${stock.industry || "待映射"}</small>
          </span>
          <em class="${direction}">${signedPercent(stock.pct_change)}</em>
        </button>
      `;
    })
    .join("");
}

function renderSelectedStock() {
  const stock = selectedStock();
  if (!stock) {
    state.selectedCode = "";
    $("#selectedName").textContent = "请先加入股票";
    $("#selectedCode").textContent = "------";
    $("#stockPool").textContent = "自选股";
    $("#stockNote").textContent = "左侧加入一只股票后，这里会显示行情和多维度分析入口。";
    ["latestPrice", "pctChange", "quoteOpen", "quoteHigh", "quoteLow", "quotePrev", "quoteAmount", "quoteTurnover", "ma5Value", "ma10Value", "ma30Value"].forEach((id) => {
      $(`#${id}`).textContent = "--";
    });
    $("#latestTradeDate").textContent = "最新交易日 --";
    $("#maState").textContent = "--";
    $("#turnoverState").textContent = "--";
    $("#trendScore").textContent = "--";
    $("#riskLevel").textContent = "--";
    $("#confidenceBadge").textContent = "置信度 --";
    $("#aiConclusion").textContent = "等待加入股票。";
    $("#stockMemoryPath").textContent = "Obsidian/股票/--.md";
    $("#maChart").innerHTML = "";
    return;
  }
  state.selectedCode = stock.code;
  const direction = classifyDirection(stock.pct_change);
  $("#selectedName").textContent = stock.name;
  $("#selectedCode").textContent = stock.code;
  $("#stockPool").textContent = stock.pool || "核心自选";
  $("#stockNote").textContent = stock.watch_note || "等待补充关注原因";
  $("#latestPrice").textContent = formatNumber(stock.latest_price);
  $("#latestPrice").className = direction;
  $("#pctChange").textContent = signedPercent(stock.pct_change);
  $("#pctChange").className = direction;
  $("#quoteOpen").textContent = formatNumber(stock.open);
  $("#quoteHigh").textContent = formatNumber(stock.high);
  $("#quoteLow").textContent = formatNumber(stock.low);
  $("#quotePrev").textContent = formatNumber(stock.previous_close);
  $("#quoteAmount").textContent = formatMoney(stock.amount);
  $("#quoteTurnover").textContent = typeof stock.turnover_rate === "number" ? `${stock.turnover_rate.toFixed(2)}%` : "--";
  $("#ma5Value").textContent = formatNumber(stock.ma?.ma5);
  $("#ma10Value").textContent = formatNumber(stock.ma?.ma10);
  $("#ma30Value").textContent = formatNumber(stock.ma?.ma30);
  $("#latestTradeDate").textContent = `最新交易日 ${stock.source?.latest_trade_date || "--"}`;
  $("#maState").textContent = stock.ma_state || "--";
  $("#turnoverState").textContent = typeof stock.turnover_percentile === "number" ? `${stock.turnover_percentile}%` : "--";
  $("#trendScore").textContent = stock.trend_score ?? "--";
  $("#riskLevel").textContent = stock.risk || "--";
  $("#confidenceBadge").textContent = `置信度 ${stock.confidence || "--"}`;
  $("#aiConclusion").textContent = stock.conclusion || "等待真实行情加载。";
  $("#stockMemoryPath").textContent = `Obsidian/股票/${stock.code}-${stock.name}.md`;
  renderChart(stock);
}

function researchEntry(code = state.selectedCode) {
  if (!code) return null;
  if (!state.research.byCode[code]) {
    state.research.byCode[code] = {
      overview: null,
      capital: null,
      events: { reports: null, announcements: null },
    };
  }
  return state.research.byCode[code];
}

function providerName(provider) {
  const names = {
    tencent: "腾讯财经",
    eastmoney: "东方财富",
    sina: "新浪财经",
    cninfo: "巨潮资讯",
    szse: "深交所",
    tushare: "Tushare",
    fallback: "本地档案",
    local: "本地档案",
  };
  return names[provider] || provider || "未知来源";
}

function blockSource(block) {
  if (!block?.success) return "数据暂不可用";
  const timestamp = block.data_date || block.fetched_at?.replace("T", " ").slice(0, 16) || "时间待确认";
  return `${providerName(block.provider)} · ${timestamp}${block.fallback_used ? " · 备用源" : ""}`;
}

function researchLoadingKey(code, section, kind = "all") {
  return `${code}:${section}:${kind}`;
}

async function loadResearchSection(section, force = false, options = {}) {
  const code = state.selectedCode;
  if (!code) return;
  const entry = researchEntry(code);
  const kind = options.kind || "all";
  const page = options.page || 1;
  const pageSize = options.pageSize || 10;
  if (!force) {
    if (section !== "events" && entry[section]) return;
    if (section === "events" && kind !== "all" && entry.events[kind] && page === 1) return;
    if (section === "events" && kind === "all" && entry.events.reports && entry.events.announcements) return;
  }

  const loadingKey = researchLoadingKey(code, section, kind);
  if (state.research.loading[loadingKey]) return;
  state.research.loading[loadingKey] = true;
  renderResearchSection();
  try {
    const query = new URLSearchParams();
    if (force) query.set("force", "1");
    if (section === "events") {
      query.set("kind", kind);
      query.set("page", String(page));
      query.set("page_size", String(pageSize));
    }
    const suffix = query.toString() ? `?${query}` : "";
    const payload = await requestJson(`/api/stocks/${encodeURIComponent(code)}/research/${section}${suffix}`, {
      cache: "no-store",
    });
    if (state.selectedCode !== code) return;
    if (section === "events") {
      Object.entries(payload.blocks || {}).forEach(([blockName, block]) => {
        const existing = entry.events[blockName];
        if (page > 1 && existing?.success && block?.success) {
          entry.events[blockName] = {
            ...block,
            data: {
              ...block.data,
              items: [...(existing.data?.items || []), ...(block.data?.items || [])],
            },
          };
        } else {
          entry.events[blockName] = block;
        }
      });
    } else {
      entry[section] = payload;
    }
  } finally {
    delete state.research.loading[loadingKey];
    if (state.selectedCode === code) renderResearchSection();
  }
}

function renderResearchSection() {
  const code = state.selectedCode;
  const entry = researchEntry(code);
  document.querySelectorAll("[data-research-tab]").forEach((button) => {
    const active = button.dataset.researchTab === state.research.activeTab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  ["overview", "capital", "events"].forEach((section) => {
    const panel = $(`#research${section[0].toUpperCase()}${section.slice(1)}Panel`);
    if (panel) panel.hidden = section !== state.research.activeTab;
  });

  if (!code || !entry) {
    $("#researchSectionStatus").textContent = "等待选择股票";
    $("#researchOverviewContent").innerHTML = researchEmpty("选择自选股后加载研究数据");
    ["fundFlowBlock", "marginBlock", "shareholdersBlock", "lockupsBlock"].forEach((id) => {
      $(`#${id}`).innerHTML = researchEmpty("等待选择股票");
    });
    $("#reportsList").innerHTML = researchEmpty("等待选择股票");
    $("#announcementsList").innerHTML = researchEmpty("等待选择股票");
    return;
  }

  const activeLoading = Object.keys(state.research.loading).some((key) =>
    key.startsWith(`${code}:${state.research.activeTab}:`),
  );
  $("#researchSectionStatus").textContent = activeLoading ? "正在更新" : "按来源实时校验";
  renderResearchOverview(entry.overview, activeLoading && state.research.activeTab === "overview");
  renderResearchCapital(entry.capital, activeLoading && state.research.activeTab === "capital");
  renderResearchEvents(entry.events, activeLoading && state.research.activeTab === "events");
}

function researchEmpty(message) {
  return `<div class="research-empty">${escapeHtml(message)}</div>`;
}

function researchSkeleton(lines = 3) {
  return `<div class="research-loading" aria-label="数据加载中">${Array.from(
    { length: lines },
    (_, index) => `<span style="--skeleton-width:${82 - index * 13}%"></span>`,
  ).join("")}</div>`;
}

function metricValue(value, suffix = "") {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)}${suffix}` : "--";
}

function renderResearchOverview(payload, loading) {
  const container = $("#researchOverviewContent");
  if (!payload) {
    container.innerHTML = loading ? researchSkeleton(4) : researchEmpty("概览将在选择股票后自动加载");
    return;
  }
  const valuation = payload.blocks?.valuation;
  const metadata = payload.blocks?.metadata;
  const data = valuation?.data || {};
  const metrics = [
    ["PE(TTM)", metricValue(data.pe_ttm)],
    ["PB", metricValue(data.pb)],
    ["总市值", metricValue(data.market_cap_yi, " 亿")],
    ["流通市值", metricValue(data.float_market_cap_yi, " 亿")],
    ["量比", metricValue(data.volume_ratio)],
    ["振幅", metricValue(data.amplitude, "%")],
  ];
  const concepts = metadata?.data?.concepts || [];
  container.innerHTML = `
    <div class="research-metric-grid">
      ${metrics
        .map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`)
        .join("")}
    </div>
    <div class="research-overview-details">
      <div><span>行业</span><strong>${escapeHtml(metadata?.data?.industry || "待映射")}</strong></div>
      <div><span>涨停 / 跌停</span><strong>${escapeHtml(metricValue(data.limit_up))} / ${escapeHtml(metricValue(data.limit_down))}</strong></div>
    </div>
    <div class="concept-chip-list">
      ${concepts.length ? concepts.map((concept) => `<span>${escapeHtml(concept)}</span>`).join("") : "<span>暂无概念标签</span>"}
    </div>
    <div class="research-source-row">
      <span>${escapeHtml(blockSource(valuation))}</span>
      <span>${escapeHtml(blockSource(metadata))}</span>
    </div>
  `;
}

function renderResearchCapital(payload, loading) {
  const blocks = payload?.blocks || {};
  const configurations = [
    ["fundFlowBlock", "资金流", blocks.fund_flow, (data) => [
      ["当日主力净流入", formatMoney(data.today_main_net)],
      ["近 5 日", data.five_day_direction || "--"],
      ["近 20 日", data.twenty_day_direction || "--"],
    ]],
    ["marginBlock", "融资融券", blocks.margin, (data) => [
      ["融资余额", formatMoney(data.latest_balance)],
      ["较上一期", formatMoney(data.balance_change)],
      ["两融合计", formatMoney(data.total_balance)],
    ]],
    ["shareholdersBlock", "股东户数", blocks.shareholders, (data) => [
      ["最新户数", data.holder_count ?? "--"],
      ["环比变化", metricValue(data.change_ratio, "%")],
      ["户均持股", metricValue(data.average_shares)],
    ]],
    ["lockupsBlock", "未来 90 天解禁", blocks.lockups, (data) => {
      const first = data.upcoming?.[0];
      return [
        ["待解禁批次", data.upcoming?.length ?? 0],
        ["最近日期", first?.date || "暂无"],
        ["实际可流通", first ? metricValue(first.able_shares, " 万股") : "--"],
      ];
    }],
  ];
  configurations.forEach(([id, title, block, rows]) => {
    const element = $(`#${id}`);
    if (!payload) {
      element.innerHTML = loading ? researchSkeleton(3) : researchEmpty("打开标签后加载");
      return;
    }
    if (!block?.success) {
      element.innerHTML = `<div class="research-data-title"><h4>${title}</h4></div>${researchEmpty(block?.message || "数据暂不可用")}`;
      return;
    }
    element.innerHTML = `
      <div class="research-data-title"><h4>${title}</h4><span>${escapeHtml(blockSource(block))}</span></div>
      <dl>${rows(block.data || {})
        .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
        .join("")}</dl>
    `;
  });
}

function renderResearchEvents(events, loading) {
  renderResearchEventList("reports", events?.reports, loading);
  renderResearchEventList("announcements", events?.announcements, loading);
}

function renderResearchEventList(kind, block, loading) {
  const list = kind === "reports" ? $("#reportsList") : $("#announcementsList");
  const source = kind === "reports" ? $("#reportsSource") : $("#announcementsSource");
  const button = kind === "reports" ? $("#loadMoreReportsBtn") : $("#loadMoreAnnouncementsBtn");
  if (!block) {
    list.innerHTML = loading ? researchSkeleton(4) : researchEmpty("打开标签后加载");
    source.textContent = "--";
    button.hidden = true;
    return;
  }
  source.textContent = blockSource(block);
  if (!block.success) {
    list.innerHTML = researchEmpty(block.message || "数据暂不可用");
    button.hidden = true;
    return;
  }
  const items = block.data?.items || [];
  list.innerHTML = items.length
    ? items
        .map((item) => {
          const url = safeExternalUrl(item.url);
          const title = escapeHtml(item.title || "未命名记录");
          const titleHtml = url
            ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`
            : `<span>${title}</span>`;
          const meta =
            kind === "reports"
              ? `${item.date || "--"} · ${item.organization || "机构待确认"} · ${item.rating || "未评级"}`
              : `${item.date || "--"} · ${item.type || "公告"}`;
          return `<article>${titleHtml}<small>${escapeHtml(meta)}</small></article>`;
        })
        .join("")
    : researchEmpty("暂无数据");
  button.hidden = !block.data?.has_more;
  button.disabled = loading;
}

function buildClientResearchSnapshot() {
  const entry = researchEntry();
  if (!entry) return null;
  const flatten = (section) => {
    const result = {};
    Object.entries(section?.blocks || section || {}).forEach(([name, block]) => {
      if (!block) return;
      result[name] = block.success
        ? {
            success: true,
            provider: block.provider,
            data_date: block.data_date,
            fallback_used: Boolean(block.fallback_used),
            ...(block.data || {}),
          }
        : { success: false, message: block.message };
    });
    return result;
  };
  return {
    code: state.selectedCode,
    overview: flatten(entry.overview),
    capital: flatten(entry.capital),
    events: flatten(entry.events),
  };
}

function switchResearchTab(tab) {
  state.research.activeTab = tab;
  renderResearchSection();
  loadResearchSection(tab).catch((error) => showToast(error.message));
}

function loadMoreResearchEvents(kind) {
  const entry = researchEntry();
  const current = entry?.events?.[kind];
  const nextPage = (current?.data?.page || 1) + 1;
  loadResearchSection("events", false, { kind, page: nextPage, pageSize: 10 }).catch((error) =>
    showToast(error.message),
  );
}

function renderChart(stock) {
  const chart = Array.isArray(stock.chart) && stock.chart.length ? stock.chart : [];
  if (!chart.length) {
    $("#maChart").innerHTML = "";
    return;
  }
  const close = chart.map((item) => (typeof item === "number" ? item : item.close));
  const ma5 = chart.map((item, index) => (typeof item === "number" ? average(close, 5)[index] : item.ma5));
  const ma10 = chart.map((item, index) => (typeof item === "number" ? average(close, 10)[index] : item.ma10));
  const ma30 = chart.map((item, index) => (typeof item === "number" ? average(close, 30)[index] : item.ma30));
  const values = [...close, ...ma5, ...ma10, ...ma30].filter((value) => typeof value === "number" && Number.isFinite(value));
  const grid = [40, 84, 128, 172, 216].map((y) => `<line x1="24" y1="${y}" x2="696" y2="${y}" stroke="#e8efec"/>`).join("");
  const volumes = chart
    .slice(-18)
    .map((item, index) => {
      const rate = typeof item === "number" ? 0.5 + index * 0.05 : item.turnover_rate || 0.2;
      const height = Math.max(8, Math.min(46, rate * 10));
      const width = 672 / 18 - 4;
      const x = 24 + index * (672 / 18);
      const y = 246 - height;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${width.toFixed(1)}" height="${height.toFixed(1)}" rx="2" fill="${
        index % 3 === 0 ? "#df565b" : "#17977f"
      }" opacity="0.9"/>`;
    })
    .join("");
  $("#maChart").innerHTML = `
    ${grid}
    <polyline points="${seriesPoints(close, values)}" fill="none" stroke="#87929a" stroke-width="1.5"/>
    <polyline points="${seriesPoints(ma30, values)}" fill="none" stroke="#8b5cf6" stroke-width="2.1"/>
    <polyline points="${seriesPoints(ma10, values)}" fill="none" stroke="#176bd1" stroke-width="2.2"/>
    <polyline points="${seriesPoints(ma5, values)}" fill="none" stroke="#db8718" stroke-width="2.4"/>
    ${volumes}
  `;
}

function average(values, windowSize) {
  return values.map((_, index) => {
    const start = Math.max(0, index - windowSize + 1);
    const slice = values.slice(start, index + 1);
    return slice.reduce((sum, value) => sum + value, 0) / slice.length;
  });
}

function seriesPoints(values, allValues) {
  const clean = values.filter((value) => typeof value === "number" && Number.isFinite(value));
  if (!clean.length || !allValues.length) return "";
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const step = 672 / Math.max(1, values.length - 1);
  return values
    .map((value, index) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return null;
      const x = 24 + index * step;
      const y = 220 - ((value - min) / range) * 178;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function loadAiChatState() {
  try {
    const savedChat = JSON.parse(localStorage.getItem(AI_CHAT_STORAGE_KEY) || "{}");
    state.aiConversation = Array.isArray(savedChat.messages) ? savedChat.messages : [];
    state.latestAiAnalysis = savedChat.latestAiAnalysis || "";
  } catch {
    state.aiConversation = [];
  }
}

function saveAiChatState() {
  localStorage.setItem(
    AI_CHAT_STORAGE_KEY,
    JSON.stringify({
      messages: state.aiConversation.slice(-16),
      latestAiAnalysis: state.latestAiAnalysis,
    }),
  );
}

function getReviewState() {
  return {
    analysisFocus: $("#analysisFocus").value,
    technicalNotes: $("#technicalNotes").value.trim(),
    volumeNotes: $("#volumeNotes").value.trim(),
    fundamentalNotes: $("#fundamentalNotes").value.trim(),
    riskNotes: $("#riskNotes").value.trim(),
    planNotes: $("#planNotes").value.trim(),
  };
}

function setReviewState(analysis) {
  $("#technicalNotes").value = analysis.technical_notes || "";
  $("#volumeNotes").value = analysis.volume_notes || "";
  $("#fundamentalNotes").value = analysis.fundamental_notes || "";
  $("#riskNotes").value = analysis.risk_notes || "";
  $("#planNotes").value = analysis.plan_notes || "";
  state.generatedDimensionAnalysis = analysis.dimension_analysis || "";
  state.generatedResearchConclusion = analysis.research_conclusion || "";
  renderReviewDraft();
}

function buildDimensionAnalysis(stock, review) {
  if (state.generatedDimensionAnalysis) return state.generatedDimensionAnalysis;
  const technical = review.technicalNotes || `${stock.ma_state || "技术结构待确认"}，MA5 ${formatNumber(stock.ma?.ma5)}，MA10 ${formatNumber(stock.ma?.ma10)}，MA30 ${formatNumber(stock.ma?.ma30)}。`;
  const volume = review.volumeNotes || `换手率 ${typeof stock.turnover_rate === "number" ? `${stock.turnover_rate.toFixed(2)}%` : "--"}，换手分位 ${stock.turnover_percentile ?? "--"}%。`;
  const fundamental = review.fundamentalNotes || `${stock.industry || "行业待映射"} / ${stock.board || "A股"}，需要结合板块强度、公司事件和估值位置继续核验。`;
  const risk = review.riskNotes || `当前风险等级：${stock.risk || "--"}。重点观察趋势失效、换手异常放大和板块退潮。`;
  return `【技术】${technical}【量能】${volume}【基本面/板块】${fundamental}【风险】${risk}`;
}

function buildResearchConclusion(stock, review) {
  if (state.generatedResearchConclusion) return state.generatedResearchConclusion;
  const focus = review.analysisFocus || "综合复盘";
  const plan = review.planNotes || "下一步先补齐关键数据，再等待技术结构、量能和板块方向形成一致信号。";
  return `${stock.name} 当前分析重点为“${focus}”。结论不直接给出买卖动作，而是沉淀可复盘的判断条件：趋势是否延续、量能是否支持、板块是否共振、风险是否可被明确反证。观察计划：${plan}`;
}

function renderReviewDraft() {
  const stock = selectedStock();
  if (!stock) {
    $("#dimensionAnalysis").textContent = "加入股票后可生成。";
    $("#researchConclusion").textContent = "等待股票。";
    $("#memoryPreview").value = "";
    return;
  }
  const review = getReviewState();
  const dimensionAnalysis = buildDimensionAnalysis(stock, review);
  const researchConclusion = buildResearchConclusion(stock, review);
  const aiBlock = state.latestAiAnalysis
    ? `
> [!note] AI 对话补充
> ${state.latestAiAnalysis.replace(/\n/g, "\n> ")}
`
    : "";
  $("#dimensionAnalysis").textContent = dimensionAnalysis;
  $("#researchConclusion").textContent = researchConclusion;
  $("#memoryPreview").value = `### ${$("#reviewDate").value || today()} ${stock.code} ${stock.name} 多维度分析

- 分组：${stock.pool || "核心自选"}
- 分析重点：${review.analysisFocus}
- 最新价：${formatNumber(stock.latest_price)}
- 涨跌幅：${signedPercent(stock.pct_change)}
- 换手率：${typeof stock.turnover_rate === "number" ? `${stock.turnover_rate.toFixed(2)}%` : "--"}
- 技术结构：${stock.ma_state || "--"}
- 风险等级：${stock.risk || "--"}

#### 技术结构

${review.technicalNotes || "未填写"}

#### 量能与换手

${review.volumeNotes || "未填写"}

#### 基本面与板块

${review.fundamentalNotes || "未填写"}

#### 风险与反证

${review.riskNotes || "未填写"}

#### 观察计划

${review.planNotes || "未填写"}

> [!summary] 维度分析
> ${dimensionAnalysis}

> [!check] 研究结论
> ${researchConclusion}
${aiBlock}
`;
}

function buildLocalAiReply(question) {
  const stock = selectedStock();
  if (!stock) return "请先加入并选择一只股票。";
  const review = getReviewState();
  return [
    `基于当前上下文，${stock.name} 的分析锚点是：${stock.ma_state || "技术结构待确认"}，换手分位 ${stock.turnover_percentile ?? "--"}%，风险等级 ${stock.risk || "--"}。`,
    `你当前聚焦“${review.analysisFocus}”。我会优先把问题拆成四层：技术是否有效、量能是否确认、板块/基本面是否共振、风险反证是否清楚。`,
    `针对你的问题“${question}”，当前最值得写入长期记忆的是：不要只记录结论，要记录结论成立所依赖的条件，以及什么情况会推翻它。`,
  ].join("\n");
}

function renderAiChat() {
  const log = $("#aiChatLog");
  if (!state.aiConversation.length) {
    log.innerHTML = `<p class="ai-chat-empty">等待对话。</p>`;
    return;
  }
  log.innerHTML = state.aiConversation
    .slice(-8)
    .map(
      (message) => `
        <div class="chat-message ${message.role}">
          <span>${message.role === "user" ? "我" : "AI"}</span>
          <p>${message.content.replace(/</g, "&lt;").replace(/\n/g, "<br />")}</p>
        </div>
      `,
    )
    .join("");
  log.scrollTop = log.scrollHeight;
}

async function sendAiMessage(event) {
  event.preventDefault();
  const input = $("#aiChatInput");
  const question = input.value.trim();
  if (!question) return;
  state.aiConversation.push({ role: "user", content: question, at: new Date().toISOString() });
  const answer = buildLocalAiReply(question);
  state.aiConversation.push({ role: "assistant", content: answer, at: new Date().toISOString() });
  state.latestAiAnalysis = answer;
  input.value = "";
  saveAiChatState();
  renderAiChat();
  renderReviewDraft();
}

function appendAiAnalysisToDraft() {
  if (!state.latestAiAnalysis) {
    showToast("先完成一次 AI 对话，再加入复盘草稿");
    return;
  }
  renderReviewDraft();
  showToast("AI 对话分析已加入复盘草稿，保存时会写入 Obsidian");
}

async function addStock(event) {
  event.preventDefault();
  const payload = {
    code: $("#newStockCode").value.trim(),
    pool: $("#newStockPool").value,
    industry: $("#newStockIndustry").value.trim(),
    note: $("#newStockNote").value.trim(),
  };
  try {
    const result = await requestJson("/api/watchlist", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.selectedCode = result.stock.code;
    $("#addStockForm").reset();
    showToast(`已加入 ${result.stock.name}，并创建/更新 Obsidian 股票文件`);
    await loadWatchlist(true);
  } catch (error) {
    showToast(error.message);
  }
}

async function deleteSelectedStock() {
  const stock = selectedStock();
  if (!stock?.code) return;
  try {
    await requestJson(`/api/watchlist?code=${encodeURIComponent(stock.code)}`, { method: "DELETE" });
    showToast(`已将 ${stock.name} 移出自选股池，历史文件保留在 Obsidian`);
    state.selectedCode = "";
    await loadWatchlist(true);
  } catch (error) {
    showToast(error.message);
  }
}

async function generateDimensionAnalysis() {
  const stock = selectedStock();
  if (!stock) {
    showToast("请先加入一只股票");
    return;
  }
  if (state.aiGenerating) return;
  state.aiGenerating = true;
  const button = $("#generateAnalysisBtn");
  button.disabled = true;
  button.textContent = "AI 生成中";
  try {
    const result = await requestJson("/api/ai/dimension-analysis", {
      method: "POST",
      body: JSON.stringify({
        stock,
        review: getReviewState(),
      }),
    });
    state.research.aiSnapshot = result.research_snapshot || null;
    state.latestAiAnalysis = result.analysis.research_conclusion || result.analysis.dimension_analysis || "";
    setReviewState(result.analysis);
    saveAiChatState();
    showToast("DeepSeek 已生成多维度分析");
  } catch (error) {
    showToast(error.message || "AI 生成失败");
  } finally {
    state.aiGenerating = false;
    button.disabled = false;
    button.textContent = "AI 生成维度分析";
  }
}

async function generateProfessionalReport() {
  const stock = selectedStock();
  if (!stock) {
    showToast("请先加入一只股票");
    return;
  }
  if (state.professionalReportGenerating) return;
  state.professionalReportGenerating = true;
  const button = $("#generateProfessionalReportBtn");
  const status = $("#professionalReportStatus");
  const output = $("#professionalReportOutput");
  button.disabled = true;
  button.textContent = "报告生成中";
  status.textContent = "正在连接 SpringAI";
  output.value = "正在生成综合型专业研究报告，请稍候...";
  try {
    await Promise.all([loadResearchSection("capital"), loadResearchSection("events")]);
    const researchQuestion = [
      `请为 ${stock.code} ${stock.name} 生成一份综合型专业股票研究报告。`,
      "全程使用中文，报告标题、章节标题、正文、表格字段和风险提示都必须是中文。",
      "不要输出英文标题，不要输出英文段落，不要使用英文分析框架名称。",
      "重点关注趋势结构、量价关系、板块与基本面核验、交易复盘关联、核心假设、反证条件、风险矩阵和后续观察计划。",
      "只做研究分析和风险提示，不给出确定性买卖指令，不承诺收益。",
    ].join("\n");
    const payload = {
      stockCode: stock.code,
      reportType: "comprehensive",
      language: "zh-CN",
      outputRequirements: [
        "全程使用中文。",
        "不要输出英文标题。",
        "不要输出英文段落。",
        "保留非投资建议和风险提示边界。",
      ],
      researchQuestion,
      includeTradingReview: true,
      autoPersist: false,
      researchSnapshot: state.research.aiSnapshot || buildClientResearchSnapshot(),
    };
    const result = await requestJson(`${SPRING_AI_AGENT_BASE_URL}/api/agent/reports/stock`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const report = result.markdown || "SpringAI Agent 未返回报告正文。";
    state.latestProfessionalReport = report;
    output.value = report;
    status.textContent = `${result.observationLevel || "watch"} / ${result.riskLevel || "risk"}`;
    showToast("专业研究报告已生成");
  } catch (error) {
    status.textContent = "SpringAI 未连接";
    output.value = `生成失败：${error.message || "请确认 SpringAI Agent 已启动在 http://127.0.0.1:8090"}`;
    showToast(error.message || "专业报告生成失败");
  } finally {
    state.professionalReportGenerating = false;
    button.disabled = false;
    button.textContent = "生成专业报告";
  }
}

async function saveStockReview(event) {
  event.preventDefault();
  const stock = selectedStock();
  if (!stock) {
    showToast("请先加入一只股票");
    return;
  }
  const review = getReviewState();
  const payload = {
    date: $("#reviewDate").value || today(),
    stock_code: stock.code,
    stock_name: stock.name,
    industry: stock.industry,
    board: stock.board,
    pool: stock.pool,
    concepts: stock.concepts || [],
    analysis_focus: review.analysisFocus,
    technical_notes: review.technicalNotes,
    volume_notes: review.volumeNotes,
    fundamental_notes: review.fundamentalNotes,
    risk_notes: review.riskNotes,
    plan_notes: review.planNotes,
    ai_summary: $("#dimensionAnalysis").textContent,
    evaluation: $("#researchConclusion").textContent,
    professional_report: state.latestProfessionalReport || $("#professionalReportOutput")?.value || "",
    ai_dialogue: state.aiConversation.slice(-8),
    ai_dialogue_summary: state.latestAiAnalysis,
    quote_snapshot: {
      latest_price: formatNumber(stock.latest_price),
      pct_change: signedPercent(stock.pct_change),
      turnover_rate: typeof stock.turnover_rate === "number" ? `${stock.turnover_rate.toFixed(2)}%` : "--",
      turnover_percentile: stock.turnover_percentile,
      distribution_score: stock.distribution_score,
      ma_state: stock.ma_state,
      risk: stock.risk || "--",
    },
    research_snapshot: state.research.aiSnapshot || buildClientResearchSnapshot(),
  };
  try {
    const result = await requestJson("/api/obsidian/stock-daily-review", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(`已写入该股票长期记忆：${result.stock_path}`);
  } catch (error) {
    showToast(error.message);
  }
}

async function saveCapitalFlow(event) {
  event.preventDefault();
  const payload = {
    date: $("#tradingDate").value || today(),
    type: $("#capitalFlowType").value,
    amount: Number($("#capitalFlowAmount").value),
    note: $("#capitalFlowNote").value.trim(),
  };
  try {
    await requestJson("/api/trading/capital-flows", { method: "POST", body: JSON.stringify(payload) });
    $("#capitalFlowForm").reset();
    await loadTradingDashboard();
    showToast("本金流水已保存");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveManualTrade(event) {
  event.preventDefault();
  const payload = {
    trade_datetime: $("#tradeTime").value ? new Date($("#tradeTime").value).toISOString() : `${$("#tradingDate").value || today()}T15:00:00+08:00`,
    stock_code: $("#tradeStockCode").value.trim(),
    stock_name: $("#tradeStockName").value.trim(),
    side: $("#tradeSide").value,
    price: Number($("#tradePrice").value),
    quantity: Number($("#tradeQuantity").value),
    amount: Number($("#tradeAmount").value),
  };
  try {
    await requestJson("/api/trading/trades", { method: "POST", body: JSON.stringify(payload) });
    $("#manualTradeForm").reset();
    await loadTradingDashboard();
    showToast("交易记录已保存");
  } catch (error) {
    showToast(error.message);
  }
}

async function uploadTradingScreenshot(event, inputId, endpoint) {
  event.preventDefault();
  const file = $(`#${inputId}`).files[0];
  if (!file) {
    showToast("请先选择截图");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("trade_date", $("#tradingDate").value || today());
  try {
    await requestForm(endpoint, formData);
    await loadTradingDashboard();
    showToast("截图解析草稿已生成，请确认后入账");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveDailyReview(event) {
  event.preventDefault();
  const dashboard = tradingState.dashboard || {};
  const payload = {
    date: $("#tradingDate").value || today(),
    snapshot: dashboard.account?.snapshot || {},
    trades: dashboard.trades || [],
    review: {
      summary: $("#dailySummary").value.trim(),
      did_well: $("#dailyDidWell").value.trim(),
      mistake: $("#dailyMistake").value.trim(),
      position_review: $("#dailyPositionReview").value.trim(),
      emotion_review: $("#dailyEmotionReview").value.trim(),
      next_plan: $("#dailyNextPlan").value.trim(),
      lesson: $("#dailyLesson").value.trim(),
    },
  };
  try {
    await requestJson("/api/trading/daily-review", { method: "POST", body: JSON.stringify(payload) });
    showToast("每日交易复盘已写入 Obsidian");
  } catch (error) {
    showToast(error.message);
  }
}

function bindEvents() {
  $("#reviewDate").value = today();
  $("#tradingDate").value = today();
  $("#addStockForm").addEventListener("submit", addStock);
  $("#deleteStockBtn").addEventListener("click", deleteSelectedStock);
  $("#refreshBtn").addEventListener("click", async () => {
    await loadWatchlist(true);
    await loadResearchSection(state.research.activeTab, true).catch((error) => showToast(error.message));
  });
  document.querySelectorAll("[data-research-tab]").forEach((button) => {
    button.addEventListener("click", () => switchResearchTab(button.dataset.researchTab));
  });
  $("#loadMoreReportsBtn").addEventListener("click", () => loadMoreResearchEvents("reports"));
  $("#loadMoreAnnouncementsBtn").addEventListener("click", () => loadMoreResearchEvents("announcements"));
  document.querySelectorAll(".main-tab").forEach((button) => {
    button.addEventListener("click", () => switchMainView(button.dataset.view));
  });
  $("#tradingDate").addEventListener("change", () => loadTradingDashboard().catch((error) => showToast(error.message)));
  $("#capitalFlowForm").addEventListener("submit", saveCapitalFlow);
  $("#manualTradeForm").addEventListener("submit", saveManualTrade);
  $("#accountScreenshotForm").addEventListener("submit", (event) =>
    uploadTradingScreenshot(event, "accountScreenshotInput", "/api/trading/parse/account-screenshot"),
  );
  $("#tradesScreenshotForm").addEventListener("submit", (event) =>
    uploadTradingScreenshot(event, "tradesScreenshotInput", "/api/trading/parse/trades-screenshot"),
  );
  $("#dailyReviewForm").addEventListener("submit", saveDailyReview);
  $("#selfStockList").addEventListener("click", (event) => {
    const row = event.target.closest("[data-code]");
    if (!row) return;
    if (state.selectedCode !== row.dataset.code) {
      state.research.aiSnapshot = null;
    }
    state.selectedCode = row.dataset.code;
    renderAll();
  });
  document.querySelectorAll(".watch-tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".watch-tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      state.filter = button.dataset.filter;
      renderWatchlist();
    });
  });
  ["analysisFocus", "technicalNotes", "volumeNotes", "fundamentalNotes", "riskNotes", "planNotes", "reviewDate"].forEach((id) => {
    $(`#${id}`).addEventListener("input", () => {
      state.generatedDimensionAnalysis = "";
      state.generatedResearchConclusion = "";
      renderReviewDraft();
    });
    $(`#${id}`).addEventListener("change", renderReviewDraft);
  });
  $("#reviewForm").addEventListener("submit", saveStockReview);
  $("#generateAnalysisBtn").addEventListener("click", generateDimensionAnalysis);
  $("#generateProfessionalReportBtn").addEventListener("click", generateProfessionalReport);
  $("#sendAiChatBtn").addEventListener("click", sendAiMessage);
  $("#appendAiMemoryBtn").addEventListener("click", appendAiAnalysisToDraft);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2400);
}

loadAiChatState();
bindEvents();
loadWatchlist();
