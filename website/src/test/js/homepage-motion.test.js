const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scriptPath = path.resolve(__dirname, "../../main/resources/static/js/script.js");
const scriptSource = fs.readFileSync(scriptPath, "utf8");
const animationCalls = [];

const timeline = {
    to(target) {
        animationCalls.push({ method: "to", target });
        return this;
    },
    fromTo(target) {
        animationCalls.push({ method: "fromTo", target });
        return this;
    },
    eventCallback() {
        return this;
    }
};

const gsap = {
    set(target) {
        animationCalls.push({ method: "set", target });
    },
    timeline() {
        return timeline;
    },
    fromTo(target) {
        animationCalls.push({ method: "fromTo", target });
    }
};

const elements = {
    ".hero-copy": { className: "hero-copy" },
    ".service-dock": { className: "service-dock" },
    ".hero-badge": { className: "hero-badge" },
    "#hero-title": { id: "hero-title" },
    ".hero-statement": { className: "hero-statement" },
    ".scene-switcher": { className: "scene-switcher" }
};

const sandbox = {
    console,
    document: {
        addEventListener() {},
        querySelector(selector) {
            return elements[selector] || null;
        },
        querySelectorAll(selector) {
            return selector === ".service-card" ? [{ className: "service-card" }] : [];
        }
    },
    gsap,
    window: {
        gsap,
        matchMedia() {
            return { matches: false };
        }
    }
};

vm.createContext(sandbox);
vm.runInContext(scriptSource, sandbox, { filename: scriptPath });
sandbox.setupMotion();

function containsMissingTarget(target) {
    if (target === null || typeof target === "undefined") {
        return true;
    }
    return Array.isArray(target) && target.some(containsMissingTarget);
}

assert.ok(
    !animationCalls.some((call) => containsMissingTarget(call.target)),
    "删除可选的 .hero-actions 后，setupMotion 不应向 GSAP 传入 null target"
);

console.log("homepage motion optional target test passed");
