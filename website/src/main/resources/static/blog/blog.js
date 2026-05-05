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
    authModal: document.getElementById("authModal"),
    authForm: document.getElementById("authForm"),
    authTitle: document.getElementById("authTitle"),
    authModeLabel: document.getElementById("authModeLabel"),
    displayNameRow: document.getElementById("displayNameRow"),
    authUsername: document.getElementById("authUsername"),
    authDisplayName: document.getElementById("authDisplayName"),
    authPassword: document.getElementById("authPassword"),
    authMessage: document.getElementById("authMessage"),
    editorModal: document.getElementById("editorModal"),
    articleForm: document.getElementById("articleForm"),
    articleMessage: document.getElementById("articleMessage")
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

function formatDate(value) {
    if (!value) {
        return "";
    }
    return value.slice(0, 10);
}

function renderFilters() {
    const categoryButtons = ["全部"].concat(state.categories).map(function(category) {
        const value = category === "全部" ? "" : category;
        const active = value === state.category ? " active" : "";
        return '<button class="chip' + active + '" type="button" data-category="' + value + '">' + category + '</button>';
    });

    elements.categoryList.innerHTML = categoryButtons.join("");
    elements.tagList.innerHTML = state.tags.map(function(tag) {
        const active = tag === state.tag ? " active" : "";
        return '<button class="chip' + active + '" type="button" data-tag="' + tag + '">' + tag + '</button>';
    }).join("");
}

function renderPostList() {
    elements.postDetail.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postList.hidden = false;
    elements.listTitle.textContent = state.articles.length ? "最新文章" : "没有匹配的文章";

    elements.postList.innerHTML = state.articles.map(function(post) {
        return [
            '<article class="post-card" data-post-slug="' + post.slug + '">',
            '<div class="post-meta">',
            '<span class="category-badge">' + post.category + '</span>',
            '<time>' + formatDate(post.publishedAt) + '</time>',
            '<span>' + post.wordCount + ' 字</span>',
            '<span>' + post.readMinutes + ' 分钟</span>',
            '</div>',
            '<h3>' + post.title + '</h3>',
            '<p>' + post.summary + '</p>',
            '<div class="post-tags">' + post.tags.map(function(tag) { return '<span class="post-tag">' + tag + '</span>'; }).join("") + '</div>',
            '</article>'
        ].join("");
    }).join("");
}

function renderError(message) {
    elements.postDetail.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postList.hidden = false;
    elements.listTitle.textContent = "加载失败";
    elements.postList.innerHTML = '<article class="post-card"><h3>' + message + '</h3><p>请确认 website 应用已启动，并且数据库可用。</p></article>';
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
}

function openAuthModal(mode) {
    state.authMode = mode;
    elements.authTitle.textContent = mode === "register" ? "注册" : "登录";
    elements.authModeLabel.textContent = mode === "register" ? "Register" : "Login";
    elements.displayNameRow.hidden = mode !== "register";
    elements.authPassword.setAttribute("autocomplete", mode === "register" ? "new-password" : "current-password");
    elements.authMessage.textContent = "";
    elements.authMessage.className = "form-message";
    elements.authForm.reset();
    elements.authModal.hidden = false;
}

function closeModals() {
    elements.authModal.hidden = true;
    elements.editorModal.hidden = true;
}

async function submitAuth(event) {
    event.preventDefault();
    setFormMessage(elements.authMessage, "", "");
    const payload = {
        username: elements.authUsername.value,
        password: elements.authPassword.value,
        displayName: elements.authDisplayName.value
    };
    const endpoint = state.authMode === "register" ? "/api/auth/register" : "/api/auth/login";
    const response = await fetch(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        setFormMessage(elements.authMessage, "用户名或密码不符合要求", "error");
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

function openEditor() {
    if (!state.currentUser) {
        openAuthModal("login");
        return;
    }
    elements.articleForm.reset();
    setFormMessage(elements.articleMessage, "", "");
    elements.editorModal.hidden = false;
}

async function submitArticle(event) {
    event.preventDefault();
    setFormMessage(elements.articleMessage, "正在发布...", "");
    const formData = new FormData(elements.articleForm);
    const payload = {
        title: formData.get("title"),
        slug: formData.get("slug"),
        summary: formData.get("summary"),
        category: formData.get("category"),
        tags: splitTags(formData.get("tags")),
        contentHtml: formData.get("contentHtml")
    };
    const response = await fetch("/api/blog/articles", {
        method: "POST",
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
        setFormMessage(elements.articleMessage, "发布失败，请检查标题、摘要、分类和 slug 是否有效", "error");
        return;
    }
    setFormMessage(elements.articleMessage, "发布成功", "success");
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
    element.textContent = message;
    element.className = type ? "form-message " + type : "form-message";
}

async function renderPostDetail(slug) {
    const response = await fetch("/api/blog/articles/" + encodeURIComponent(slug));
    if (!response.ok) {
        renderError("文章不存在或接口不可用");
        return;
    }
    const payload = await response.json();
    const post = payload.article;

    elements.postList.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postDetail.hidden = false;
    elements.postDetail.innerHTML = [
        '<button class="back-button" type="button" id="backToList">返回列表</button>',
        '<p class="eyebrow">' + post.category + '</p>',
        '<h1>' + post.title + '</h1>',
        '<div class="post-meta"><time>' + formatDate(post.publishedAt) + '</time><span>' + post.wordCount + ' 字</span><span>' + post.readMinutes + ' 分钟</span></div>',
        '<p>' + post.summary + '</p>',
        '<div class="article-body">' + post.contentHtml + '</div>',
        '<div class="post-tags">' + post.tags.map(function(tag) { return '<span class="post-tag">' + tag + '</span>'; }).join("") + '</div>'
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
    elements.archivePanel.innerHTML = '<p class="eyebrow">Archive</p><h1>文章归档</h1>' + Object.keys(grouped).sort().reverse().map(function(year) {
        return '<section class="archive-year"><h2>' + year + '</h2>' + grouped[year].map(function(post) {
            return '<div class="archive-item" data-post-slug="' + post.slug + '"><time>' + formatDate(post.publishedAt) + '</time><strong>' + post.title + '</strong></div>';
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
    localStorage.setItem("blogTheme", theme);
}

document.addEventListener("click", function(event) {
    const categoryButton = event.target.closest("[data-category]");
    const tagButton = event.target.closest("[data-tag]");
    const postCard = event.target.closest("[data-post-slug]");

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
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
    }

    if (event.target.id === "backToList") {
        renderPostList();
    }

    if (event.target.matches("[data-close-modal]")) {
        closeModals();
    }
});

document.querySelector('a[href="#archive"]').addEventListener("click", function(event) {
    event.preventDefault();
    renderArchive();
});

document.querySelector('a[href="#home"]').addEventListener("click", function(event) {
    event.preventDefault();
    renderPostList();
});

document.querySelector('a[href="#about"]').addEventListener("click", function(event) {
    event.preventDefault();
    elements.postList.hidden = true;
    elements.archivePanel.hidden = true;
    elements.postDetail.hidden = false;
    elements.postDetail.innerHTML = '<button class="back-button" type="button" id="backToList">返回列表</button><p class="eyebrow">About</p><h1>关于这个博客</h1><p>这是 website 模块中的个人博客微应用。页面通过 /api/blog 接口读取 MySQL 中的文章数据，后端使用 Spring MVC、Service 和 JdbcTemplate Repository 分层实现。</p>';
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
elements.writeButton.addEventListener("click", openEditor);
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

elements.themeToggle.addEventListener("click", function() {
    const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
});

applyTheme(localStorage.getItem("blogTheme") || "light");
loadCurrentUser();
loadFilters()
    .then(loadArticles)
    .catch(function() {
        renderError("博客接口不可用");
    });
