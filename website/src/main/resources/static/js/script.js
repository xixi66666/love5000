console.log("%cXiXi Service Universe", "background:#ffffff;color:#18242d;font-size:16px;font-weight:700;padding:7px 11px;");

function setupHeroVideo() {
    var videos = Array.prototype.slice.call(document.querySelectorAll(".scene-video"));
    if (!videos.length) {
        return;
    }

    function markReady(video) {
        if (video.classList.contains("is-active") && video.readyState >= 2) {
            document.body.classList.add("video-ready");
        }
    }

    videos.forEach(function (video) {
        video.addEventListener("loadeddata", function () {
            markReady(video);
        });
        video.addEventListener("canplay", function () {
            markReady(video);
        });
        video.addEventListener("error", function () {
            if (video.classList.contains("is-active")) {
                document.body.classList.remove("video-ready");
            }
        });
        markReady(video);
    });
}

function setupVideoSwitcher() {
    var videos = Array.prototype.slice.call(document.querySelectorAll("[data-scene-video]"));
    var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-scene-index]"));
    var activeVideo = 0;
    var transitionLocked = false;
    var transitionDuration = 1000;

    if (!videos.length || !buttons.length) {
        return;
    }

    function safePlay(video) {
        var playResult = video.play();
        if (playResult && typeof playResult.catch === "function") {
            playResult.catch(function () {
                document.body.classList.remove("video-ready");
            });
        }
    }

    function setActiveState(nextIndex) {
        videos.forEach(function (video, index) {
            video.classList.toggle("is-active", index === nextIndex);
        });
        buttons.forEach(function (button, index) {
            var isActive = index === nextIndex;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
        document.body.classList.toggle("scene-deep-woods", nextIndex === 2);
    }

    function switchScene(nextIndex) {
        if (nextIndex === activeVideo || transitionLocked || !videos[nextIndex]) {
            return;
        }

        transitionLocked = true;
        safePlay(videos[nextIndex]);
        setActiveState(nextIndex);
        activeVideo = nextIndex;

        window.setTimeout(function () {
            videos.forEach(function (video, index) {
                if (index !== activeVideo) {
                    video.pause();
                }
            });
            transitionLocked = false;
        }, transitionDuration);
    }

    buttons.forEach(function (button) {
        button.addEventListener("click", function () {
            switchScene(Number(button.getAttribute("data-scene-index")));
        });
    });

    videos.forEach(function (video, index) {
        if (index === activeVideo) {
            safePlay(video);
        } else {
            video.pause();
        }
    });
    setActiveState(activeVideo);
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
    var loginButtons = Array.prototype.slice.call(document.querySelectorAll(".auth-login-button"));
    var registerButtons = Array.prototype.slice.call(document.querySelectorAll(".auth-register-button"));
    var logoutButtons = Array.prototype.slice.call(document.querySelectorAll(".auth-logout-button"));
    var closeButton = document.querySelector(".auth-pop-up-close");
    var authMode = "login";
    var currentUser = null;
    var pendingProtectedLink = null;

    if (!authPopup || !authForm) {
        return;
    }

    function showButtons(buttons, visible) {
        buttons.forEach(function (button) {
            button.hidden = !visible;
        });
    }

    function setAuthState(user) {
        var loggedIn = !!user;
        currentUser = user || null;
        showButtons(loginButtons, !loggedIn);
        showButtons(registerButtons, !loggedIn);
        showButtons(logoutButtons, loggedIn);
    }

    function openAuth(mode) {
        authMode = mode;
        authTitle.textContent = mode === "register" ? "创建账号" : "欢迎回来";
        authCopy.textContent = mode === "register"
            ? "创建账号后，可以进入需要鉴权的私人服务。"
            : "登录后可以访问受保护项目，并保持当前工作区连接。";
        authSubmitButton.textContent = mode === "register" ? "创建账号" : "继续";
        authDisplayNameWrap.hidden = mode !== "register";
        authDisplayName.required = mode === "register";
        authPassword.setAttribute("autocomplete", mode === "register" ? "new-password" : "current-password");
        authMessage.textContent = "";
        authForm.reset();
        authPopup.classList.add("active");
        authPopup.setAttribute("aria-hidden", "false");
        window.setTimeout(function () {
            authUsername.focus();
        }, 30);
    }

    function closeAuth() {
        authPopup.classList.remove("active");
        authPopup.setAttribute("aria-hidden", "true");
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
                return response.ok ? response.json() : null;
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
                authMessage.textContent = "登录后即可访问 " + (link.getAttribute("data-auth-target-name") || "该项目") + "。";
            })
            .catch(function () {
                pendingProtectedLink = {
                    href: link.href,
                    target: link.target
                };
                openAuth("login");
                authMessage.textContent = "登录后即可访问该项目。";
            });
    }

    function loadMe() {
        fetch("/api/auth/me")
            .then(function (response) {
                return response.ok ? response.json() : null;
            })
            .then(function (payload) {
                setAuthState(payload && payload.user ? payload.user : null);
            })
            .catch(function () {
                setAuthState(null);
            });
    }

    loginButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            openAuth("login");
        });
    });

    registerButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            openAuth("register");
        });
    });

    logoutButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            fetch("/api/auth/logout", { method: "POST" }).then(function () {
                setAuthState(null);
            });
        });
    });

    if (closeButton) {
        closeButton.addEventListener("click", closeAuth);
    }

    authPopup.addEventListener("click", function (event) {
        if (event.target === authPopup) {
            closeAuth();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && authPopup.classList.contains("active")) {
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
        var payload;
        event.preventDefault();
        authMessage.textContent = "";
        authSubmitButton.disabled = true;
        payload = {
            username: authUsername.value.trim(),
            password: authPassword.value
        };
        if (authMode === "register") {
            payload.displayName = authDisplayName.value.trim();
        }

        fetch(authMode === "register" ? "/api/auth/register" : "/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("auth failed");
                }
                return response.json();
            })
            .then(function (responsePayload) {
                setAuthState(responsePayload.user);
                closeAuth();
                if (pendingProtectedLink) {
                    openProtectedLink(pendingProtectedLink);
                    pendingProtectedLink = null;
                }
            })
            .catch(function () {
                authMessage.textContent = "登录或注册失败，请检查账号与密码。";
            })
            .then(function () {
                authSubmitButton.disabled = false;
            });
    });

    setAuthState(null);
    loadMe();
}

function setupServiceHealth() {
    var serviceCards = Array.prototype.slice.call(document.querySelectorAll(".service-card[data-health-url]"));

    if (!serviceCards.length) {
        return;
    }

    function setServiceState(card, state) {
        var status = card.querySelector(".service-status");
        var message = state === "online" ? "在线" : state === "offline" ? "离线" : "检测中";
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
        var options = {
            method: "GET",
            cache: "no-store"
        };

        if (!healthUrl) {
            return;
        }
        if (healthMode === "no-cors") {
            options.mode = "no-cors";
        }

        setServiceState(card, "checking");
        fetch(healthUrl, options)
            .then(function (response) {
                setServiceState(card, response.type === "opaque" || response.ok ? "online" : "offline");
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
    setupVideoSwitcher();
    setupAuth();
    setupServiceHealth();
});
