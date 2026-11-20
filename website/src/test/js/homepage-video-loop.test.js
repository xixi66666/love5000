/**
 * 首页四段场景视频靠 JavaScript 补层做交叉循环：原片 10.04 秒首尾不是同一镜头，
 * 原生 loop 会在末尾停帧再跳回第一帧。这里用假 DOM 驱动 setupVideoSwitcher，
 * 锁住"提前 1 秒接管、只接管一次、离开场景要收干净"这三个行为。
 *
 * 运行：node website/src/test/js/homepage-video-loop.test.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scriptPath = path.resolve(__dirname, "../../main/resources/static/js/script.js");
const scriptSource = fs.readFileSync(scriptPath, "utf8");

const FADE_SECONDS = 1;
const DURATION = 10.04;

function classListOf(element) {
    const names = () => (element.className ? element.className.trim().split(/\s+/) : []);

    return {
        add(name) {
            const list = names();
            if (list.indexOf(name) === -1) {
                list.push(name);
                element.className = list.join(" ");
            }
        },
        remove(name) {
            element.className = names().filter((item) => item !== name).join(" ");
        },
        contains(name) {
            return names().indexOf(name) !== -1;
        },
        toggle(name, force) {
            const has = names().indexOf(name) !== -1;
            const next = force === undefined ? !has : Boolean(force);
            if (next === has) {
                return next;
            }
            if (next) {
                element.classList.add(name);
            } else {
                element.classList.remove(name);
            }
            return next;
        }
    };
}

function createElement(tagName) {
    const children = [];
    const attributes = {};
    const listeners = {};

    const element = {
        tagName: tagName.toUpperCase(),
        className: "",
        style: {},
        dataset: {},
        muted: false,
        loop: false,
        paused: true,
        ended: false,
        readyState: 4,
        currentTime: 0,
        // 视频元数据已就绪：四段场景片都是 10.04 秒，与线上一致
        duration: tagName === "video" ? DURATION : 0,
        playCalls: 0,
        pauseCalls: 0,
        parentNode: null,
        play() {
            element.playCalls += 1;
            element.paused = false;
            // 与真实浏览器一致：resolve 时立刻回调，让接管不依赖额外的微任务时序。
            return {
                then(onFulfilled) {
                    if (typeof onFulfilled === "function") {
                        onFulfilled();
                    }
                    return { catch() { return undefined; } };
                }
            };
        },
        pause() {
            element.pauseCalls += 1;
            element.paused = true;
        },
        load() {
            element.currentTime = 0;
            element.ended = false;
        },
        setAttribute(name, value) {
            attributes[name] = String(value);
        },
        getAttribute(name) {
            return Object.prototype.hasOwnProperty.call(attributes, name) ? attributes[name] : null;
        },
        appendChild(child) {
            child.parentNode = element;
            children.push(child);
            return child;
        },
        insertBefore(child, reference) {
            child.parentNode = element;
            const index = reference ? children.indexOf(reference) : -1;
            if (index < 0) {
                children.push(child);
            } else {
                children.splice(index, 0, child);
            }
            return child;
        },
        querySelector(selector) {
            if (selector.charAt(0) === ".") {
                const name = selector.slice(1);
                return children.filter((child) => child.classList.contains(name))[0] || null;
            }
            return children.filter((child) => child.tagName === selector.toUpperCase())[0] || null;
        },
        querySelectorAll() {
            return [];
        },
        addEventListener(type, handler) {
            listeners[type] = listeners[type] || [];
            listeners[type].push(handler);
        },
        dispatch(type) {
            (listeners[type] || []).forEach((handler) => handler({ type }));
        },
        getAnimations() {
            return [];
        }
    };

    Object.defineProperty(element, "classList", { value: classListOf(element) });
    Object.defineProperty(element, "children", { get: () => children.slice() });
    return element;
}

const videos = [];
const buttons = [];
for (let index = 0; index < 4; index += 1) {
    const video = createElement("video");
    video.dataset.sceneVideo = String(index);
    video.duration = DURATION;
    const source = createElement("source");
    source.setAttribute("src", "https://cdn.example/scene-" + index + ".mp4");
    video.appendChild(source);
    videos.push(video);

    const button = createElement("button");
    button.setAttribute("data-scene-index", String(index));
    buttons.push(button);
}

const background = createElement("div");
background.className = "scene-background";
videos.forEach((video) => background.appendChild(video));
const shade = createElement("div");
shade.className = "scene-shade";
background.appendChild(shade);

const timers = [];
let timerId = 0;
function queueTimer(handler, delay, repeat) {
    timerId += 1;
    timers.push({ id: timerId, handler, delay, repeat });
    return timerId;
}

const documentStub = {
    body: createElement("body"),
    querySelectorAll(selector) {
        if (selector === "[data-scene-video]") {
            return videos.slice();
        }
        if (selector === "[data-scene-index]") {
            return buttons.slice();
        }
        return [];
    },
    querySelector(selector) {
        if (selector === ".scene-background") {
            return background;
        }
        if (selector === ".scene-shade") {
            return shade;
        }
        return null;
    },
    createElement(tagName) {
        return createElement(tagName);
    },
    addEventListener() {}
};

const windowStub = {
    setInterval(handler, delay) {
        return queueTimer(handler, delay, true);
    },
    setTimeout(handler, delay) {
        return queueTimer(handler, delay, false);
    },
    clearInterval(id) {
        const timer = timers.filter((item) => item.id === id)[0];
        if (timer) {
            timers.splice(timers.indexOf(timer), 1);
        }
    },
    requestIdleCallback(handler) {
        handler();
    },
    dispatchEvent() {},
    matchMedia() {
        return { matches: false };
    }
};

const sandbox = {
    console,
    document: documentStub,
    window: windowStub,
    CustomEvent: function CustomEvent(type, init) {
        this.type = type;
        this.detail = init && init.detail;
    }
};

vm.createContext(sandbox);
vm.runInContext(scriptSource, sandbox, { filename: scriptPath });
sandbox.setupVideoSwitcher();

function runTick() {
    timers.filter((timer) => timer.repeat).forEach((timer) => timer.handler());
}

function runTimeouts(maxDelay) {
    const due = timers.filter((timer) => !timer.repeat && timer.delay <= maxDelay);
    due.forEach((timer) => {
        const index = timers.indexOf(timer);
        if (index !== -1) {
            timers.splice(index, 1);
        }
    });
    due.forEach((timer) => timer.handler());
}

function loopLayerOf(index) {
    return background.children.filter((child) => child.classList.contains("scene-video--loop"))[index];
}

// 1. 只给当前场景建一层补层，并且压在全部场景视频之上、暗角之下
const layer = loopLayerOf(0);
assert.ok(layer, "首个场景应创建循环补层");
assert.strictEqual(layer.src, "https://cdn.example/scene-0.mp4", "补层必须与原视频同源");
assert.strictEqual(layer.getAttribute("aria-hidden"), "true", "补层不能进入无障碍树");
assert.strictEqual(layer.getAttribute("playsinline"), "", "补层要支持移动端内联播放");
assert.strictEqual(layer.loop, true, "补层保留原生 loop 作为兜底");
assert.strictEqual(layer.paused, true, "补层在接管之前保持暂停");
assert.ok(
    background.children.indexOf(layer) < background.children.indexOf(shade),
    "补层必须排在 .scene-shade 之前，否则会盖住暗角与颗粒"
);
assert.strictEqual(videos[0].paused, false, "首个场景视频应开始播放");
assert.strictEqual(videos[1].paused, true, "非当前场景视频保持暂停");

// 2. 离结尾还远时不能提前接管
videos[0].currentTime = DURATION - FADE_SECONDS - 3;
runTick();
assert.strictEqual(layer.classList.contains("is-loop-visible"), false, "淡入区间之前不得接管");

// 3. 进入淡入区间：补层从第一帧起播并盖在原视频上
//    原视频必须始终保持不透明，否则两层同时半透明时中间会透出背景（“黑一下”）
videos[0].currentTime = DURATION - FADE_SECONDS - 0.1;
runTick();
assert.strictEqual(layer.classList.contains("is-loop-visible"), true, "补层应接管画面");
assert.strictEqual(layer.paused, false, "补层接管时应正在播放");
assert.strictEqual(layer.currentTime, 0, "补层必须从第一帧开始");
assert.strictEqual(videos[0].classList.contains("is-active"), true, "原视频不能被摘掉激活状态");
assert.strictEqual(videos[0].classList.contains("is-loop-hidden"), false, "原视频不能同时淡出");

// 4. 淡出结束后暂停旧层，避免两个 1080p 视频长期同时解码
runTimeouts(1500);
assert.strictEqual(videos[0].paused, true, "旧层淡出后应暂停");
assert.strictEqual(layer.classList.contains("is-loop-visible"), true, "接管后补层保持可见");

// 5. 反方向接管：补层播到淡入区间时把画面交回原视频
videos[0].paused = false;
layer.currentTime = DURATION - FADE_SECONDS - 0.1;
runTick();
assert.strictEqual(layer.classList.contains("is-loop-visible"), false, "补层应退回透明");
assert.strictEqual(videos[0].classList.contains("is-active"), true, "原视频始终保持可见");
assert.strictEqual(videos[0].paused, false);
assert.strictEqual(videos[0].currentTime, 0, "接管方必须从第一帧开始");

// 6. 一次接管只发生一次
const playCalls = videos[0].playCalls;
runTick();
assert.strictEqual(videos[0].playCalls, playCalls, "同一时刻不得重复触发接管");

// 7. 短到放不下两个淡化区间的片段不做交叉淡化
videos[0].duration = 2;
videos[0].currentTime = 1.9;
runTick();
assert.strictEqual(layer.classList.contains("is-loop-visible"), false, "极短片段保持原样");
videos[0].duration = DURATION;

// 8. 切换场景要收干净上一个场景的补层，并给新场景建好补层
buttons[1].dispatch("click");
assert.strictEqual(videos[1].paused, false, "切换后新场景视频开始播放");
runTimeouts(1000);
assert.strictEqual(videos[1].paused, false);
assert.strictEqual(videos[0].paused, true, "上一个场景的视频停止播放");

const layers = background.children.filter((child) => child.classList.contains("scene-video--loop"));
assert.strictEqual(layers.length, 2, "每个访问过的场景各有一层补层");
assert.strictEqual(layers[1].src, "https://cdn.example/scene-1.mp4");
assert.strictEqual(layers[1].paused, true, "新场景的补层在接管之前保持暂停");
assert.strictEqual(layer.classList.contains("is-loop-visible"), false, "旧补层必须退回透明");
assert.strictEqual(videos[0].classList.contains("is-active"), false, "旧场景原视频不再激活");
assert.strictEqual(videos[1].classList.contains("is-active"), true, "新场景原视频应激活");

// 9. 切回原场景后循环依旧生效
buttons[0].dispatch("click");
runTimeouts(1000);
videos[0].currentTime = DURATION - FADE_SECONDS - 0.1;
runTick();
assert.strictEqual(layer.classList.contains("is-loop-visible"), true, "回到原场景后补层应继续接管");

console.log("homepage video loop test passed");
