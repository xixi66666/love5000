console.log("%cCaleb XXY AI Innovation Hub", "background:#ffffff;color:#05080d;font-size:18px;font-weight:800;padding:8px 12px;");

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

function setupFallbackCanvas() {
    var canvas = document.getElementById("fallback-canvas");
    if (!canvas) {
        return;
    }

    var ctx = canvas.getContext("2d", { alpha: false });
    var dpr = 1;
    var stars = [];
    var particles = [];
    var pointer = { x: 0.5, y: 0.18 };
    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function random(min, max) {
        return min + Math.random() * (max - min);
    }

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 1.6);
        canvas.width = Math.floor(window.innerWidth * dpr);
        canvas.height = Math.floor(window.innerHeight * dpr);
        canvas.style.width = window.innerWidth + "px";
        canvas.style.height = window.innerHeight + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        seed();
    }

    function seed() {
        var w = window.innerWidth;
        var h = window.innerHeight;
        var starCount = w < 720 ? 80 : 140;
        var particleCount = w < 720 ? 420 : 980;
        stars = [];
        particles = [];

        for (var i = 0; i < starCount; i++) {
            stars.push({
                x: Math.random() * w,
                y: Math.random() * h,
                r: random(0.45, 1.35),
                a: random(0.12, 0.82),
                p: Math.random() * 10
            });
        }

        for (var j = 0; j < particleCount; j++) {
            particles.push({
                angle: random(Math.PI * 0.03, Math.PI * 1.05),
                radius: random(0.12, 0.58),
                drift: random(-1, 1),
                size: random(0.35, 1.2),
                alpha: random(0.035, 0.34),
                phase: Math.random() * 1000
            });
        }
    }

    function strokeOrbit(cx, cy, rx, ry, start, end, alpha, width, time, offset) {
        ctx.beginPath();
        var steps = 96;
        for (var i = 0; i <= steps; i++) {
            var t = i / steps;
            var a = start + (end - start) * t;
            var noise = Math.sin(a * 11 + time * 0.0007 + offset) * 3.8 +
                Math.sin(a * 23 - time * 0.00045 + offset * 0.7) * 1.7;
            var x = cx + Math.cos(a) * (rx + noise);
            var y = cy + Math.sin(a) * (ry + noise * 0.22);
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.strokeStyle = "rgba(178, 226, 255, " + alpha + ")";
        ctx.lineWidth = width;
        ctx.stroke();
    }

    function draw(time) {
        var w = window.innerWidth;
        var h = window.innerHeight;
        var cx = w * (0.51 + (pointer.x - 0.5) * 0.018);
        var cy = h * (0.02 + (pointer.y - 0.18) * 0.018);
        var base = Math.min(w, h);
        var rxBase = Math.min(w * 0.48, 570);
        var ryBase = Math.min(h * 0.27, 220);

        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = "#010307";
        ctx.fillRect(0, 0, w, h);

        var sky = ctx.createRadialGradient(cx, cy + 60, base * 0.08, cx, cy + 80, base * 0.8);
        sky.addColorStop(0, "rgba(68, 171, 255, 0.24)");
        sky.addColorStop(0.26, "rgba(24, 76, 126, 0.16)");
        sky.addColorStop(0.64, "rgba(3, 13, 28, 0.45)");
        sky.addColorStop(1, "rgba(1, 3, 7, 1)");
        ctx.fillStyle = sky;
        ctx.fillRect(0, 0, w, h);

        stars.forEach(function (star) {
            var twinkle = 0.5 + Math.sin(time * 0.001 + star.p) * 0.5;
            ctx.fillStyle = "rgba(240, 248, 255, " + star.a * (0.45 + twinkle * 0.55) + ")";
            ctx.beginPath();
            ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
            ctx.fill();
        });

        ctx.globalCompositeOperation = "lighter";

        for (var layer = 0; layer < 70; layer++) {
            var span = random(Math.PI * 0.18, Math.PI * 0.9);
            var start = -Math.PI * 0.05 + layer * 0.019 + Math.sin(time * 0.00018 + layer) * 0.05;
            var end = start + span;
            var rx = rxBase * random(0.62, 1.16) + layer * 0.8;
            var ry = ryBase * random(0.58, 1.18) + layer * 0.22;
            strokeOrbit(cx, cy + layer * 0.2, rx, ry, start, end, random(0.01, 0.045), random(0.55, 1.35), time, layer);
        }

        particles.forEach(function (particle, index) {
            var spin = time * (0.000045 + particle.drift * 0.000018);
            var angle = particle.angle + spin + Math.sin(time * 0.0005 + particle.phase) * 0.045;
            var radius = rxBase * particle.radius * (1 + Math.sin(time * 0.0007 + particle.phase) * 0.035);
            var yScale = 0.33 + Math.sin(index * 1.7) * 0.055;
            var x = cx + Math.cos(angle) * radius * random(1.35, 2.15);
            var y = cy + Math.sin(angle) * radius * yScale + random(12, 110);
            var glow = ctx.createRadialGradient(x, y, 0, x, y, particle.size * 10);
            glow.addColorStop(0, "rgba(227, 247, 255, " + particle.alpha + ")");
            glow.addColorStop(0.3, "rgba(80, 181, 255, " + particle.alpha * 0.22 + ")");
            glow.addColorStop(1, "rgba(1, 3, 7, 0)");
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(x, y, particle.size * 8, 0, Math.PI * 2);
            ctx.fill();
        });

        var coreGlow = ctx.createRadialGradient(cx, cy + 74, 10, cx, cy + 74, rxBase * 0.74);
        coreGlow.addColorStop(0, "rgba(205, 237, 255, 0.1)");
        coreGlow.addColorStop(0.18, "rgba(78, 183, 255, 0.16)");
        coreGlow.addColorStop(0.42, "rgba(25, 87, 151, 0.11)");
        coreGlow.addColorStop(1, "rgba(1, 3, 7, 0)");
        ctx.fillStyle = coreGlow;
        ctx.beginPath();
        ctx.ellipse(cx, cy + 74, rxBase * 0.72, ryBase * 0.74, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.globalCompositeOperation = "destination-out";
        var blackCore = ctx.createRadialGradient(cx, cy + 88, 10, cx, cy + 88, rxBase * 0.48);
        blackCore.addColorStop(0, "rgba(0, 0, 0, 1)");
        blackCore.addColorStop(0.55, "rgba(0, 0, 0, 0.96)");
        blackCore.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = blackCore;
        ctx.beginPath();
        ctx.ellipse(cx, cy + 88, rxBase * 0.44, ryBase * 0.42, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.globalCompositeOperation = "source-over";
        var shade = ctx.createLinearGradient(0, 0, 0, h);
        shade.addColorStop(0, "rgba(0, 0, 0, 0)");
        shade.addColorStop(0.46, "rgba(0, 0, 0, 0.14)");
        shade.addColorStop(0.67, "rgba(0, 0, 0, 0.62)");
        shade.addColorStop(1, "rgba(0, 0, 0, 0.92)");
        ctx.fillStyle = shade;
        ctx.fillRect(0, 0, w, h);

        if (!reducedMotion) {
            requestAnimationFrame(draw);
        }
    }

    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", function (event) {
        pointer.x = event.clientX / window.innerWidth;
        pointer.y = event.clientY / window.innerHeight;
    });

    resize();
    requestAnimationFrame(draw);
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
        authTitle.textContent = mode === "register" ? "Register" : "Login";
        authCopy.textContent = mode === "register"
            ? "创建账号后，可以访问受保护项目。"
            : "登录后可以访问受保护项目，并保持当前工作区连接。";
        authSubmitButton.textContent = mode === "register" ? "Create account" : "Continue";
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
                authMessage.textContent = "需要登录后访问 " + (link.getAttribute("data-auth-target-name") || "该项目");
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

document.addEventListener("DOMContentLoaded", function () {
    setupHeroVideo();
    setupFallbackCanvas();
    setupAuth();
});
