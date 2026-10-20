(function () {
    "use strict";
    var cards = Array.prototype.slice.call(document.querySelectorAll("[data-service]"));

    function url(card, path) {
        return "/api/services/local/" + card.getAttribute("data-service") + "/" + path;
    }

    function request(card, path, mutation) {
        return fetch(url(card, path), { method: mutation ? "POST" : "GET", cache: "no-store",
            headers: mutation ? { "X-Love530-Local": "1" } : {} })
            .then(function (response) {
                return response.json().then(function (body) {
                    if (!response.ok || !body.success) throw new Error(body.message || "服务暂不可用");
                    return body;
                });
            });
    }

    function render(card, state) {
        card.classList.toggle("is-online", state.running);
        card.classList.toggle("is-offline", !state.running);
        card.querySelector("[data-status]").textContent = state.running ? "服务在线" : "服务已关闭";
        var model = card.querySelector("[data-model-state]");
        if (model) model.textContent = state.service === "strata" ? (state.loaded ? "模型已加载，可开始对话。" : "模型未加载；点击加载模型，或发送第一条消息。")
            : (state.installed ? "H3 权重已安装，提交生成任务后加载。引擎在线不代表模型常驻内存。" : "H3 权重不完整，请检查 AIMedia 模型目录。");
        var link = card.querySelector("[data-open-app]");
        link.href = state.url;
        link.setAttribute("aria-disabled", String(!state.running));
        Array.prototype.forEach.call(card.querySelectorAll("[data-action]"), function (button) {
            var action = button.getAttribute("data-action");
            button.disabled = !!card._busy || (action === "start" && state.running)
                || ((action === "stop" || action === "unload") && !state.running)
                || (action === "load" && state.loaded);
        });
    }

    function refresh(card) {
        return request(card, "status", false).then(function (state) {
            card._state = state;
            render(card, state);
        }).catch(function (error) {
            card.querySelector("[data-status]").textContent = "状态读取失败";
            var feedback = card.querySelector("[data-feedback]");
            feedback.textContent = error.message;
            feedback.classList.add("is-error");
        });
    }

    cards.forEach(function (card) {
        card.querySelector("[data-open-app]").addEventListener("click", function (event) {
            if (this.getAttribute("aria-disabled") === "true") event.preventDefault();
        });
        card.addEventListener("click", function (event) {
            var button = event.target.closest("[data-action]");
            if (!button || button.disabled || card._busy) return;
            card._busy = true;
            var feedback = card.querySelector("[data-feedback]");
            feedback.classList.remove("is-error");
            feedback.textContent = button.getAttribute("data-action") === "load" ? "正在加载模型，请稍候…" : "正在操作，请稍候…";
            Array.prototype.forEach.call(card.querySelectorAll("button"), function (item) { item.disabled = true; });
            request(card, button.getAttribute("data-action"), true).then(function (state) {
                feedback.textContent = state.message || "操作完成";
            }).catch(function (error) {
                feedback.textContent = error.message;
                feedback.classList.add("is-error");
            }).then(function () {
                card._busy = false;
                return refresh(card);
            });
        });
        refresh(card);
    });
    window.setInterval(function () { cards.forEach(function (card) { if (!card._busy) refresh(card); }); }, 30 * 60 * 1000);
}());
