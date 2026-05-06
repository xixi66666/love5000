const AUTH_RULES = [
    "用户名长度必须为 3-32 个字符。",
    "用户名只能包含英文字母、数字或下划线。",
    "用户名会自动去除首尾空格并转换为小写。",
    "密码长度必须为 8-72 个字符。",
    "密码至少包含 1 个英文字母和 1 个数字。",
    "密码不能包含空格、换行或制表符。"
];

const state = {
    category: "",
    tag: "",
    keyword: "",
    articles: [],
    categories: [],
    tags: [],
    currentUser: null,
    authMode: "login"
};

const elements = {
    postList: document.getElementById("postList"),
    postDetail: document.getElementById("postDetail"),
    archivePanel: document.getElementById("archivePanel"),
    categoryList: document.getElementById("categoryList"),
    tagList: document.getElementById("tagList"),
    searchInput: document.getElementById("searchInput"),
    listTitle: document.getElementById("listTitle"),
    postCount: document.getElementById("postCount"),
    categoryCount: document.getElementById("categoryCount"),
    resetFilters: document.getElementById("resetFilters"),
    themeToggle: document.getElementById("themeToggle"),
    loginButton: document.getElementById("loginButton"),
    registerButton: document.getElementById("registerButton"),
    logoutButton: document.getElementById("logoutButton"),
    writeButton: document.getElementById("writeButton"),
    userPanel: document.getElementById("userPanel"),
    authModal: document.getElementById("authModal"),
    authForm: document.getElementById("authForm"),
    authTitle: document.getElementById("authTitle"),
    authModeLabel: document.getElementById("authModeLabel"),
    authRules: document.getElementById("authRules"),
    displayNameRow: document.getElementById("displayNameRow"),
    authUsername: document.getElementById("authUsername"),
    authDisplayName: document.getElementById("authDisplayName"),
    authPassword: document.getElementById("authPassword"),
    authMessage: document.getElementById("authMessage"),
    editorModal: document.getElementById("editorModal"),
    articleForm: document.getElementById("articleForm"),
    articleMessage: document.getElementById("articleMessage"),
    editorTitle: document.getElementById("editorTitle"),
    articleId: document.getElementById("articleId"),
    articleTitle: document.getElementById("articleTitle"),
    articleSlug: document.getElementById("articleSlug"),
    articleSummary: document.getElementById("articleSummary"),
    articleCategory: document.getElementById("articleCategory"),
    articleTags: document.getElementById("articleTags"),
    articleContent: document.getElementById("articleContent"),
    articleSubmitButton: document.getElementById("articleSubmitButton"),
    deleteArticleButton: document.getElementById("deleteArticleButton"),
    navLinks: document.querySelectorAll('.top-nav a, .sub-title')
};

function apiUrl(path, params) {
    const url = new URL(path, window.location.origin);
    Object.keys(params || {}).forEach(function(key) {
        if (params[key]) {
            url.searchParams.set(key, params[key]);
        }
    });
    return url.toString();
}

function escapeHtml(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function formatDate(value) {
    return value ? value.slice(0, 10) : "";
}

function isAdmin() {
    return !!state.currentUser && String(state.currentUser.role || "").toUpperCase() === "ADMIN";
}

function canManage(post) {
    if (!state.currentUser || !post) {
        return false;
    }
    return isAdmin() || (post.authorId && post.authorId === state.currentUser.id);
}

function setActiveNav(hash) {
    elements.navLinks.forEach(function(link) {
        link.classList.toggle("active", link.getAttribute("href") === hash);
    });
}

function scrollToHash(hash) {
    const target = document.querySelector(hash);
    if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function renderFilters() {
    const categoryButtons = ["全部"].concat(state.categories).map(function(category) {
        const value = category === "全部" ? "" : category;
        const active = value === state.category ? " active" : "";
        return '<button class="chip' + active + '" type="button" data-category="' + escapeHtml(value) + '">' + escapeHtml(category) + '</button>';
    });

    elements.categoryList.innerHTML = categoryButtons.join("");
    elements.tagList.innerHTML = state.tags.map(function(tag) {
        const active = tag === state.tag ? " active" : "";
        return '<button class="chip' + active + '" type="button" data-tag="' + escapeHtml(tag) + '">' + escapeHtml(tag) + '</button>';
    }).join("");
}

function renderUserPanel() {
    if (!state.currentUser) {
        elements.userPanel.innerHTML = '<h2>访客</h2><p>登录后可以发布文章；管理员可以编辑和删除所有文章。</p>';
        return;
    }
    const role = isAdmin() ? "管理员" : "作者";
    elements.userPanel.innerHTML = [
        '<h2>' + escapeHtml(state.currentUser.displayName || state.currentUser.username) + '</h2>',
        '<p><span class="role-badge">' + role + '</span> ' + escapeHtml(state.currentUser.username) + '</p>',
        isAdmin() ? '<p>管理模式已开启，可操作所有文章。</p>' : '<p>可以管理自己创建的文章。</p>'
    ].join("");
}

function renderPostList(activeHash) {
    elements.postDetail.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postList.hidden = false;
    setActiveNav(activeHash || "#posts");
    elements.listTitle.textContent = state.articles.length ? "最新文章" : "没有匹配的文章";

    elements.postList.innerHTML = state.articles.map(function(post) {
        const author = post.authorDisplayName || post.authorUsername || "未归属";
        const management = canManage(post) ? [
            '<div class="post-actions">',
            '<button type="button" data-edit-article="' + post.id + '" data-edit-slug="' + escapeHtml(post.slug) + '">编辑</button>',
            '<button type="button" class="danger-text-button" data-delete-article="' + post.id + '">删除</button>',
            '</div>'
        ].join("") : "";
        return [
            '<article class="post-card" data-post-slug="' + escapeHtml(post.slug) + '">',
            '<div class="post-meta">',
            '<span class="category-badge">' + escapeHtml(post.category) + '</span>',
            '<time>' + formatDate(post.publishedAt) + '</time>',
            '<span>' + escapeHtml(post.wordCount) + ' 字</span>',
            '<span>' + escapeHtml(post.readMinutes) + ' 分钟</span>',
            '<span>作者：' + escapeHtml(author) + '</span>',
            '</div>',
            '<h3>' + escapeHtml(post.title) + '</h3>',
            '<p>' + escapeHtml(post.summary) + '</p>',
            '<div class="post-tags">' + (post.tags || []).map(function(tag) { return '<span class="post-tag">' + escapeHtml(tag) + '</span>'; }).join("") + '</div>',
            management,
            '</article>'
        ].join("");
    }).join("");
}

function renderError(message) {
    elements.postDetail.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postList.hidden = false;
    setActiveNav("#posts");
    elements.listTitle.textContent = "加载失败";
    elements.postList.innerHTML = '<article class="post-card"><h3>' + escapeHtml(message) + '</h3><p>请确认 website 应用已启动，并且数据库可用。</p></article>';
}

async function loadArticles() {
    const response = await fetch(apiUrl("/api/blog/articles", {
        keyword: state.keyword,
        category: state.category,
        tag: state.tag
    }));
    if (!response.ok) {
        throw new Error("Article API failed");
    }
    const payload = await response.json();
    state.articles = payload.articles || [];
    elements.postCount.textContent = String(state.articles.length);
    renderPostList();
}

async function loadFilters() {
    const categoryResponse = await fetch("/api/blog/categories");
    const tagResponse = await fetch("/api/blog/tags");
    if (!categoryResponse.ok || !tagResponse.ok) {
        throw new Error("Filter API failed");
    }
    const categoryPayload = await categoryResponse.json();
    const tagPayload = await tagResponse.json();
    state.categories = categoryPayload.categories || [];
    state.tags = tagPayload.tags || [];
    elements.categoryCount.textContent = String(state.categories.length);
    renderFilters();
}

async function loadCurrentUser() {
    const response = await fetch("/api/auth/me");
    if (!response.ok) {
        state.currentUser = null;
        renderAuthState();
        return;
    }
    const payload = await response.json();
    state.currentUser = payload.user || null;
    renderAuthState();
}

function renderAuthState() {
    const loggedIn = !!state.currentUser;
    elements.loginButton.hidden = loggedIn;
    elements.registerButton.hidden = loggedIn;
    elements.logoutButton.hidden = !loggedIn;
    elements.writeButton.textContent = loggedIn ? "写文章" : "登录后写文章";
    renderUserPanel();
    renderPostList();
}

function openAuthModal(mode) {
    state.authMode = mode;
    elements.authTitle.textContent = mode === "register" ? "注册" : "登录";
    elements.authModeLabel.textContent = mode === "register" ? "Register" : "Login";
    elements.authRules.hidden = mode !== "register";
    elements.displayNameRow.hidden = mode !== "register";
    elements.authPassword.setAttribute("autocomplete", mode === "register" ? "new-password" : "current-password");
    setFormMessage(elements.authMessage, "", "");
    elements.authForm.reset();
    elements.authModal.hidden = false;
}

function closeModals() {
    elements.authModal.hidden = true;
    elements.editorModal.hidden = true;
}

function validateRegistration(username, password) {
    const issues = [];
    const normalizedUsername = (username || "").trim();
    if (!/^[a-zA-Z0-9_]{3,32}$/.test(normalizedUsername)) {
        issues.push("当前用户名不符合规范：请使用 3-32 位英文字母、数字或下划线。");
    }
    if (!password || password.length < 8 || password.length > 72) {
        issues.push("当前密码长度不符合规范：请输入 8-72 个字符。");
    }
    if (!/[A-Za-z]/.test(password || "")) {
        issues.push("当前密码缺少英文字母。");
    }
    if (!/\d/.test(password || "")) {
        issues.push("当前密码缺少数字。");
    }
    if (/\s/.test(password || "")) {
        issues.push("当前密码包含空白字符。");
    }
    return issues;
}

async function parseErrorDetails(response) {
    try {
        const payload = await response.json();
        if (Array.isArray(payload.details) && payload.details.length) {
            return payload.details;
        }
        if (payload.message) {
            return [payload.message];
        }
    } catch (ignored) {
    }
    return ["请求失败，请稍后重试。"];
}

async function submitAuth(event) {
    event.preventDefault();
    setFormMessage(elements.authMessage, "", "");
    const payload = {
        username: elements.authUsername.value,
        password: elements.authPassword.value,
        displayName: elements.authDisplayName.value
    };
    if (state.authMode === "register") {
        const issues = validateRegistration(payload.username, payload.password);
        if (issues.length) {
            setFormMessage(elements.authMessage, issues.concat(["完整注册规范："]).concat(AUTH_RULES), "error");
            return;
        }
    }
    const endpoint = state.authMode === "register" ? "/api/auth/register" : "/api/auth/login";
    const response = await fetch(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        setFormMessage(elements.authMessage, await parseErrorDetails(response), "error");
        return;
    }
    const result = await response.json();
    state.currentUser = result.user || null;
    renderAuthState();
    closeModals();
}

async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    state.currentUser = null;
    renderAuthState();
}

function openEditor(post) {
    if (!state.currentUser) {
        openAuthModal("login");
        return;
    }
    elements.articleForm.reset();
    setFormMessage(elements.articleMessage, "", "");
    if (post) {
        elements.editorTitle.textContent = "编辑文章";
        elements.articleSubmitButton.textContent = "保存";
        elements.deleteArticleButton.hidden = !canManage(post);
        elements.articleId.value = post.id || "";
        elements.articleTitle.value = post.title || "";
        elements.articleSlug.value = post.slug || "";
        elements.articleSummary.value = post.summary || "";
        elements.articleCategory.value = post.category || "";
        elements.articleTags.value = (post.tags || []).join(", ");
        elements.articleContent.value = post.contentHtml || "";
    } else {
        elements.editorTitle.textContent = "新增文章";
        elements.articleSubmitButton.textContent = "发布";
        elements.deleteArticleButton.hidden = true;
        elements.articleId.value = "";
    }
    elements.editorModal.hidden = false;
}

async function openEditorBySlug(slug) {
    const response = await fetch("/api/blog/articles/" + encodeURIComponent(slug));
    if (!response.ok) {
        renderError("文章不存在或接口不可用");
        return;
    }
    const payload = await response.json();
    openEditor(payload.article);
}

async function submitArticle(event) {
    event.preventDefault();
    setFormMessage(elements.articleMessage, "正在保存...", "");
    const formData = new FormData(elements.articleForm);
    const id = formData.get("id");
    const payload = {
        title: formData.get("title"),
        slug: formData.get("slug"),
        summary: formData.get("summary"),
        category: formData.get("category"),
        tags: splitTags(formData.get("tags")),
        contentHtml: formData.get("contentHtml")
    };
    const response = await fetch(id ? "/api/blog/articles/" + encodeURIComponent(id) : "/api/blog/articles", {
        method: id ? "PUT" : "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });
    if (response.status === 401) {
        closeModals();
        openAuthModal("login");
        return;
    }
    if (!response.ok) {
        setFormMessage(elements.articleMessage, await parseErrorDetails(response), "error");
        return;
    }
    setFormMessage(elements.articleMessage, id ? "保存成功" : "发布成功", "success");
    closeModals();
    await loadFilters();
    await loadArticles();
}

async function deleteArticle(id) {
    if (!id || !window.confirm("确定删除这篇文章吗？此操作不可撤销。")) {
        return;
    }
    const response = await fetch("/api/blog/articles/" + encodeURIComponent(id), { method: "DELETE" });
    if (!response.ok) {
        setFormMessage(elements.articleMessage, await parseErrorDetails(response), "error");
        return;
    }
    closeModals();
    await loadFilters();
    await loadArticles();
}

function splitTags(value) {
    if (!value) {
        return [];
    }
    return value.split(",").map(function(tag) {
        return tag.trim();
    }).filter(Boolean);
}

function setFormMessage(element, message, type) {
    const messages = Array.isArray(message) ? message : (message ? [message] : []);
    element.className = type ? "form-message " + type : "form-message";
    if (!messages.length) {
        element.textContent = "";
        return;
    }
    if (messages.length === 1) {
        element.textContent = messages[0];
        return;
    }
    element.innerHTML = '<ul>' + messages.map(function(item) {
        return '<li>' + escapeHtml(item) + '</li>';
    }).join("") + '</ul>';
}

async function renderPostDetail(slug) {
    const response = await fetch("/api/blog/articles/" + encodeURIComponent(slug));
    if (!response.ok) {
        renderError("文章不存在或接口不可用");
        return;
    }
    const payload = await response.json();
    const post = payload.article;
    const author = post.authorDisplayName || post.authorUsername || "未归属";
    const management = canManage(post) ? [
        '<div class="post-actions">',
        '<button type="button" data-edit-article="' + post.id + '" data-edit-slug="' + escapeHtml(post.slug) + '">编辑</button>',
        '<button type="button" class="danger-text-button" data-delete-article="' + post.id + '">删除</button>',
        '</div>'
    ].join("") : "";

    elements.postList.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postDetail.hidden = false;
    setActiveNav("#posts");
    elements.postDetail.innerHTML = [
        '<button class="back-button" type="button" id="backToList">返回列表</button>',
        '<p class="eyebrow">' + escapeHtml(post.category) + '</p>',
        '<h1>' + escapeHtml(post.title) + '</h1>',
        '<div class="post-meta"><time>' + formatDate(post.publishedAt) + '</time><span>' + escapeHtml(post.wordCount) + ' 字</span><span>' + escapeHtml(post.readMinutes) + ' 分钟</span><span>作者：' + escapeHtml(author) + '</span></div>',
        '<p>' + escapeHtml(post.summary) + '</p>',
        management,
        '<div class="article-body">' + (post.contentHtml || "") + '</div>',
        '<div class="post-tags">' + (post.tags || []).map(function(tag) { return '<span class="post-tag">' + escapeHtml(tag) + '</span>'; }).join("") + '</div>'
    ].join("");
}

function renderArchive() {
    const grouped = state.articles.reduce(function(result, post) {
        const year = (post.publishedAt || "").slice(0, 4) || "未发布";
        result[year] = result[year] || [];
        result[year].push(post);
        return result;
    }, {});

    elements.postList.hidden = true;
    elements.postDetail.hidden = true;
    elements.archivePanel.hidden = false;
    setActiveNav("#archive");
    elements.archivePanel.innerHTML = '<p class="eyebrow">Archive</p><h1>文章归档</h1>' + Object.keys(grouped).sort().reverse().map(function(year) {
        return '<section class="archive-year"><h2>' + escapeHtml(year) + '</h2>' + grouped[year].map(function(post) {
            return '<div class="archive-item" data-post-slug="' + escapeHtml(post.slug) + '"><time>' + formatDate(post.publishedAt) + '</time><strong>' + escapeHtml(post.title) + '</strong></div>';
        }).join("") + '</section>';
    }).join("");
}

function resetFilters() {
    state.category = "";
    state.tag = "";
    state.keyword = "";
    elements.searchInput.value = "";
    renderFilters();
    loadArticles().catch(function() {
        renderError("文章列表接口不可用");
    });
}

function applyTheme(theme) {
    document.documentElement.dataset.theme = theme === "dark" ? "dark" : "";
    elements.themeToggle.textContent = theme === "dark" ? "日间" : "夜间";
    elements.themeToggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    localStorage.setItem("blogTheme", theme);
}

document.addEventListener("click", function(event) {
    const editButton = event.target.closest("[data-edit-article]");
    const deleteButton = event.target.closest("[data-delete-article]");
    const categoryButton = event.target.closest("[data-category]");
    const tagButton = event.target.closest("[data-tag]");
    const postCard = event.target.closest("[data-post-slug]");

    if (editButton) {
        event.preventDefault();
        event.stopPropagation();
        openEditorBySlug(editButton.dataset.editSlug);
        return;
    }

    if (deleteButton) {
        event.preventDefault();
        event.stopPropagation();
        deleteArticle(deleteButton.dataset.deleteArticle);
        return;
    }

    if (categoryButton) {
        state.category = categoryButton.dataset.category;
        renderFilters();
        loadArticles().catch(function() {
            renderError("文章列表接口不可用");
        });
        return;
    }

    if (tagButton) {
        state.tag = state.tag === tagButton.dataset.tag ? "" : tagButton.dataset.tag;
        renderFilters();
        loadArticles().catch(function() {
            renderError("文章列表接口不可用");
        });
        return;
    }

    if (postCard) {
        renderPostDetail(postCard.dataset.postSlug);
        scrollToHash("#posts");
        return;
    }

    if (event.target.id === "backToList") {
        renderPostList();
    }

    if (event.target.matches("[data-close-modal]")) {
        closeModals();
    }
});

document.querySelectorAll('a[href="#archive"]').forEach(function(link) {
    link.addEventListener("click", function(event) {
        event.preventDefault();
        renderArchive();
        scrollToHash("#posts");
    });
});

document.querySelectorAll('a[href="#posts"]').forEach(function(link) {
    link.addEventListener("click", function(event) {
        event.preventDefault();
        renderPostList("#posts");
        scrollToHash("#posts");
    });
});

elements.searchInput.addEventListener("input", function(event) {
    state.keyword = event.target.value;
    loadArticles().catch(function() {
        renderError("文章列表接口不可用");
    });
});

elements.resetFilters.addEventListener("click", resetFilters);
elements.loginButton.addEventListener("click", function() {
    openAuthModal("login");
});
elements.registerButton.addEventListener("click", function() {
    openAuthModal("register");
});
elements.logoutButton.addEventListener("click", logout);
elements.writeButton.addEventListener("click", function() {
    openEditor();
});
elements.authForm.addEventListener("submit", function(event) {
    submitAuth(event).catch(function() {
        setFormMessage(elements.authMessage, "认证接口不可用", "error");
    });
});
elements.articleForm.addEventListener("submit", function(event) {
    submitArticle(event).catch(function() {
        setFormMessage(elements.articleMessage, "文章接口不可用", "error");
    });
});
elements.deleteArticleButton.addEventListener("click", function() {
    deleteArticle(elements.articleId.value);
});

elements.themeToggle.addEventListener("click", function() {
    const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
});

applyTheme(localStorage.getItem("blogTheme") || "light");
renderUserPanel();
loadCurrentUser();
loadFilters()
    .then(loadArticles)
    .catch(function() {
        renderError("博客接口不可用");
    });
