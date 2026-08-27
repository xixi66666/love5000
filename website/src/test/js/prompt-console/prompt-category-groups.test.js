const assert = require("assert");
const fs = require("fs");
const path = require("path");

const categoryGroups = require("../../../main/resources/static/prompt-console/prompt-category-groups");

const libraryPath = path.resolve(__dirname, "../../../main/resources/static/prompt-console/data/prompt-library.json");
const library = JSON.parse(fs.readFileSync(libraryPath, "utf8"));

function categoryStats(entries) {
    const stats = new Map();
    entries.forEach((entry) => {
        const category = entry.category || "未分类";
        stats.set(category, (stats.get(category) || 0) + 1);
    });
    return Array.from(stats.entries()).map(([name, count]) => ({ name, count }));
}

const stats = categoryStats(library.entries || []);
const groups = categoryGroups.buildGroupStats(library.entries || [], stats);

assert.strictEqual(categoryGroups.getGroupForCategory("技术与编程").name, "开发与技术");
assert.strictEqual(categoryGroups.getGroupForCategory("网络安全").name, "安全与合规");
assert.strictEqual(categoryGroups.getGroupForCategory("GPT Image 2").name, "设计与图像");
assert.strictEqual(categoryGroups.getGroupForCategory("角色提示").name, "角色与专业身份");

const developmentGroup = categoryGroups.findGroup(groups, "development-technology");
assert.ok(developmentGroup, "开发与技术大类应该存在");
assert.ok(developmentGroup.count >= 254, "开发与技术应该包含技术与编程等小类");
assert.ok(
    developmentGroup.categories.some((category) => category.name === "技术与编程" && category.count === 254),
    "开发与技术应该包含技术与编程小类及真实数量"
);

const allGroupedCategories = new Set();
groups.forEach((group) => {
    group.categories.forEach((category) => allGroupedCategories.add(category.name));
});
stats.forEach((category) => {
    assert.ok(allGroupedCategories.has(category.name), `小类 ${category.name} 应该出现在某个大类下`);
});

console.log("prompt category groups tests passed");
