(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.PromptCategoryGroups = factory();
    }
})(typeof self !== "undefined" ? self : this, function () {
    var GROUPS = [
        {
            name: "开发与技术",
            slug: "development-technology",
            categories: [
                "技术与编程",
                "开发",
                "全栈开发",
                "移动开发",
                "Python",
                "API文档",
                "架构设计",
                "软件测试",
                "数据库管理",
                "云原生",
                "容器技术",
                "系统管理",
                "网络设计"
            ]
        },
        {
            name: "安全与合规",
            slug: "security-compliance",
            categories: [
                "网络安全",
                "信息安全",
                "应用安全",
                "安全运维",
                "漏洞挖掘",
                "渗透测试",
                "数据隐私",
                "合规"
            ]
        },
        {
            name: "AI 与提示词",
            slug: "ai-prompts",
            categories: [
                "AI 与智能体",
                "提示词",
                "超级提示词",
                "deepseek官方",
                "kimi",
                "人工智能"
            ]
        },
        {
            name: "写作与内容",
            slug: "writing-content",
            categories: [
                "文本",
                "创意与写作",
                "创意写作",
                "文学",
                "诗歌创作",
                "创作",
                "编辑",
                "自媒体",
                "小红书",
                "短视频",
                "内容运营",
                "社交媒体"
            ]
        },
        {
            name: "设计与图像",
            slug: "design-image",
            categories: [
                "GPT Image 2",
                "图片",
                "AI绘画",
                "海报",
                "海报与字体",
                "UI 与界面",
                "UI",
                "插画与艺术",
                "摄影与真实感",
                "人像摄影",
                "图表与信息图",
                "对比图",
                "产品与电商",
                "电商",
                "电商运营",
                "电子商务",
                "品牌与 Logo",
                "建筑与空间",
                "场景与叙事",
                "广告创意",
                "角色与人物",
                "食物与烹饪",
                "历史与古典主题"
            ]
        },
        {
            name: "商业与职场",
            slug: "business-workplace",
            categories: [
                "商业",
                "职场",
                "会议纪要",
                "产品管理",
                "产品设计",
                "项目管理",
                "项目",
                "需求管理",
                "采购管理",
                "销售策略",
                "税务规划",
                "精算",
                "效率",
                "Excel"
            ]
        },
        {
            name: "学习与研究",
            slug: "learning-research",
            categories: [
                "学习",
                "学习方法",
                "论文",
                "学术",
                "深度思考",
                "面试"
            ]
        },
        {
            name: "角色与专业身份",
            slug: "roles-personas",
            categories: [
                "角色提示",
                "角色",
                "专业角色"
            ]
        },
        {
            name: "精选与结构化",
            slug: "featured-structured",
            categories: [
                "精选",
                "STRUCTURED",
                "其他用途"
            ]
        },
        {
            name: "其他",
            slug: "other",
            categories: []
        }
    ];

    var groupByCategory = {};
    GROUPS.forEach(function (group) {
        group.categories.forEach(function (category) {
            groupByCategory[category] = group;
        });
    });

    function getGroupForCategory(category) {
        return groupByCategory[category] || GROUPS[GROUPS.length - 1];
    }

    function buildGroupStats(entries, categoryStats) {
        var categoriesByName = {};
        (categoryStats || []).forEach(function (category) {
            categoriesByName[category.name] = {
                name: category.name,
                count: category.count || 0
            };
        });

        (entries || []).forEach(function (entry) {
            var categoryName = entry.category || "未分类";
            if (!categoriesByName[categoryName]) {
                categoriesByName[categoryName] = {
                    name: categoryName,
                    count: 0
                };
            }
        });

        var groupStats = GROUPS.map(function (group) {
            return {
                name: group.name,
                slug: group.slug,
                count: 0,
                categories: []
            };
        });
        var bySlug = {};
        groupStats.forEach(function (group) {
            bySlug[group.slug] = group;
        });

        Object.keys(categoriesByName).forEach(function (categoryName) {
            var category = categoriesByName[categoryName];
            var group = getGroupForCategory(categoryName);
            var target = bySlug[group.slug];
            target.count += category.count;
            target.categories.push({
                name: category.name,
                count: category.count
            });
        });

        groupStats.forEach(function (group) {
            group.categories.sort(function (a, b) {
                return b.count - a.count || a.name.localeCompare(b.name, "zh-Hans-CN");
            });
        });

        return groupStats.filter(function (group) {
            return group.count > 0 || group.categories.length > 0;
        });
    }

    function findGroup(groupStats, slug) {
        for (var i = 0; i < groupStats.length; i++) {
            if (groupStats[i].slug === slug) {
                return groupStats[i];
            }
        }
        return null;
    }

    return {
        GROUPS: GROUPS,
        buildGroupStats: buildGroupStats,
        findGroup: findGroup,
        getGroupForCategory: getGroupForCategory
    };
});
