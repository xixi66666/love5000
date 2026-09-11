(function () {
    var PAGE_SIZE = 48;
    var SEARCH_DEBOUNCE_MS = 300;
    var state = {
        meta: null,
        entries: [],
        totalVisible: 0,
        activeGroup: "all",
        activeCategory: "all",
        currentPage: 1,
        loadedAll: true,
        activePrompt: null
    };

    var elements = {};

    function $(selector) {
        return document.querySelector(selector);
    }

    function findElements() {
        elements.entryCount = $(".entry-count");
        elements.visibleCount = $(".visible-count");
        elements.sourceCount = $(".source-count");
        elements.categoryCount = $(".category-count");
        elements.sourceList = $(".source-list");
        elements.categoryList = $(".category-list");
        elements.entryList = $(".entry-list");
        elements.searchInput = $(".search-input");
        elements.sourceFilter = $(".source-filter");
        elements.groupFilter = $(".group-filter");
        elements.categoryFilter = $(".category-filter");
        elements.statusFilter = $(".status-filter");
        elements.dialog = $(".entry-dialog");
        elements.dialogTitle = $(".dialog-title");
        elements.dialogSource = $(".dialog-source");
        elements.dialogTags = $(".dialog-tags");
        elements.dialogPrompt = $(".dialog-prompt");
        elements.dialogLicense = $(".dialog-license");
        elements.dialogLink = $(".dialog-link");
        elements.dialogClose = $(".dialog-close");
        elements.copyDialogButton = $(".copy-dialog-button");
        elements.addButton = $(".add-prompt-button");
        elements.addDialog = $(".add-dialog");
        elements.addForm = $(".add-form");
        elements.addClose = $(".add-close");
        elements.addCancel = $(".add-cancel-button");
        elements.addTitleInput = $(".add-title-input");
        elements.addCategoryInput = $(".add-category-input");
        elements.addTagsInput = $(".add-tags-input");
        elements.addSourceUrlInput = $(".add-source-url-input");
        elements.addLicenseInput = $(".add-license-input");
        elements.addPromptInput = $(".add-prompt-input");
        elements.addError = $(".add-error");
        elements.addCategoryOptions = $("#addCategoryOptions");
    }

    function fetchJson(url, options) {
        return fetch(url, options || { cache: "no-store" }).then(function (response) {
            return response.json().catch(function () {
                return null;
            }).then(function (payload) {
                if (!response.ok) {
                    var message = payload && payload.message ? payload.message : "请求失败，请稍后重试";
                    throw new Error(message);
                }
                return payload;
            });
        });
    }

    function loadMeta() {
        return fetchJson("/api/prompts/meta")
            .then(function (payload) {
                var groupValue = elements.groupFilter.value || "all";
                var categoryValue = elements.categoryFilter.value || "all";
                var sourceValue = elements.sourceFilter.value || "all";
                state.meta = payload;
                buildFilters();
                elements.sourceFilter.value = sourceValue;
                elements.groupFilter.value = groupValue;
                state.activeGroup = groupValue;
                state.activeCategory = categoryValue;
                renderCategoryFilterOptions();
                renderCategoryOptions();
                renderSources();
                renderCategories();
                updateCounts();
                applyFilters();
            })
            .catch(function () {
                elements.entryList.innerHTML = '<div class="empty-state">合集数据加载失败，请检查服务与数据库连接。</div>';
            });
    }

    function renderCategoryOptions() {
        if (!elements.addCategoryOptions) {
            return;
        }
        var names = [];
        state.meta.groups.forEach(function (group) {
            group.categories.forEach(function (item) {
                if (names.indexOf(item.name) === -1) {
                    names.push(item.name);
                }
            });
        });
        elements.addCategoryOptions.innerHTML = names.map(function (name) {
            return '<option value="' + escapeAttribute(name) + '"></option>';
        }).join("");
    }

    function buildFilters() {
        elements.sourceFilter.innerHTML = '<option value="all">全部来源</option>' + state.meta.sources.map(function (source) {
            return '<option value="' + escapeAttribute(source.id) + '">' + escapeHtml(source.name) + '</option>';
        }).join("");
        elements.groupFilter.innerHTML = '<option value="all">全部大分类</option>' + state.meta.groups.map(function (group) {
            return '<option value="' + escapeAttribute(group.slug) + '">' + escapeHtml(group.name) + ' (' + group.count + ')</option>';
        }).join("");
        renderCategoryFilterOptions();
    }

    function getVisibleCategoriesForActiveGroup() {
        if (state.activeGroup === "all") {
            var all = [];
            state.meta.groups.forEach(function (group) {
                group.categories.forEach(function (item) {
                    all.push({ name: item.name, count: item.count });
                });
            });
            return all;
        }
        var group = null;
        state.meta.groups.forEach(function (item) {
            if (item.slug === state.activeGroup) {
                group = item;
            }
        });
        return group ? group.categories : [];
    }

    function renderCategoryFilterOptions() {
        var categories = getVisibleCategoriesForActiveGroup();
        if (state.activeCategory !== "all" && !categories.some(function (item) { return item.name === state.activeCategory; })) {
            state.activeCategory = "all";
        }
        elements.categoryFilter.innerHTML = '<option value="all">全部小分类</option>' + categories.map(function (item) {
            return '<option value="' + escapeAttribute(item.name) + '">' + escapeHtml(item.name) + ' (' + item.count + ')</option>';
        }).join("");
        elements.categoryFilter.value = state.activeCategory;
    }

    function currentParams() {
        var query = elements.searchInput.value.trim();
        var sourceId = elements.sourceFilter.value;
        var group = elements.groupFilter.value;
        var category = elements.categoryFilter.value;
        var status = elements.statusFilter.value;
        state.activeGroup = group;
        state.activeCategory = category;
        return { keyword: query, source: sourceId, group: group, category: category, status: status };
    }

    function buildQuery(params, page, size) {
        var parts = ["page=" + page, "size=" + size];
        if (params.keyword) {
            parts.push("keyword=" + encodeURIComponent(params.keyword));
        }
        if (params.source && params.source !== "all") {
            parts.push("source=" + encodeURIComponent(params.source));
        }
        if (params.group && params.group !== "all") {
            parts.push("group=" + encodeURIComponent(params.group));
        }
        if (params.category && params.category !== "all") {
            parts.push("category=" + encodeURIComponent(params.category));
        }
        if (params.status && params.status !== "all") {
            parts.push("status=" + encodeURIComponent(params.status));
        }
        return "/api/prompts?" + parts.join("&");
    }

    function applyFilters() {
        var params = currentParams();
        state.entries = [];
        state.currentPage = 1;
        state.loadedAll = false;
        renderCategories();
        fetchPage(params, true);
    }

    function fetchPage(params, reset) {
        elements.entryList.innerHTML = reset ? '<div class="empty-state">加载中…</div>' : elements.entryList.innerHTML;
        return fetchJson(buildQuery(params, state.currentPage, PAGE_SIZE))
            .then(function (payload) {
                if (reset) {
                    state.entries = payload.entries || [];
                } else {
                    state.entries = state.entries.concat(payload.entries || []);
                }
                state.totalVisible = payload.total || 0;
                state.loadedAll = state.entries.length >= state.totalVisible;
                renderEntries();
                updateCounts();
            })
            .catch(function () {
                elements.entryList.innerHTML = '<div class="empty-state">提示词加载失败，请稍后重试。</div>';
            });
    }

    function renderCategories() {
        elements.categoryCount.textContent = String(state.meta.groups.length);
        var html = '<button class="category-chip category-chip-all' + (state.activeGroup === "all" && state.activeCategory === "all" ? " active" : "") + '" type="button" data-group-value="all">'
            + '<span>全部分类</span><strong>' + state.meta.total + '</strong></button>';
        html += state.meta.groups.map(function (group) {
            var childHtml = group.categories.map(function (item) {
                return '<button class="subcategory-chip' + (state.activeCategory === item.name ? " active" : "") + '" type="button" data-category-value="' + escapeAttribute(item.name) + '">'
                    + '<span>' + escapeHtml(item.name) + '</span><strong>' + item.count + '</strong></button>';
            }).join("");
            return '<article class="category-group">'
                + '<button class="category-chip' + (state.activeGroup === group.slug && state.activeCategory === "all" ? " active" : "") + '" type="button" data-group-value="' + escapeAttribute(group.slug) + '">'
                + '<span>' + escapeHtml(group.name) + '</span><strong>' + group.count + '</strong></button>'
                + '<div class="subcategory-list">' + childHtml + '</div>'
                + '</article>';
        }).join("");
        elements.categoryList.innerHTML = html;
    }

    function renderSources() {
        elements.sourceCount.textContent = String(state.meta.sources.length);
        elements.sourceList.innerHTML = state.meta.sources.map(function (source) {
            var status = source.status || "imported";
            return '<article class="source-card">'
                + '<h3>' + escapeHtml(source.name) + '</h3>'
                + '<p>' + escapeHtml(source.summary || "") + '</p>'
                + '<div class="source-meta">'
                + '<span class="pill ' + escapeAttribute(status) + '">' + escapeHtml(status === "imported" ? "已导入" : "待导入") + '</span>'
                + '<span class="pill">' + escapeHtml(source.license || "授权") + '</span>'
                + '<span class="pill">' + source.count + ' 条</span>'
                + '</div>'
                + '</article>';
        }).join("");
    }

    function renderEntries() {
        if (!state.entries.length) {
            elements.entryList.innerHTML = '<div class="empty-state">当前没有可显示的提示词。可以换一个关键词、来源或分类。</div>';
            return;
        }
        var cards = state.entries.map(function (entry, index) {
            var tags = (entry.tags || []).slice(0, 5).map(function (tag) {
                return '<span class="tag">' + escapeHtml(tag) + '</span>';
            }).join("");
            if (isMostlyEnglish(entry.preview || "")) {
                tags += '<span class="tag language-tag">英文原文</span>';
            }
            return '<article class="entry-card">'
                + '<div>'
                + '<h3>' + escapeHtml(entry.title || "Untitled Prompt") + '</h3>'
                + '<p class="entry-meta-text">' + escapeHtml(entry.sourceName || "") + ' · ' + escapeHtml(entry.groupName || entry.category || "") + ' / ' + escapeHtml(entry.category || "") + '</p>'
                + '</div>'
                + '<p class="prompt-preview">' + escapeHtml(entry.preview || "") + '</p>'
                + '<div class="entry-meta">' + tags + '<span class="pill">' + escapeHtml(entry.license || "") + '</span></div>'
                + '<button type="button" data-entry-index="' + index + '">查看 / 复制</button>'
                + '</article>';
        });
        if (!state.loadedAll) {
            cards.push('<button class="load-more-button" type="button">加载更多</button>');
        }
        elements.entryList.innerHTML = cards.join("");

        if (!elements.entryList.dataset.entered) {
            window.requestAnimationFrame(function () {
                if (elements.entryList) {
                    elements.entryList.dataset.entered = "true";
                }
            });
        }
    }

    function updateCounts() {
        elements.entryCount.textContent = String(state.meta ? state.meta.total : 0);
        elements.visibleCount.textContent = String(state.totalVisible);
    }

    function findGroupForCategory(categoryName) {
        var found = null;
        state.meta.groups.forEach(function (group) {
            group.categories.forEach(function (item) {
                if (item.name === categoryName) {
                    found = group;
                }
            });
        });
        return found;
    }

    function setGroup(group, shouldScroll) {
        state.activeGroup = group;
        state.activeCategory = "all";
        elements.groupFilter.value = group;
        renderCategoryFilterOptions();
        applyFilters();
        if (shouldScroll) {
            $(".entry-panel").scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    function setCategory(category, shouldScroll) {
        if (category !== "all") {
            var group = findGroupForCategory(category);
            if (group) {
                state.activeGroup = group.slug;
                elements.groupFilter.value = group.slug;
            }
        }
        state.activeCategory = category;
        renderCategoryFilterOptions();
        elements.categoryFilter.value = category;
        applyFilters();
        if (shouldScroll) {
            $(".entry-panel").scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    function openEntry(index) {
        var entry = state.entries[index];
        if (!entry) {
            return;
        }
        fetchJson("/api/prompts/" + entry.id)
            .then(function (payload) {
                if (!payload || !payload.entry) {
                    return;
                }
                showEntryDialog(payload.entry);
            })
            .catch(function () {
                elements.dialogTitle.textContent = "加载失败";
            });
    }

    function showEntryDialog(detail) {
        state.activePrompt = detail.prompt || "";
        elements.dialogTitle.textContent = detail.title || "Untitled Prompt";
        elements.dialogSource.textContent = (detail.sourceName || "") + " · " + (detail.groupName || detail.category || "") + " / " + (detail.category || "");
        elements.dialogTags.innerHTML = (detail.tags || []).map(function (tag) {
            return '<span class="tag">' + escapeHtml(tag) + '</span>';
        }).join("") + (isMostlyEnglish(detail.prompt || "") ? '<span class="tag language-tag">英文原文</span>' : "");
        elements.dialogPrompt.textContent = detail.prompt || "";
        elements.dialogLicense.textContent = "授权：" + (detail.license || "User-provided authorization");
        elements.dialogLink.href = detail.sourceUrl || "#";
        elements.dialog.showModal();
    }

    function openAddDialog() {
        elements.addForm.reset();
        elements.addError.hidden = true;
        elements.addError.textContent = "";
        elements.addDialog.showModal();
        elements.addTitleInput.focus();
    }

    function closeAddDialog() {
        elements.addDialog.close();
    }

    function showAddError(message) {
        elements.addError.textContent = message;
        elements.addError.hidden = false;
    }

    function submitAdd(event) {
        event.preventDefault();
        var title = elements.addTitleInput.value.trim();
        var category = elements.addCategoryInput.value.trim();
        var prompt = elements.addPromptInput.value.trim();
        if (!title) {
            showAddError("请填写标题");
            return;
        }
        if (!category) {
            showAddError("请填写小分类");
            return;
        }
        if (!prompt) {
            showAddError("请填写提示词正文");
            return;
        }

        var payload = {
            title: title,
            category: category,
            prompt: prompt,
            tags: elements.addTagsInput.value.trim(),
            sourceUrl: elements.addSourceUrlInput.value.trim(),
            license: elements.addLicenseInput.value.trim()
        };

        elements.addForm.querySelector(".add-submit-button").disabled = true;
        fetchJson("/api/prompts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            cache: "no-store",
            body: JSON.stringify(payload)
        })
            .then(function (response) {
                closeAddDialog();
                if (response && response.entry) {
                    showEntryDialog(response.entry);
                }
                return loadMeta();
            })
            .catch(function (error) {
                showAddError(error.message || "保存失败，请稍后重试");
            })
            .then(function () {
                elements.addForm.querySelector(".add-submit-button").disabled = false;
            });
    }

    function copyActivePrompt() {
        if (!state.activePrompt || !navigator.clipboard) {
            return;
        }
        navigator.clipboard.writeText(state.activePrompt).then(function () {
            elements.copyDialogButton.textContent = "已复制";
            window.setTimeout(function () {
                elements.copyDialogButton.textContent = "复制提示词";
            }, 1400);
        });
    }

    function debounce(fn, wait) {
        var timer = null;
        return function () {
            var context = this;
            var args = arguments;
            window.clearTimeout(timer);
            timer = window.setTimeout(function () {
                fn.apply(context, args);
            }, wait);
        };
    }

    function setupEvents() {
        elements.searchInput.addEventListener("input", debounce(applyFilters, SEARCH_DEBOUNCE_MS));
        elements.sourceFilter.addEventListener("change", applyFilters);
        elements.groupFilter.addEventListener("change", function () {
            setGroup(elements.groupFilter.value, true);
        });
        elements.categoryFilter.addEventListener("change", function () {
            setCategory(elements.categoryFilter.value, true);
        });
        elements.statusFilter.addEventListener("change", applyFilters);
        elements.categoryList.addEventListener("click", function (event) {
            var categoryButton = event.target.closest("[data-category-value]");
            if (categoryButton) {
                setCategory(categoryButton.getAttribute("data-category-value"), true);
                return;
            }
            var groupButton = event.target.closest("[data-group-value]");
            if (groupButton) {
                setGroup(groupButton.getAttribute("data-group-value"), true);
            }
        });
        elements.entryList.addEventListener("click", function (event) {
            var loadMore = event.target.closest(".load-more-button");
            if (loadMore) {
                state.currentPage += 1;
                fetchPage(currentParams(), false);
                return;
            }
            var button = event.target.closest("[data-entry-index]");
            if (button) {
                openEntry(Number(button.getAttribute("data-entry-index")));
            }
        });
        elements.dialogClose.addEventListener("click", function () {
            elements.dialog.close();
        });
        elements.copyDialogButton.addEventListener("click", copyActivePrompt);
        elements.addButton.addEventListener("click", openAddDialog);
        elements.addClose.addEventListener("click", closeAddDialog);
        elements.addCancel.addEventListener("click", closeAddDialog);
        elements.addForm.addEventListener("submit", submitAdd);
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replace(/`/g, "&#96;");
    }

    function isMostlyEnglish(value) {
        var text = String(value || "").replace(/\s+/g, "");
        if (text.length < 80) {
            return false;
        }
        var latin = (text.match(/[A-Za-z]/g) || []).length;
        var cjk = (text.match(/[\u3400-\u9fff]/g) || []).length;
        return latin > 120 && latin > cjk * 2;
    }

    document.addEventListener("DOMContentLoaded", function () {
        findElements();
        setupEvents();
        loadMeta();
    });
})();