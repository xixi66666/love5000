const state = {
    busy: false,
};

const els = {
    serviceStatus: document.querySelector("#serviceStatus"),
    providerStatus: document.querySelector("#providerStatus"),
    modelStatus: document.querySelector("#modelStatus"),
    notice: document.querySelector("#notice"),
    syncButton: document.querySelector("#syncButton"),
    scoreButton: document.querySelector("#scoreButton"),
    backtestButton: document.querySelector("#backtestButton"),
    startDate: document.querySelector("#startDate"),
    endDate: document.querySelector("#endDate"),
    scoreDate: document.querySelector("#scoreDate"),
    indexCodes: document.querySelector("#indexCodes"),
    initialCash: document.querySelector("#initialCash"),
    scoreMeta: document.querySelector("#scoreMeta"),
    scoreTableBody: document.querySelector("#scoreTableBody"),
    backtestMeta: document.querySelector("#backtestMeta"),
    metricsList: document.querySelector("#metricsList"),
    biasList: document.querySelector("#biasList"),
    summaryMeta: document.querySelector("#summaryMeta"),
    summaryContent: document.querySelector("#summaryContent"),
};

document.addEventListener("DOMContentLoaded", () => {
    bindActions();
    loadStatus();
});

function bindActions() {
    els.syncButton.addEventListener("click", () => runAction("sync"));
    els.scoreButton.addEventListener("click", () => runAction("score"));
    els.backtestButton.addEventListener("click", () => runAction("backtest"));
}

async function loadStatus() {
    try {
        const payload = await requestJson("/api/status");
        const data = payload.data || {};
        els.serviceStatus.textContent = `${data.service || "quant-a"} 正常`;
        els.providerStatus.textContent = data.provider || "-";
        els.modelStatus.textContent = data.model_version || "-";
    } catch (error) {
        els.serviceStatus.textContent = "不可用";
        els.providerStatus.textContent = "-";
        els.modelStatus.textContent = "-";
        showNotice(`状态加载失败：${error.message}`, "error");
    }
}

async function runAction(type) {
    if (state.busy) {
        return;
    }

    const params = readParams();
    if (!params) {
        return;
    }

    setBusy(true);
    try {
        if (type === "sync") {
            showNotice("正在同步研究数据...", "loading");
            const payload = await requestJson("/api/data/sync", {
                method: "POST",
                body: JSON.stringify({
                    start_date: params.startDate,
                    end_date: params.endDate,
                    index_codes: params.indexCodes,
                }),
            });
            renderSyncResult(payload.data || {});
            showNotice("数据同步完成，可以继续运行评分或回测。", "success");
        }

        if (type === "score") {
            showNotice("正在计算多因子评分...", "loading");
            const payload = await requestJson("/api/scores/run", {
                method: "POST",
                body: JSON.stringify({
                    trade_date: params.scoreDate,
                    index_codes: params.indexCodes,
                }),
            });
            renderScores(payload.data || {});
            showNotice("评分运行完成。结果仅表示模型排序信号，不代表交易指令。", "success");
        }

        if (type === "backtest") {
            showNotice("正在运行回测，请稍候...", "loading");
            const payload = await requestJson("/api/backtests/run", {
                method: "POST",
                body: JSON.stringify({
                    start_date: params.startDate,
                    end_date: params.endDate,
                    index_codes: params.indexCodes,
                    initial_cash: params.initialCash,
                }),
            });
            renderBacktest(payload.data || {});
            showNotice("回测运行完成。请结合披露区检查数据和执行假设。", "success");
        }
    } catch (error) {
        showNotice(`操作失败：${error.message}`, "error");
    } finally {
        setBusy(false);
    }
}

function readParams() {
    const indexCodes = els.indexCodes.value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    const initialCash = Number(els.initialCash.value);

    if (!els.startDate.value || !els.endDate.value || !els.scoreDate.value) {
        showNotice("请完整填写开始日期、结束日期和评分日期。", "error");
        return null;
    }
    if (els.startDate.value > els.endDate.value) {
        showNotice("开始日期不能晚于结束日期。", "error");
        return null;
    }
    if (indexCodes.length === 0) {
        showNotice("请至少填写一个指数池代码。", "error");
        return null;
    }
    if (!Number.isFinite(initialCash) || initialCash <= 0) {
        showNotice("初始资金必须大于 0。", "error");
        return null;
    }

    return {
        startDate: els.startDate.value,
        endDate: els.endDate.value,
        scoreDate: els.scoreDate.value,
        indexCodes,
        initialCash,
    };
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });
    let payload;
    try {
        payload = await response.json();
    } catch (error) {
        throw new Error(`接口返回不是 JSON：${response.status}`);
    }
    if (!response.ok || payload.success === false) {
        throw new Error(payload.message || `HTTP ${response.status}`);
    }
    return payload;
}

function renderSyncResult(data) {
    const parts = [
        ["数据版本", data.data_version],
        ["交易日", data.calendar_count],
        ["股票", data.stock_count],
        ["行情", data.daily_bar_count],
        ["指数成分", data.index_member_count],
    ].map(([label, value]) => `${label}: ${value ?? "-"}`);
    els.summaryMeta.textContent = "数据同步";
    els.summaryContent.innerHTML = `<p>${parts.join(" / ")}</p>`;
}

function renderScores(data) {
    const scores = Array.isArray(data.scores) ? data.scores : [];
    els.scoreMeta.textContent = data.trade_date ? `评分日期 ${data.trade_date}` : "评分完成";

    if (scores.length === 0) {
        els.scoreTableBody.innerHTML = '<tr><td colspan="5" class="empty">没有可展示的评分结果。</td></tr>';
        return;
    }

    els.scoreTableBody.innerHTML = scores.map((score) => `
        <tr>
            <td>${escapeHtml(score.rank)}</td>
            <td>${escapeHtml(score.code)}</td>
            <td>${escapeHtml(score.name)}</td>
            <td>${escapeHtml(score.industry)}</td>
            <td>${formatNumber(score.total_score, 4)}</td>
        </tr>
    `).join("");
}

function renderBacktest(data) {
    const report = data.report || {};
    const backtest = data.backtest || {};
    const metrics = report.metrics || {};
    const nav = Array.isArray(report.nav) ? report.nav : [];
    const orders = Array.isArray(report.orders) ? report.orders : [];
    const biases = Array.isArray(report.known_biases) ? report.known_biases : [];
    const skipped = Array.isArray(data.skipped_score_dates) ? data.skipped_score_dates : [];

    els.backtestMeta.textContent = report.experiment_id || backtest.experiment_id || "回测完成";
    els.metricsList.innerHTML = metricHtml("起始净值", metrics.start_nav)
        + metricHtml("结束净值", metrics.end_nav)
        + metricHtml("区间收益", formatPercent(metrics.total_return))
        + metricHtml("最大回撤", formatPercent(metrics.max_drawdown))
        + metricHtml("订单数", metrics.order_count);

    renderBiases(biases, skipped);
    renderSummary(nav, orders);
}

function renderBiases(biases, skipped) {
    const items = biases.map((bias) => `
        <li>
            <strong>${escapeHtml(bias.bias_type)} · ${escapeHtml(bias.severity)}</strong>
            <span>${escapeHtml(bias.impact_description)}</span>
            <small>${escapeHtml(bias.mitigation)}</small>
        </li>
    `);

    if (skipped.length > 0) {
        items.push(`<li><strong>评分日期跳过</strong><span>${skipped.length} 个评分日期未纳入回测。</span></li>`);
    }

    items.push("<li>本页面展示的是历史数据研究输出，不构成确定性收益判断或投资建议。</li>");
    els.biasList.innerHTML = items.join("");
}

function renderSummary(nav, orders) {
    const latestNav = nav[nav.length - 1];
    const filledOrders = orders.filter((order) => order.order_status === "filled").length;
    const rejectedOrders = orders.filter((order) => order.order_status === "rejected").length;

    els.summaryMeta.textContent = "回测摘要";
    els.summaryContent.innerHTML = `
        <p>最近 NAV：${latestNav ? `${escapeHtml(latestNav.trade_date)} / ${formatNumber(latestNav.nav, 4)}` : "-"}</p>
        <p>订单：${orders.length} 条，成交 ${filledOrders} 条，未成交 ${rejectedOrders} 条。</p>
        <p>最近持仓市值：${latestNav ? formatCurrency(latestNav.market_value) : "-"}</p>
    `;
}

function metricHtml(label, value) {
    return `<div><dt>${label}</dt><dd>${value ?? "-"}</dd></div>`;
}

function setBusy(isBusy) {
    state.busy = isBusy;
    [els.syncButton, els.scoreButton, els.backtestButton].forEach((button) => {
        button.disabled = isBusy;
    });
}

function showNotice(message, type) {
    els.notice.textContent = message;
    els.notice.dataset.type = type || "info";
}

function formatNumber(value, digits = 2) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "-";
    }
    return number.toLocaleString("zh-CN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

function formatPercent(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "-";
    }
    return `${(number * 100).toFixed(2)}%`;
}

function formatCurrency(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "-";
    }
    return number.toLocaleString("zh-CN", {
        style: "currency",
        currency: "CNY",
        maximumFractionDigits: 0,
    });
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;",
    }[char]));
}
