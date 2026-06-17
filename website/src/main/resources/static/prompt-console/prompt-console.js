(function () {
    var PAGE_SIZE = 120;
    var state = {
        sources: [],
        entries: [],
        categories: [],
        categoryGroups: [],
        visibleEntries: [],
        activeEntry: null,
        activeGroup: "all",
        activeCategory: "all",
        renderLimit: PAGE_SIZE
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
    }

    function fetchJson(url) {
        return fetch(url, { cache: "no-store" }).then(function (response) {
            if (!response.ok) {
                throw new Error("Request failed");
            }
            return response.json();
        });
    }

    function loadLibrary() {
        return fetchJson("data/prompt-library.json")
            .then(function (payload) {
                state.sources = payload.sources || [];
                state.entries = payload.entries || [];
                buildFilters();
                renderSources();
                renderCategories();
                applyFilters();
            })
            .catch(function () {
                elements.entryList.innerHTML = '<div class="empty-state">合集数据加载失败，请检查 data/prompt-library.json。</div>';
            });
    }

    function buildFilters() {
        state.categories = buildCategoryStats();
        state.categoryGroups = PromptCategoryGroups.buildGroupStats(state.entries, state.categories);

        elements.sourceFilter.innerHTML = '<option value="all">全部来源</option>' + state.sources.map(function (source) {
            return '<option value="' + escapeAttribute(source.id) + '">' + escapeHtml(source.name) + '</option>';
        }).join("");

        elements.groupFilter.innerHTML = '<option value="all">全部大分类</option>' + state.categoryGroups.map(function (group) {
            return '<option value="' + escapeAttribute(group.slug) + '">' + escapeHtml(group.name) + ' (' + group.count + ')</option>';
        }).join("");

        renderCategoryFilterOptions();
    }

    function buildCategoryStats() {
        var stats = {};
        state.entries.forEach(function (entry) {
            var category = entry.category || "未分类";
            stats[category] = (stats[category] || 0) + 1;
        });
        state.sources.forEach(function (source) {
            (source.categories || []).forEach(function (category) {
                if (!stats[category]) {
                    stats[category] = 0;
                }
            });
        });
        return Object.keys(stats).map(function (name) {
            return {
                name: name,
                count: stats[name]
            };
        }).sort(function (a, b) {
            return b.count - a.count || a.name.localeCompare(b.name, "zh-Hans-CN");
        });
    }

    function applyFilters() {
        var query = elements.searchInput.value.trim().toLowerCase();
        var sourceId = elements.sourceFilter.value;
        var group = elements.groupFilter.value;
        var category = elements.categoryFilter.value;
        var status = elements.statusFilter.value;
        state.activeGroup = group;
        state.activeCategory = category;
        state.renderLimit = PAGE_SIZE;

        state.visibleEntries = state.entries.filter(function (entry) {
            if (sourceId !== "all" && entry.sourceId !== sourceId) {
                return false;
            }
            if (group !== "all" && PromptCategoryGroups.getGroupForCategory(entry.category || "未分类").slug !== group) {
                return false;
            }
            if (category !== "all" && entry.category !== category) {
                return false;
            }
            if (status !== "all" && (entry.status || "imported") !== status) {
                return false;
            }
            if (!query) {
                return true;
            }
            return searchableText(entry).indexOf(query) !== -1;
        });

        renderCategories();
        renderEntries();
        updateCounts();
    }

    function searchableText(entry) {
        return [
            entry.title,
            entry.category,
            PromptCategoryGroups.getGroupForCategory(entry.category || "未分类").name,
            entry.prompt,
            entry.sourceName,
            (entry.tags || []).join(" ")
        ].join(" ").toLowerCase();
    }

    function getVisibleCategoriesForActiveGroup() {
        if (state.activeGroup === "all") {
            return state.categories;
        }
        var group = PromptCategoryGroups.findGroup(state.categoryGroups, state.activeGroup);
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

    function renderCategories() {
        elements.categoryCount.textContent = String(state.categoryGroups.length);
        var total = state.entries.length;
        var html = '<button class="category-chip category-chip-all' + (state.activeGroup === "all" && state.activeCategory === "all" ? " active" : "") + '" type="button" data-group-value="all">'
            + '<span>全部分类</span><strong>' + total + '</strong></button>';
        html += state.categoryGroups.map(function (group) {
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
        elements.sourceCount.textContent = String(state.sources.length);
        elements.sourceList.innerHTML = state.sources.map(function (source) {
            var count = state.entries.filter(function (entry) {
                return entry.sourceId === source.id;
            }).length;
            var status = source.status || (count > 0 ? "imported" : "pending");
            return '<article class="source-card">'
                + '<h3>' + escapeHtml(source.name) + '</h3>'
                + '<p>' + escapeHtml(source.summary || "") + '</p>'
                + '<div class="source-meta">'
                + '<span class="pill ' + escapeAttribute(status) + '">' + escapeHtml(status === "imported" ? "已导入" : "待导入") + '</span>'
                + '<span class="pill">' + escapeHtml(source.license || "授权") + '</span>'
                + '<span class="pill">' + count + ' 条</span>'
                + '</div>'
                + '</article>';
        }).join("");
    }

    function renderEntries() {
        if (!state.visibleEntries.length) {
            elements.entryList.innerHTML = '<div class="empty-state">当前没有可显示的提示词。可以换一个关键词、来源或分类。</div>';
            return;
        }

        var items = state.visibleEntries.slice(0, state.renderLimit);
        var cards = items.map(function (entry, index) {
            var group = PromptCategoryGroups.getGroupForCategory(entry.category || "未分类");
            var tags = (entry.tags || []).slice(0, 5).map(function (tag) {
                return '<span class="tag">' + escapeHtml(tag) + '</span>';
            }).join("");
            if (isMostlyEnglish(entry.prompt || "")) {
                tags += '<span class="tag language-tag">英文原文</span>';
            }
            return '<article class="entry-card">'
                + '<div>'
                + '<h3>' + escapeHtml(entry.title || "Untitled Prompt") + '</h3>'
                + '<p class="entry-meta-text">' + escapeHtml(entry.sourceName || entry.sourceId) + ' · ' + escapeHtml(group.name) + ' / ' + escapeHtml(entry.category || "未分类") + '</p>'
                + '</div>'
                + '<p class="prompt-preview">' + escapeHtml(entry.prompt || "") + '</p>'
                + '<div class="entry-meta">' + tags + '<span class="pill">' + escapeHtml(entry.license || "") + '</span></div>'
                + '<button type="button" data-entry-index="' + index + '">查看 / 复制</button>'
                + '</article>';
        });

        if (state.visibleEntries.length > items.length) {
            cards.push('<button class="load-more-button" type="button">再显示 ' + Math.min(PAGE_SIZE, state.visibleEntries.length - items.length) + ' 条</button>');
        }

        elements.entryList.innerHTML = cards.join("");
    }

    function updateCounts() {
        elements.entryCount.textContent = String(state.entries.length);
        elements.visibleCount.textContent = String(state.visibleEntries.length);
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
            var group = PromptCategoryGroups.getGroupForCategory(category);
            state.activeGroup = group.slug;
            elements.groupFilter.value = group.slug;
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
        var entry = state.visibleEntries[index];
        if (!entry) {
            return;
        }
        var group = PromptCategoryGroups.getGroupForCategory(entry.category || "未分类");
        state.activeEntry = entry;
        elements.dialogTitle.textContent = entry.title || "Untitled Prompt";
        elements.dialogSource.textContent = (entry.sourceName || entry.sourceId || "来源") + " · " + group.name + " / " + (entry.category || "未分类");
        elements.dialogTags.innerHTML = (entry.tags || []).map(function (tag) {
            return '<span class="tag">' + escapeHtml(tag) + '</span>';
        }).join("") + (isMostlyEnglish(entry.prompt || "") ? '<span class="tag language-tag">英文原文</span>' : "");
        elements.dialogPrompt.textContent = entry.prompt || "";
        elements.dialogLicense.textContent = "授权：" + (entry.license || "User-provided authorization");
        elements.dialogLink.href = entry.sourceUrl || "#";
        elements.dialog.showModal();
    }

    function copyActivePrompt() {
        if (!state.activeEntry || !navigator.clipboard) {
            return;
        }
        navigator.clipboard.writeText(state.activeEntry.prompt || "").then(function () {
            elements.copyDialogButton.textContent = "已复制";
            window.setTimeout(function () {
                elements.copyDialogButton.textContent = "复制提示词";
            }, 1400);
        });
    }

    function setupEvents() {
        elements.searchInput.addEventListener("input", applyFilters);
        elements.sourceFilter.addEventListener("change", applyFilters);
        elements.groupFilter.addEventListener("change", function () {
            setGroup(elements.groupFilter.value, false);
        });
        elements.categoryFilter.addEventListener("change", function () {
            setCategory(elements.categoryFilter.value, false);
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
                state.renderLimit += PAGE_SIZE;
                renderEntries();
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
        loadLibrary();
    });
})();
