const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function card(name, healthUrl) {
    const classes = new Set();
    return {
        classes,
        getAttribute(key) {
            return { "data-health-service": name, "data-health-url": healthUrl }[key] || null;
        },
        classList: {
            contains(value) { return classes.has(value); },
            toggle(value, enabled) { if (enabled) classes.add(value); else classes.delete(value); }
        },
        querySelector() { return { setAttribute() {} }; },
        dispatchEvent() {}
    };
}

async function main() {
    const skillFinder = card("skill-finder", "http://127.0.0.1:5177/api/health");
    const imageTemplate = card("imagetemplate", "http://localhost:8082/index.html");
    const starting = card("personal-agent", "http://127.0.0.1:5178/api/health");
    starting.classes.add("is-starting");
    const localPage = card(null, "/prompt-console/index.html");
    const calls = [], timers = [];
    const sandbox = {
        console: { log() {} },
        CustomEvent: function () {},
        document: { addEventListener() {}, querySelectorAll() { return [skillFinder, imageTemplate, starting, localPage]; } },
        window: { setInterval(callback, ms) { timers.push({ callback, ms }); } },
        fetch(url) {
            calls.push(url);
            return Promise.resolve({ ok: true, json: () => Promise.resolve({
                success: true, services: [
                    { name: "skill-finder", healthy: true },
                    { name: "imagetemplate", healthy: false },
                    { name: "personal-agent", healthy: false }
                ]
            }) });
        }
    };
    const source = fs.readFileSync(path.resolve(__dirname, "../../main/resources/static/js/script.js"), "utf8");
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    sandbox.setupServiceHealth();
    await new Promise(setImmediate);
    assert.deepStrictEqual(calls.sort(), ["/api/services/health", "/prompt-console/index.html"].sort());
    assert.strictEqual(timers.length, 1);
    assert.strictEqual(timers[0].ms, 1800000);
    assert(skillFinder.classes.has("is-online"));
    assert(imageTemplate.classes.has("is-offline"));
    assert(starting.classes.has("is-starting"));
    assert(!starting.classes.has("is-offline"));
    timers[0].callback();
    await new Promise(setImmediate);
    assert.strictEqual(calls.length, 4, "周期到达后只读统一缓存和本地页面，不直连子项目");

    const localTimers = [];
    vm.runInNewContext(fs.readFileSync(path.resolve(__dirname, "../../main/resources/static/local-services/app.js"), "utf8"), {
        document: { querySelectorAll() { return []; } },
        window: { setInterval(callback, ms) { localTimers.push(ms); } }
    });
    assert.deepStrictEqual(localTimers, [1800000]);
    console.log("service health cache and 30-minute interval tests passed");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
