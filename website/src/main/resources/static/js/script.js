console.log("%cLOVE530 Moon Command", "background:#ffffff;color:#05080d;font-size:18px;font-weight:800;padding:8px 12px;");

function setupHeroVideo() {
    var video = document.querySelector(".hero-video");
    if (!video) {
        return;
    }

    function markReady() {
        if (video.readyState >= 2) {
            document.body.classList.add("video-ready");
        }
    }

    video.addEventListener("loadeddata", markReady);
    video.addEventListener("canplay", markReady);
    video.addEventListener("error", function () {
        document.body.classList.remove("video-ready");
    });
    markReady();
}

function setupAuth() {
    var authPopup = document.querySelector(".auth-pop-up");
    var authForm = document.querySelector(".auth-pop-up-main");
    var authTitle = document.querySelector(".auth-pop-up-title");
    var authCopy = document.querySelector(".auth-pop-up-copy");
    var authUsername = document.querySelector(".auth-username");
    var authDisplayNameWrap = document.querySelector(".auth-display-name-wrap");
    var authDisplayName = document.querySelector(".auth-display-name");
    var authPassword = document.querySelector(".auth-password");
    var authMessage = document.querySelector(".auth-message");
    var authSubmitButton = document.querySelector(".auth-submit-button");
    var loginButton = document.querySelector(".auth-login-button");
    var registerButton = document.querySelector(".auth-register-button");
    var logoutButton = document.querySelector(".auth-logout-button");
    var closeButton = document.querySelector(".auth-pop-up-close");
    var authMode = "login";
    var currentUser = null;
    var pendingProtectedLink = null;

    if (!authPopup || !authForm) {
        return;
    }

    function setAuthState(user) {
        var loggedIn = !!user;
        currentUser = user || null;
        if (loginButton) {
            loginButton.style.display = loggedIn ? "none" : "inline-flex";
        }
        if (registerButton) {
            registerButton.style.display = loggedIn ? "none" : "inline-flex";
        }
        if (logoutButton) {
            logoutButton.style.display = loggedIn ? "inline-flex" : "none";
        }
    }

    function openAuth(mode) {
        authMode = mode;
        authTitle.textContent = mode === "register" ? "Create Account" : "Login";
        authCopy.textContent = mode === "register"
            ? "创建账号后，可以访问需要鉴权的服务入口。"
            : "登录后可以访问受保护项目，并保持当前工作区连接。";
        authSubmitButton.textContent = mode === "register" ? "创建账号" : "继续";
        authDisplayNameWrap.style.display = mode === "register" ? "grid" : "none";
        authDisplayName.required = mode === "register";
        authPassword.setAttribute("autocomplete", mode === "register" ? "new-password" : "current-password");
        authMessage.textContent = "";
        authForm.reset();
        authPopup.classList.add("active");
        authUsername.focus();
    }

    function closeAuth() {
        authPopup.classList.remove("active");
    }

    function openProtectedLink(link) {
        if (!link || !link.href) {
            return;
        }
        window.open(link.href, link.target || "_blank", "noopener");
    }

    function requireLoginForLink(event, link) {
        event.preventDefault();
        if (currentUser) {
            openProtectedLink(link);
            return;
        }
        fetch("/api/auth/me")
            .then(function (response) {
                if (!response.ok) {
                    return null;
                }
                return response.json();
            })
            .then(function (payload) {
                if (payload && payload.user) {
                    setAuthState(payload.user);
                    openProtectedLink(link);
                    return;
                }
                pendingProtectedLink = {
                    href: link.href,
                    target: link.target
                };
                openAuth("login");
                authMessage.textContent = "需要登录后访问 " + (link.getAttribute("data-auth-target-name") || "该项目") + "。";
            })
            .catch(function () {
                pendingProtectedLink = {
                    href: link.href,
                    target: link.target
                };
                openAuth("login");
                authMessage.textContent = "需要登录后访问该项目";
            });
    }

    function loadMe() {
        fetch("/api/auth/me")
            .then(function (response) {
                if (!response.ok) {
                    setAuthState(null);
                    return null;
                }
                return response.json();
            })
            .then(function (payload) {
                if (payload) {
                    setAuthState(payload.user);
                }
            })
            .catch(function () {
                setAuthState(null);
            });
    }

    if (loginButton) {
        loginButton.addEventListener("click", function () {
            openAuth("login");
        });
    }
    if (registerButton) {
        registerButton.addEventListener("click", function () {
            openAuth("register");
        });
    }
    if (closeButton) {
        closeButton.addEventListener("click", closeAuth);
    }
    if (logoutButton) {
        logoutButton.addEventListener("click", function () {
            fetch("/api/auth/logout", { method: "POST" }).then(function () {
                setAuthState(null);
            });
        });
    }

    authPopup.addEventListener("click", function (event) {
        if (event.target === authPopup) {
            closeAuth();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeAuth();
        }
    });

    document.addEventListener("click", function (event) {
        var link = event.target.closest('[data-auth-required="true"]');
        if (link) {
            requireLoginForLink(event, link);
        }
    });

    authForm.addEventListener("submit", function (event) {
        event.preventDefault();
        authMessage.textContent = "";
        authSubmitButton.disabled = true;
        var payload = {
            username: authUsername.value,
            password: authPassword.value
        };
        if (authMode === "register") {
            payload.displayName = authDisplayName.value;
        }
        fetch(authMode === "register" ? "/api/auth/register" : "/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("auth failed");
            }
            return response.json();
        }).then(function (payload) {
            setAuthState(payload.user);
            closeAuth();
            if (pendingProtectedLink) {
                openProtectedLink(pendingProtectedLink);
                pendingProtectedLink = null;
            }
        }).catch(function () {
            authMessage.textContent = "登录或注册失败，请检查账号密码。";
        }).finally(function () {
            authSubmitButton.disabled = false;
        });
    });

    loadMe();
}

function setupServiceHealth() {
    var serviceCards = Array.prototype.slice.call(document.querySelectorAll(".service-card[data-health-url]"));
    if (!serviceCards.length) {
        return;
    }

    function setServiceState(card, state) {
        var status = card.querySelector(".service-status");
        var message = state === "online" ? "可用" : state === "offline" ? "不可用" : "检测中";
        card.classList.toggle("is-online", state === "online");
        card.classList.toggle("is-offline", state === "offline");
        if (status) {
            status.setAttribute("aria-label", message);
            status.setAttribute("title", message);
        }
    }

    function checkService(card) {
        var healthUrl = card.getAttribute("data-health-url");
        var healthMode = card.getAttribute("data-health-mode");
        if (!healthUrl) {
            return;
        }
        setServiceState(card, "checking");
        var options = {
            method: "GET",
            cache: "no-store"
        };
        if (healthMode === "no-cors") {
            options.mode = "no-cors";
        }
        fetch(healthUrl, options)
            .then(function (response) {
                if (response.type === "opaque" || response.ok) {
                    setServiceState(card, "online");
                    return;
                }
                setServiceState(card, "offline");
            })
            .catch(function () {
                setServiceState(card, "offline");
            });
    }

    function checkAllServices() {
        serviceCards.forEach(checkService);
    }

    checkAllServices();
    window.setInterval(checkAllServices, 30000);
}

document.addEventListener("DOMContentLoaded", function () {
    setupHeroVideo();
    setupAuth();
    setupServiceHealth();
});
