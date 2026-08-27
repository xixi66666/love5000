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
        document.body.setAttribute("data-scene-theme", String(nextIndex));
        window.__xixiActiveScene = nextIndex;
        window.dispatchEvent(new CustomEvent("xixiscenechange", {
            detail: { sceneIndex: nextIndex }
        }));
    }

    function switchScene(nextIndex) {
        if (nextIndex === activeVideo || transitionLocked || !videos[nextIndex]) {
            return;
        }

        transitionLocked = true;
        videos[nextIndex].load();
        safePlay(videos[nextIndex]);
        setActiveState(nextIndex);
        activeVideo = nextIndex;

        if (typeof window.__xixiSceneCrossfade === "function") {
            window.__xixiSceneCrossfade();
        }

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
        if (index !== activeVideo) {
            video.pause();
        }
    });
    setActiveState(activeVideo);

    var deferFirstPlay = window.requestIdleCallback || function (fn) {
        window.setTimeout(fn, 350);
    };
    deferFirstPlay(function () {
        safePlay(videos[activeVideo]);
    });
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
        try {
            card.dispatchEvent(new CustomEvent("servicestate", { detail: { state: state } }));
        } catch (err) {
            card.dispatchEvent({ type: "servicestate", detail: { state: state } });
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

function setupServiceFx() {
    var FX_VERTEX_SHADER = [
        "attribute vec2 aPos;",
        "varying vec2 vUv;",
        "void main() {",
        "    vUv = vec2(aPos.x * 0.5 + 0.5, aPos.y * 0.5 + 0.5);",
        "    gl_Position = vec4(aPos, 0.0, 1.0);",
        "}"
    ].join("\n");

    var FX_FRAGMENT_SHADER = [
        "precision highp float;",
        "",
        "varying vec2 vUv;",
        "uniform vec2 uRes;",
        "uniform float uFlow;",
        "uniform float uAurora;",
        "uniform vec3 uPrimaryColor;",
        "uniform vec3 uSecondaryColor;",
        "uniform vec3 uHighlightColor;",
        "uniform float uVariation;",
        "uniform float uHover;",
        "uniform float uEnergy;",
        "uniform vec2 uPointer;",
        "uniform float uRadius;",
        "",
        "float sdRoundRect(vec2 p, vec2 b, float r) {",
        "    vec2 q = abs(p) - b + r;",
        "    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;",
        "}",
        "",
        "float band(float t, float center, float width) {",
        "    float d = t - center;",
        "    d -= floor(d + 0.5);",
        "    return exp(-(d * d) / width);",
        "}",
        "",
        "vec3 boostSaturation(vec3 color, float amount) {",
        "    float luminance = dot(color, vec3(0.299, 0.587, 0.114));",
        "    return clamp(mix(vec3(luminance), color, amount), 0.0, 1.0);",
        "}",
        "",
        "void main() {",
        "    vec2 p = (vUv - 0.5) * uRes;",
        "    float d = sdRoundRect(p, uRes * 0.5, uRadius);",
        "    float aa = 1.25;",
        "    float inside = 1.0 - smoothstep(-aa, aa, d);",
        "",
        "    float ringHalf = max(uRadius * 0.06, 1.15);",
        "    float ring = 1.0 - smoothstep(ringHalf, ringHalf + aa * 2.2, abs(d));",
        "    float innerMask = inside * (1.0 - smoothstep(-uRadius * 0.72, -1.0, d));",
        "",
        "    float tParam = (p.x + p.y) / (uRes.x + uRes.y);",
        "    float speed = 0.085 + uHover * 0.10 + uEnergy * 0.20;",
        "    float t1 = fract(tParam * 1.65 - uFlow * speed);",
        "    float t2 = fract(tParam * 1.65 - uFlow * speed * 0.61 + 0.33);",
        "    float t3 = fract(tParam * 1.65 + uFlow * speed * 0.43 + 0.71);",
        "    float stream = band(t1, 0.0, 0.0065)",
        "                 + band(t2, 0.0, 0.0170) * 0.42",
        "                 + band(t3, 0.0, 0.0420) * 0.16;",
        "",
        "    float colorDrift = 0.5 + 0.5 * sin(uAurora * 0.22 + tParam * 4.0 + uVariation * 6.2831);",
        "    float paletteMix = clamp(uVariation * 0.56 + colorDrift * 0.32, 0.0, 1.0);",
        "    vec3 streamColor = mix(uPrimaryColor, uSecondaryColor, paletteMix);",
        "    streamColor = mix(streamColor, uHighlightColor, 0.12 + stream * 0.10);",
        "    streamColor = boostSaturation(streamColor, 1.16);",
        "    float streamGain = 0.40 + uHover * 0.44 + uEnergy * 0.56;",
        "    float borderAlpha = ring * stream * streamGain;",
        "",
        "    float interiorParam = fract(vUv.x * 0.82 + vUv.y * 0.30 - uFlow * 0.055 + uVariation * 0.17);",
        "    float interiorRibbon = band(interiorParam, 0.0, 0.018)",
        "                         + band(fract(interiorParam + 0.46), 0.0, 0.052) * 0.34;",
        "    float interiorShimmer = 0.72 + 0.28 * sin(uAurora * 0.34 + vUv.y * 5.4 + uVariation * 5.0);",
        "    float interiorAlpha = innerMask * interiorShimmer",
        "                        * (0.018 + interiorRibbon * (0.090 + uHover * 0.075 + uEnergy * 0.095));",
        "    vec3 interiorCol = mix(uPrimaryColor, uSecondaryColor,",
        "        clamp(0.16 + uVariation * 0.54 + interiorShimmer * 0.16, 0.0, 1.0));",
        "    interiorCol = boostSaturation(interiorCol, 1.18);",
        "",
        "    float n1 = sin((vUv.x * 2.3 + vUv.y * 1.7) * 3.14159 + uAurora * 0.54 + uVariation * 4.0);",
        "    float n2 = sin((vUv.x * 1.1 - vUv.y * 2.2) * 3.14159 - uAurora * 0.53);",
        "    float auroraMask = smoothstep(0.25, 1.0, 0.5 + 0.5 * n1 * n2);",
        "    vec3 auroraCol = mix(uSecondaryColor, uPrimaryColor, 0.5 + 0.24 * n2);",
        "    auroraCol = boostSaturation(auroraCol, 1.12);",
        "    float auroraAlpha = inside * auroraMask * (0.024 + uHover * 0.052 + uEnergy * 0.070);",
        "",
        "    float pd = length(p - uPointer);",
        "    float sheen = exp(-pd / (uRes.y * 0.5)) * uHover;",
        "    float sheenAlpha = inside * sheen * (0.030 + auroraMask * 0.030);",
        "",
        "    float alpha = clamp(borderAlpha + interiorAlpha + auroraAlpha + sheenAlpha, 0.0, 0.86);",
        "    vec3 col = mix(auroraCol, interiorCol, clamp(interiorAlpha * 5.2, 0.0, 0.52));",
        "    col = mix(col, streamColor, clamp(borderAlpha * 2.6, 0.0, 1.0));",
        "    col = mix(col, uHighlightColor, clamp(sheenAlpha * 4.0, 0.0, 0.22));",
        "",
        "    gl_FragColor = vec4(col * alpha, alpha);",
        "}"
    ].join("\n");

    // 色板来自四段背景视频本身：暮霞、山湖、雪林和晨光草甸。
    // 使用中等偏高饱和 RGB，并限制在场景邻近色内，增强辨识度但不回到彩虹霓虹效果。
    var SCENE_PALETTES = [
        { primary: [0.86, 0.42, 0.56], secondary: [0.35, 0.50, 0.78], highlight: [0.96, 0.65, 0.48] },
        { primary: [0.85, 0.32, 0.16], secondary: [0.40, 0.55, 0.22], highlight: [0.96, 0.63, 0.28] },
        { primary: [0.31, 0.53, 0.70], secondary: [0.55, 0.76, 0.82], highlight: [0.92, 0.96, 0.97] },
        { primary: [0.71, 0.58, 0.22], secondary: [0.29, 0.53, 0.34], highlight: [0.90, 0.70, 0.31] }
    ];
    var CARD_VARIATIONS = [0.08, 0.24, 0.42, 0.62, 0.78, 0.34, 0.54, 0.70];

    var cards = Array.prototype.slice.call(document.querySelectorAll(".service-card"));
    if (!cards.length) {
        return;
    }

    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        return;
    }

    var probe = document.createElement("canvas");
    var probeGl = null;
    try {
        probeGl = probe.getContext("webgl") || probe.getContext("experimental-webgl");
    } catch (err) {
        probeGl = null;
    }
    if (!probeGl) {
        return;
    }

    function compileShader(gl, type, source) {
        var shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            gl.deleteShader(shader);
            return null;
        }
        return shader;
    }

    function createCardRenderer(card, variation) {
        var canvas = document.createElement("canvas");
        canvas.className = "service-canvas";
        canvas.setAttribute("aria-hidden", "true");
        card.appendChild(canvas);

        var attrs = { alpha: true, depth: false, stencil: false, antialias: false, premultipliedAlpha: true };
        var gl = null;
        try {
            gl = canvas.getContext("webgl", attrs) || canvas.getContext("experimental-webgl", attrs);
        } catch (err) {
            gl = null;
        }
        if (!gl) {
            if (canvas.parentNode) {
                canvas.parentNode.removeChild(canvas);
            }
            return null;
        }

        var vertexShader = compileShader(gl, gl.VERTEX_SHADER, FX_VERTEX_SHADER);
        var fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, FX_FRAGMENT_SHADER);
        if (!vertexShader || !fragmentShader) {
            if (canvas.parentNode) {
                canvas.parentNode.removeChild(canvas);
            }
            return null;
        }

        var program = gl.createProgram();
        gl.attachShader(program, vertexShader);
        gl.attachShader(program, fragmentShader);
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            if (canvas.parentNode) {
                canvas.parentNode.removeChild(canvas);
            }
            return null;
        }
        gl.useProgram(program);

        var quadBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, quadBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
        var positionLocation = gl.getAttribLocation(program, "aPos");
        gl.enableVertexAttribArray(positionLocation);
        gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

        var uniforms = {
            res: gl.getUniformLocation(program, "uRes"),
            flow: gl.getUniformLocation(program, "uFlow"),
            aurora: gl.getUniformLocation(program, "uAurora"),
            primaryColor: gl.getUniformLocation(program, "uPrimaryColor"),
            secondaryColor: gl.getUniformLocation(program, "uSecondaryColor"),
            highlightColor: gl.getUniformLocation(program, "uHighlightColor"),
            variation: gl.getUniformLocation(program, "uVariation"),
            hover: gl.getUniformLocation(program, "uHover"),
            energy: gl.getUniformLocation(program, "uEnergy"),
            pointer: gl.getUniformLocation(program, "uPointer"),
            radius: gl.getUniformLocation(program, "uRadius")
        };

        var alive = true;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        var pixelWidth = 0;
        var pixelHeight = 0;

        canvas.addEventListener("webglcontextlost", function (event) {
            event.preventDefault();
            alive = false;
        });

        function readRadius() {
            var radiusCss = parseFloat(window.getComputedStyle(card).borderTopLeftRadius);
            return (radiusCss > 0 ? radiusCss : 17) * dpr;
        }

        function resize() {
            if (!alive) {
                return;
            }
            var rect = card.getBoundingClientRect();
            var nextWidth = Math.max(1, Math.round(rect.width * dpr));
            var nextHeight = Math.max(1, Math.round(rect.height * dpr));
            if (nextWidth === pixelWidth && nextHeight === pixelHeight && canvas.width === nextWidth) {
                return;
            }
            pixelWidth = nextWidth;
            pixelHeight = nextHeight;
            canvas.width = pixelWidth;
            canvas.height = pixelHeight;
            gl.viewport(0, 0, pixelWidth, pixelHeight);
            gl.uniform2f(uniforms.res, pixelWidth, pixelHeight);
            gl.uniform1f(uniforms.radius, readRadius());
        }

        resize();

        return {
            resize: resize,
            markDead: function () {
                alive = false;
            },
            isAlive: function () {
                return alive;
            },
            render: function (state, auroraTime) {
                if (!alive || !pixelWidth || !pixelHeight) {
                    return;
                }
                gl.uniform1f(uniforms.flow, state.flow);
                gl.uniform1f(uniforms.aurora, auroraTime);
                gl.uniform3f(uniforms.primaryColor, state.primary[0], state.primary[1], state.primary[2]);
                gl.uniform3f(uniforms.secondaryColor, state.secondary[0], state.secondary[1], state.secondary[2]);
                gl.uniform3f(uniforms.highlightColor, state.highlight[0], state.highlight[1], state.highlight[2]);
                gl.uniform1f(uniforms.variation, variation);
                gl.uniform1f(uniforms.hover, state.hover);
                gl.uniform1f(uniforms.energy, state.energy);
                gl.uniform2f(
                    uniforms.pointer,
                    (state.pointerX - state.rectWidth / 2) * dpr,
                    (state.rectHeight / 2 - state.pointerY) * dpr
                );
                gl.drawArrays(gl.TRIANGLES, 0, 6);
            }
        };
    }

    function createSpring(stiffness, damping) {
        return {
            x: 0,
            v: 0,
            target: 0,
            k: stiffness,
            c: damping
        };
    }

    function stepSpring(spring, dt) {
        var acceleration = -spring.k * (spring.x - spring.target) - spring.c * spring.v;
        spring.v += acceleration * dt;
        spring.x += spring.v * dt;
    }

    var states = [];
    var renderers = [];
    var failed = false;
    var initialScene = Number(document.body.getAttribute("data-scene-theme"));
    var initialPalette = SCENE_PALETTES[initialScene] || SCENE_PALETTES[0];

    for (var i = 0; i < cards.length; i++) {
        var variation = CARD_VARIATIONS[i % CARD_VARIATIONS.length];
        var renderer = createCardRenderer(cards[i], variation);
        if (!renderer) {
            failed = true;
            break;
        }
        renderers.push(renderer);
        states.push({
            el: cards[i],
            renderer: renderer,
            lift: createSpring(165, 16),
            squash: createSpring(205, 12),
            hoverTarget: 0,
            hovered: false,
            focused: false,
            hover: 0,
            energy: 0,
            flow: Math.random() * 40,
            phase: i * 0.85,
            pointerX: 0,
            pointerY: 0,
            rectWidth: 0,
            rectHeight: 0,
            primary: initialPalette.primary.slice(),
            secondary: initialPalette.secondary.slice(),
            highlight: initialPalette.highlight.slice(),
            targetPrimary: initialPalette.primary.slice(),
            targetSecondary: initialPalette.secondary.slice(),
            targetHighlight: initialPalette.highlight.slice()
        });
    }

    if (failed) {
        renderers.forEach(function (renderer) {
            renderer.markDead();
        });
        Array.prototype.forEach.call(document.querySelectorAll(".service-canvas"), function (canvas) {
            if (canvas.parentNode) {
                canvas.parentNode.removeChild(canvas);
            }
        });
        return;
    }

    var rafId = 0;
    var running = false;
    var started = false;
    var lastNow = performance.now();
    var auroraTime = Math.random() * 30;

    function approachColor(current, target, amount) {
        for (var channel = 0; channel < 3; channel++) {
            current[channel] += (target[channel] - current[channel]) * amount;
        }
    }

    function setScenePalette(sceneIndex) {
        var palette = SCENE_PALETTES[sceneIndex] || SCENE_PALETTES[0];
        states.forEach(function (state) {
            state.targetPrimary = palette.primary.slice();
            state.targetSecondary = palette.secondary.slice();
            state.targetHighlight = palette.highlight.slice();
        });
    }

    window.addEventListener("xixiscenechange", function (event) {
        var detail = event.detail || {};
        setScenePalette(Number(detail.sceneIndex));
    });

    function syncHover(state) {
        state.hoverTarget = state.hovered || state.focused ? 1 : 0;
    }

    states.forEach(function (state) {
        var el = state.el;

        el.addEventListener("pointerenter", function () {
            var rect = el.getBoundingClientRect();
            state.rectWidth = rect.width;
            state.rectHeight = rect.height;
            state.hovered = true;
            syncHover(state);
            state.squash.v -= 1.5;
        });

        el.addEventListener("pointermove", function (event) {
            var rect = el.getBoundingClientRect();
            state.rectWidth = rect.width;
            state.rectHeight = rect.height;
            state.pointerX = event.clientX - rect.left;
            state.pointerY = event.clientY - rect.top;
        });

        el.addEventListener("pointerleave", function () {
            state.hovered = false;
            syncHover(state);
        });

        el.addEventListener("pointerdown", function () {
            state.squash.v -= 2.4;
            state.energy = Math.min(state.energy + 0.7, 1.0);
        });

        el.addEventListener("focusin", function () {
            state.focused = true;
            syncHover(state);
        });

        el.addEventListener("focusout", function () {
            state.focused = false;
            syncHover(state);
        });

        el.addEventListener("servicestate", function (event) {
            var detail = event.detail || {};
            if (detail.state === "online") {
                state.lift.v -= 3.2;
                state.energy = Math.min(state.energy + 0.55, 1.0);
            } else if (detail.state === "offline") {
                state.lift.v += 1.1;
            }
        });
    });

    function frame(now) {
        rafId = requestAnimationFrame(frame);
        var dt = Math.min((now - lastNow) / 1000, 0.05);
        lastNow = now;
        auroraTime += dt;

        for (var index = 0; index < states.length; index++) {
            var state = states[index];

            state.hover += (state.hoverTarget - state.hover) * Math.min(1, dt * 9);
            state.energy *= Math.exp(-dt * 2.6);
            var paletteEase = 1 - Math.exp(-dt * 3.4);
            approachColor(state.primary, state.targetPrimary, paletteEase);
            approachColor(state.secondary, state.targetSecondary, paletteEase);
            approachColor(state.highlight, state.targetHighlight, paletteEase);

            var breathe = Math.sin(now * 0.0011 + state.phase) * 0.72
                + Math.sin(now * 0.00047 + state.phase * 1.7) * 0.32;
            state.lift.target = breathe - state.hover * 3.2;
            stepSpring(state.lift, dt);
            stepSpring(state.squash, dt);

            var scaleX = 1 + state.squash.x * 0.26;
            var scaleY = 1 - state.squash.x * 0.36;
            state.el.style.transform = "translateY(" + state.lift.x.toFixed(2)
                + "px) scale(" + scaleX.toFixed(4) + ", " + scaleY.toFixed(4) + ")";

            state.flow += dt * (0.38 + state.hover * 0.62 + state.energy * 1.45);

            if (state.renderer.isAlive()) {
                state.renderer.render(state, auroraTime);
            }
        }
    }

    function stopLoop() {
        if (!running) {
            return;
        }
        running = false;
        cancelAnimationFrame(rafId);
    }

    function startLoop() {
        if (running) {
            return;
        }
        running = true;
        lastNow = performance.now();
        rafId = requestAnimationFrame(frame);
    }

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            stopLoop();
        } else if (started) {
            startLoop();
        }
    });

    if (typeof window.ResizeObserver === "function") {
        var resizeObserver = new ResizeObserver(function () {
            states.forEach(function (state) {
                state.renderer.resize();
            });
        });
        states.forEach(function (state) {
            resizeObserver.observe(state.el);
        });
    } else {
        window.addEventListener("resize", function () {
            states.forEach(function (state) {
                state.renderer.resize();
            });
        });
    }

    function startFx() {
        if (started) {
            return;
        }
        started = true;
        document.body.classList.add("service-fx-on");
        startLoop();
    }

    window.__xixiStartServiceFx = startFx;

    if (typeof window.gsap === "undefined") {
        startFx();
    } else {
        window.setTimeout(startFx, 4000);
    }
}

function setupMotion() {
    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || typeof window.gsap === "undefined") {
        return;
    }

    var heroCopy = document.querySelector(".hero-copy");
    var dock = document.querySelector(".service-dock");
    if (!heroCopy || !dock) {
        return;
    }

    var badge = document.querySelector(".hero-badge");
    var title = document.querySelector("#hero-title");
    var statement = document.querySelector(".hero-statement");
    var switcher = document.querySelector(".scene-switcher");
    var cards = Array.prototype.slice.call(document.querySelectorAll(".service-card"));

    gsap.set(heroCopy, { autoAlpha: 0, y: 26 });
    gsap.set(dock, { autoAlpha: 0, y: 30 });

    var tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    tl.to(heroCopy, { autoAlpha: 1, y: 0, duration: 0.9, delay: 0.15 })
        .fromTo(badge, { y: -14, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.6 }, "-=0.6")
        .fromTo(title, { y: 42, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.9 }, "-=0.45")
        .fromTo(statement, { y: 24, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.7 }, "-=0.55")
        .fromTo(switcher, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.7 }, "-=0.5")
        .fromTo(cards, { y: 24, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.6, stagger: 0.05 }, "-=0.4")
        .to(dock, { autoAlpha: 1, y: 0, duration: 0.6 }, "<")
        .eventCallback("onComplete", function () {
            gsap.set([heroCopy, badge, title, statement, switcher, dock].concat(cards), {
                clearProps: "transform"
            });
            if (typeof window.__xixiStartServiceFx === "function") {
                window.__xixiStartServiceFx();
            }
        });

    window.__xixiSceneCrossfade = function () {
        gsap.fromTo(heroCopy, { autoAlpha: 0.14, y: -10 }, { autoAlpha: 1, y: 0, duration: 0.55, ease: "power2.out" });
    };
}

document.addEventListener("DOMContentLoaded", function () {
    setupHeroVideo();
    setupVideoSwitcher();
    setupAuth();
    setupServiceHealth();
    setupMotion();
    setupServiceFx();
});
