package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.TemplateFunctionClassification;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Component
public class TemplateFunctionClassifier {

    private static final List<CategoryDefinition> CATALOG = buildCatalog();

    private static final Map<String, TemplateFunctionClassification> CLASSIFICATIONS =
            buildClassificationIndex(CATALOG);

    private static final Map<String, String> ID_OVERRIDES = buildIdOverrides();

    private static final List<Rule> HIGH_TITLE_RULES = buildHighTitleRules();

    private static final List<Rule> METADATA_RULES = buildMetadataRules();

    private static final List<Rule> GENERAL_TITLE_RULES = buildGeneralTitleRules();

    private static final List<String> IMAGE_SOURCE_IDS = Arrays.asList(
            "youmind-awesome-gpt-image-2",
            "freestylefly-awesome-gpt-image-2",
            "evolink-awesome-gpt-image-2-prompts");

    public List<CategoryDefinition> getCatalog() {
        return CATALOG;
    }

    public TemplateFunctionClassification classify(ImagePromptTemplate template) {
        if (template == null) {
            return classification("other-tools", "general-prompt");
        }

        String override = ID_OVERRIDES.get(normalize(template.getId()));
        if (override != null) {
            return classification(override);
        }

        String title = normalize(template.getTitle());
        TemplateFunctionClassification result = match(HIGH_TITLE_RULES, title);
        if (result != null) {
            return result;
        }

        String metadata = normalize(joinMetadata(template));
        result = match(METADATA_RULES, metadata);
        if (result != null) {
            return result;
        }

        result = match(GENERAL_TITLE_RULES, title);
        if (result != null) {
            return result;
        }

        if (IMAGE_SOURCE_IDS.contains(normalize(template.getSourceId()))) {
            return classification("visual-design-images", "illustration-art");
        }
        return classification("other-tools", "general-prompt");
    }

    private TemplateFunctionClassification match(List<Rule> rules, String text) {
        if (text.isEmpty()) {
            return null;
        }
        for (Rule rule : rules) {
            if (rule.matches(text)) {
                return classification(rule.categorySlug, rule.sceneSlug);
            }
        }
        return null;
    }

    private String joinMetadata(ImagePromptTemplate template) {
        StringBuilder text = new StringBuilder();
        append(text, template.getCategory());
        if (template.getTags() != null) {
            for (String tag : template.getTags()) {
                append(text, tag);
            }
        }
        return text.toString();
    }

    private void append(StringBuilder text, String value) {
        if (value != null && !value.trim().isEmpty()) {
            text.append(' ').append(value);
        }
    }

    private TemplateFunctionClassification classification(String path) {
        String[] parts = path.split("/", 2);
        return classification(parts[0], parts[1]);
    }

    private TemplateFunctionClassification classification(String categorySlug,
                                                          String sceneSlug) {
        TemplateFunctionClassification value =
                CLASSIFICATIONS.get(categorySlug + "/" + sceneSlug);
        if (value == null) {
            throw new IllegalStateException("Unknown function classification: "
                    + categorySlug + "/" + sceneSlug);
        }
        return value;
    }

    private static List<CategoryDefinition> buildCatalog() {
        List<CategoryDefinition> categories = new ArrayList<CategoryDefinition>();
        categories.add(category("写作与内容", "writing-content",
                scene("文案写作", "copywriting"),
                scene("文章长文", "long-form"),
                scene("创意文学", "creative-literature"),
                scene("改写润色", "rewriting-polish"),
                scene("翻译语言", "translation-language"),
                scene("摘要提炼", "summary")));
        categories.add(category("社交媒体与自媒体", "social-media",
                scene("小红书", "xiaohongshu"),
                scene("公众号", "wechat-official"),
                scene("短视频口播", "short-video-script"),
                scene("社交帖子", "social-post"),
                scene("直播带货", "live-commerce"),
                scene("内容运营", "content-operations")));
        categories.add(category("商业营销", "business-marketing",
                scene("营销策划", "marketing-strategy"),
                scene("广告创意", "advertising"),
                scene("销售转化", "sales-conversion"),
                scene("品牌策略", "brand-strategy"),
                scene("电商运营", "ecommerce-operations"),
                scene("SEO", "seo")));
        categories.add(category("视觉设计与图片", "visual-design-images",
                scene("海报排版", "poster-layout"),
                scene("Logo 与品牌视觉", "logo-brand-visual"),
                scene("UI 界面", "ui-interface"),
                scene("信息图表", "infographic"),
                scene("插画艺术", "illustration-art"),
                scene("3D 视觉", "3d-visual"),
                scene("图片编辑与修复", "image-editing")));
        categories.add(category("摄影与人物", "photography-people",
                scene("人像写真", "portrait"),
                scene("产品摄影", "product-photography"),
                scene("风景旅行", "landscape-travel"),
                scene("美食摄影", "food-photography"),
                scene("时尚造型", "fashion-styling"),
                scene("真实感摄影", "photorealistic")));
        categories.add(category("视频与叙事", "video-storytelling",
                scene("分镜脚本", "storyboard"),
                scene("影视场景", "cinematic-scene"),
                scene("动漫角色", "anime-character"),
                scene("视频制作", "video-production"),
                scene("故事叙事", "story-narrative")));
        categories.add(category("编程与技术开发", "programming-development",
                scene("代码生成", "code-generation"),
                scene("代码解释与重构", "code-refactoring"),
                scene("Bug 排查与调试", "debugging"),
                scene("软件测试", "software-testing"),
                scene("前端开发", "frontend-development"),
                scene("后端开发", "backend-development"),
                scene("移动端开发", "mobile-development"),
                scene("全栈开发", "fullstack-development"),
                scene("架构与系统设计", "architecture"),
                scene("API 与数据库", "api-database"),
                scene("DevOps 与云原生", "devops-cloud"),
                scene("网络与信息安全", "cybersecurity"),
                scene("数据处理与自动化脚本", "data-automation")));
        categories.add(category("AI 与自动化", "ai-automation",
                scene("智能体", "agent"),
                scene("提示词工程", "prompt-engineering"),
                scene("模型应用", "model-application"),
                scene("工作流自动化", "workflow-automation")));
        categories.add(category("数据与研究", "data-research",
                scene("数据分析", "data-analysis"),
                scene("学术研究", "academic-research"),
                scene("图表报告", "charts-reports"),
                scene("市场研究", "market-research")));
        categories.add(category("办公与职场", "office-workplace",
                scene("会议纪要", "meeting-notes"),
                scene("报告汇报", "business-report"),
                scene("项目管理", "project-management"),
                scene("效率计划", "productivity-planning"),
                scene("求职面试", "career-interview")));
        categories.add(category("教育与学习", "education-learning",
                scene("知识讲解", "knowledge-explanation"),
                scene("课程教案", "course-lesson"),
                scene("学习方法", "learning-method"),
                scene("题目考试", "exam-practice")));
        categories.add(category("专业咨询", "professional-consulting",
                scene("法律与合规", "legal-compliance"),
                scene("财税与金融", "finance-tax"),
                scene("健康与心理", "health-psychology"),
                scene("企业管理", "business-management"),
                scene("行业专家", "industry-expert")));
        categories.add(category("生活方式", "lifestyle",
                scene("旅行攻略", "travel-guide"),
                scene("美食烹饪", "food-cooking"),
                scene("家居与建筑", "home-architecture"),
                scene("亲子与情感", "family-relationship")));
        categories.add(category("角色与互动", "roles-interaction",
                scene("专业角色", "professional-role"),
                scene("角色扮演", "role-playing"),
                scene("对话陪伴", "conversation-companion"),
                scene("游戏设定", "game-setting")));
        categories.add(category("其他工具", "other-tools",
                scene("通用提示词", "general-prompt")));
        return Collections.unmodifiableList(categories);
    }

    private static Map<String, TemplateFunctionClassification> buildClassificationIndex(
            List<CategoryDefinition> categories) {
        Map<String, TemplateFunctionClassification> index =
                new LinkedHashMap<String, TemplateFunctionClassification>();
        for (CategoryDefinition category : categories) {
            for (SceneDefinition scene : category.getScenes()) {
                String key = category.getSlug() + "/" + scene.getSlug();
                if (index.containsKey(key)) {
                    throw new IllegalStateException("Duplicate function classification: " + key);
                }
                index.put(key, new TemplateFunctionClassification(
                        category.getName(), category.getSlug(),
                        scene.getName(), scene.getSlug()));
            }
        }
        return Collections.unmodifiableMap(index);
    }

    private static Map<String, String> buildIdOverrides() {
        Map<String, String> overrides = new LinkedHashMap<String, String>();
        overrides.put("commerce-product-poster",
                "visual-design-images/poster-layout");
        overrides.put("brand-launch-key-visual",
                "business-marketing/brand-strategy");
        overrides.put("knowledge-card-explainer",
                "visual-design-images/infographic");
        overrides.put("mobile-app-store-screenshot",
                "visual-design-images/ui-interface");
        overrides.put("character-reference-sheet",
                "roles-interaction/game-setting");
        overrides.put("document-report-cover",
                "office-workplace/business-report");
        return Collections.unmodifiableMap(overrides);
    }

    private static List<Rule> buildHighTitleRules() {
        List<Rule> rules = new ArrayList<Rule>();

        rules.add(rule("programming-development", "debugging",
                "bug", "debug", "调试", "排错", "报错", "故障定位", "错误修复"));
        rules.add(rule("programming-development", "software-testing",
                "单元测试", "自动化测试", "软件测试", "测试用例", "test case", "testing"));
        rules.add(rule("programming-development", "frontend-development",
                "react", "vue", "angular", "前端", "html", "css", "浏览器页面"));
        rules.add(rule("programming-development", "backend-development",
                "spring boot", "springboot", "fastapi", "django", "flask", "后端",
                "服务端", "微服务"));
        rules.add(rule("programming-development", "mobile-development",
                "flutter", "android", "ios", "移动端", "移动应用", "小程序开发"));
        rules.add(rule("programming-development", "fullstack-development",
                "全栈", "full stack", "fullstack"));
        rules.add(rule("programming-development", "devops-cloud",
                "devops", "kubernetes", "docker", "云原生", "容器", "ci/cd",
                "持续集成", "运维"));
        rules.add(rule("programming-development", "cybersecurity",
                "网络安全", "信息安全", "渗透测试", "漏洞", "安全审计", "攻防"));
        rules.add(rule("programming-development", "api-database",
                "sql", "数据库", "api", "接口开发", "mysql", "postgresql", "redis"));
        rules.add(rule("programming-development", "architecture",
                "架构设计", "系统设计", "技术方案", "架构师"));
        rules.add(rule("programming-development", "code-refactoring",
                "代码审查", "代码解释", "重构", "code review", "源码分析"));
        rules.add(rule("programming-development", "data-automation",
                "自动化脚本", "爬虫", "数据处理脚本", "python 自动化", "excel 自动化"));
        rules.add(rule("programming-development", "code-generation",
                "代码生成", "编程助手", "程序员", "开发工程师", "写代码",
                "java", "javascript", "typescript", "python", "golang", "c++", "php"));

        rules.add(rule("social-media", "xiaohongshu", "小红书", "xiaohongshu"));
        rules.add(rule("social-media", "wechat-official", "公众号", "微信推文"));
        rules.add(rule("social-media", "short-video-script",
                "短视频", "口播", "抖音", "快手", "视频文案"));
        rules.add(rule("social-media", "live-commerce", "直播带货", "直播话术", "带货"));
        rules.add(rule("social-media", "content-operations",
                "内容运营", "账号运营", "自媒体运营", "选题规划"));
        rules.add(rule("social-media", "social-post",
                "朋友圈", "微博", "社交媒体", "社交帖子"));

        rules.add(rule("visual-design-images", "ui-interface",
                "ui 界面", "ui设计", "界面设计", "网页设计", "app 界面", "仪表盘"));
        rules.add(rule("visual-design-images", "poster-layout",
                "海报", "宣传单", "封面设计", "排版"));
        rules.add(rule("visual-design-images", "logo-brand-visual",
                "logo", "标志设计", "品牌视觉", "vi 设计"));
        rules.add(rule("visual-design-images", "infographic",
                "信息图", "图表", "知识卡片", "流程图", "对比图"));
        rules.add(rule("visual-design-images", "3d-visual",
                "3d", "三维", "立体渲染", "isometric"));
        rules.add(rule("visual-design-images", "image-editing",
                "图片修复", "图像修复", "抠图", "去水印", "换背景", "老照片"));

        rules.add(rule("photography-people", "portrait",
                "人像摄影", "肖像", "写真", "证件照", "头像", "headshot"));
        rules.add(rule("photography-people", "product-photography",
                "产品摄影", "商品摄影", "产品图", "电商图"));
        rules.add(rule("photography-people", "food-photography",
                "美食摄影", "食物摄影", "菜品摄影"));
        rules.add(rule("photography-people", "fashion-styling",
                "时尚摄影", "穿搭", "服装造型", "妆容"));
        rules.add(rule("photography-people", "landscape-travel",
                "风景摄影", "旅行摄影", "城市摄影", "建筑摄影"));

        rules.add(rule("video-storytelling", "storyboard",
                "分镜", "storyboard", "镜头脚本"));
        rules.add(rule("video-storytelling", "video-production",
                "视频制作", "视频剪辑", "影片制作", "短片制作"));
        rules.add(rule("video-storytelling", "anime-character",
                "动漫角色", "动画角色", "二次元角色"));
        rules.add(rule("video-storytelling", "cinematic-scene",
                "电影场景", "影视场景", "电影感", "cinematic"));

        rules.add(rule("office-workplace", "meeting-notes",
                "会议纪要", "会议总结", "会议记录"));
        rules.add(rule("office-workplace", "career-interview",
                "求职", "面试", "简历", "职业规划"));
        rules.add(rule("office-workplace", "project-management",
                "项目管理", "需求管理", "项目计划"));
        rules.add(rule("office-workplace", "business-report",
                "工作汇报", "述职", "报告撰写", "ppt", "汇报材料"));

        rules.add(rule("business-marketing", "seo", "seo", "搜索引擎优化"));
        rules.add(rule("business-marketing", "ecommerce-operations",
                "电商运营", "店铺运营", "商品详情页"));
        rules.add(rule("business-marketing", "advertising",
                "广告创意", "广告语", "广告文案"));
        rules.add(rule("business-marketing", "sales-conversion",
                "销售话术", "成交", "转化率", "客户开发"));
        rules.add(rule("business-marketing", "brand-strategy",
                "品牌策略", "品牌定位", "品牌策划"));
        rules.add(rule("business-marketing", "marketing-strategy",
                "营销策划", "市场营销", "推广方案"));

        rules.add(rule("education-learning", "exam-practice",
                "考试", "试题", "练习题", "题目解析", "测验"));
        rules.add(rule("education-learning", "course-lesson",
                "教案", "课程设计", "教学设计", "备课"));
        rules.add(rule("education-learning", "learning-method",
                "学习方法", "学习计划", "复习计划"));
        rules.add(rule("education-learning", "knowledge-explanation",
                "知识讲解", "概念解释", "科普", "导师"));

        rules.add(rule("data-research", "academic-research",
                "论文", "学术", "文献综述", "研究课题"));
        rules.add(rule("data-research", "market-research",
                "市场调研", "竞品分析", "用户研究", "行业研究"));
        rules.add(rule("data-research", "charts-reports",
                "数据报告", "数据图表", "可视化报告"));
        rules.add(rule("data-research", "data-analysis",
                "数据分析", "统计分析", "数据洞察"));

        rules.add(rule("ai-automation", "prompt-engineering",
                "提示词工程", "prompt 工程", "提示词优化"));
        rules.add(rule("ai-automation", "agent",
                "智能体", "agent", "ai 助手"));
        rules.add(rule("ai-automation", "workflow-automation",
                "工作流自动化", "自动化工作流", "工作流编排"));
        rules.add(rule("ai-automation", "model-application",
                "大模型", "chatgpt", "deepseek", "kimi", "模型应用"));

        return Collections.unmodifiableList(rules);
    }

    private static List<Rule> buildMetadataRules() {
        List<Rule> rules = new ArrayList<Rule>();
        rules.add(rule("programming-development", "cybersecurity",
                "网络安全", "信息安全", "应用安全", "漏洞挖掘", "安全运维"));
        rules.add(rule("programming-development", "devops-cloud",
                "容器技术", "云原生", "系统管理"));
        rules.add(rule("programming-development", "api-database",
                "数据库管理", "api文档"));
        rules.add(rule("programming-development", "architecture",
                "架构设计", "产品设计"));
        rules.add(rule("programming-development", "code-generation",
                "技术与编程", "编程", "开发", "全栈开发", "移动开发"));

        rules.add(rule("visual-design-images", "poster-layout", "海报与字体", "海报"));
        rules.add(rule("visual-design-images", "ui-interface", "ui 与界面", "ui"));
        rules.add(rule("visual-design-images", "infographic", "图表与信息图", "对比图"));
        rules.add(rule("visual-design-images", "logo-brand-visual", "品牌与 logo"));
        rules.add(rule("visual-design-images", "illustration-art",
                "插画与艺术", "ai绘画", "图片生成", "图片"));
        rules.add(rule("photography-people", "portrait", "人像摄影", "人像"));
        rules.add(rule("photography-people", "photorealistic",
                "摄影与真实感", "真实感", "摄影"));
        rules.add(rule("photography-people", "fashion-styling", "时尚"));

        rules.add(rule("social-media", "xiaohongshu", "小红书"));
        rules.add(rule("social-media", "short-video-script", "短视频"));
        rules.add(rule("social-media", "content-operations", "自媒体", "内容运营"));
        rules.add(rule("social-media", "social-post", "社交媒体", "社交"));

        rules.add(rule("business-marketing", "advertising", "广告创意"));
        rules.add(rule("business-marketing", "ecommerce-operations",
                "电商", "电子商务", "电商运营"));
        rules.add(rule("business-marketing", "marketing-strategy",
                "商业", "营销", "商业视觉"));

        rules.add(rule("data-research", "academic-research", "论文", "学术"));
        rules.add(rule("data-research", "data-analysis", "数据分析"));
        rules.add(rule("office-workplace", "meeting-notes", "会议纪要"));
        rules.add(rule("office-workplace", "project-management",
                "项目管理", "需求管理"));
        rules.add(rule("office-workplace", "business-report", "职场", "报告"));
        rules.add(rule("office-workplace", "productivity-planning",
                "效率", "计划"));
        rules.add(rule("education-learning", "learning-method",
                "学习方法", "学习"));
        rules.add(rule("education-learning", "knowledge-explanation", "教育"));

        rules.add(rule("writing-content", "translation-language", "翻译"));
        rules.add(rule("writing-content", "creative-literature",
                "文学", "创意写作", "诗歌创作"));
        rules.add(rule("writing-content", "rewriting-polish", "编辑", "润色"));
        rules.add(rule("writing-content", "copywriting",
                "创作", "写作", "文本", "创意与写作"));

        rules.add(rule("video-storytelling", "anime-character", "动漫角色"));
        rules.add(rule("video-storytelling", "story-narrative",
                "场景与叙事", "叙事", "历史与古典主题"));
        rules.add(rule("roles-interaction", "professional-role",
                "专业角色", "角色提示"));
        rules.add(rule("roles-interaction", "role-playing", "角色扮演", "角色"));

        rules.add(rule("professional-consulting", "legal-compliance",
                "合规", "法律", "数据隐私"));
        rules.add(rule("professional-consulting", "finance-tax",
                "税务", "精算", "金融"));
        rules.add(rule("professional-consulting", "health-psychology",
                "心理健康", "健康"));
        rules.add(rule("professional-consulting", "business-management",
                "采购管理", "企业管理", "产品管理"));

        rules.add(rule("lifestyle", "food-cooking", "食物与烹饪", "美食"));
        rules.add(rule("lifestyle", "travel-guide", "旅行"));
        rules.add(rule("lifestyle", "home-architecture", "建筑与空间", "建筑", "家居"));
        return Collections.unmodifiableList(rules);
    }

    private static List<Rule> buildGeneralTitleRules() {
        List<Rule> rules = new ArrayList<Rule>();
        rules.add(rule("writing-content", "translation-language",
                "翻译", "中英互译", "语言转换"));
        rules.add(rule("writing-content", "summary",
                "总结", "摘要", "提炼", "概括"));
        rules.add(rule("writing-content", "rewriting-polish",
                "改写", "润色", "校对", "扩写", "仿写"));
        rules.add(rule("writing-content", "creative-literature",
                "小说", "诗歌", "故事创作", "散文", "剧本"));
        rules.add(rule("writing-content", "long-form",
                "文章", "长文", "论文写作", "博客"));
        rules.add(rule("writing-content", "copywriting",
                "文案", "标题", "写作", "创作"));

        rules.add(rule("photography-people", "photorealistic",
                "摄影", "真实感", "照片", "镜头"));
        rules.add(rule("visual-design-images", "illustration-art",
                "插画", "艺术风格", "绘画", "图像生成"));
        rules.add(rule("video-storytelling", "story-narrative",
                "叙事", "剧情", "故事"));

        rules.add(rule("office-workplace", "productivity-planning",
                "计划", "效率", "时间管理", "日程"));
        rules.add(rule("professional-consulting", "industry-expert",
                "顾问", "专家", "咨询师"));
        rules.add(rule("roles-interaction", "conversation-companion",
                "陪伴", "聊天", "对话"));
        rules.add(rule("roles-interaction", "game-setting",
                "游戏", "世界观", "角色设定"));
        rules.add(rule("roles-interaction", "professional-role",
                "扮演", "角色"));
        rules.add(rule("lifestyle", "travel-guide", "旅行", "攻略"));
        rules.add(rule("lifestyle", "food-cooking", "菜谱", "烹饪", "美食"));
        rules.add(rule("lifestyle", "home-architecture", "家居", "装修", "建筑"));
        rules.add(rule("lifestyle", "family-relationship", "亲子", "情感", "恋爱"));
        return Collections.unmodifiableList(rules);
    }

    private static CategoryDefinition category(String name,
                                               String slug,
                                               SceneDefinition... scenes) {
        return new CategoryDefinition(name, slug, Arrays.asList(scenes));
    }

    private static SceneDefinition scene(String name, String slug) {
        return new SceneDefinition(name, slug);
    }

    private static Rule rule(String categorySlug,
                             String sceneSlug,
                             String... keywords) {
        return new Rule(categorySlug, sceneSlug, Arrays.asList(keywords));
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    public static final class CategoryDefinition {

        private final String name;

        private final String slug;

        private final List<SceneDefinition> scenes;

        private CategoryDefinition(String name,
                                   String slug,
                                   List<SceneDefinition> scenes) {
            this.name = name;
            this.slug = slug;
            this.scenes = Collections.unmodifiableList(
                    new ArrayList<SceneDefinition>(scenes));
        }

        public String getName() {
            return name;
        }

        public String getSlug() {
            return slug;
        }

        public List<SceneDefinition> getScenes() {
            return scenes;
        }
    }

    public static final class SceneDefinition {

        private final String name;

        private final String slug;

        private SceneDefinition(String name, String slug) {
            this.name = name;
            this.slug = slug;
        }

        public String getName() {
            return name;
        }

        public String getSlug() {
            return slug;
        }
    }

    private static final class Rule {

        private final String categorySlug;

        private final String sceneSlug;

        private final List<String> keywords;

        private Rule(String categorySlug,
                     String sceneSlug,
                     List<String> keywords) {
            this.categorySlug = categorySlug;
            this.sceneSlug = sceneSlug;
            List<String> normalized = new ArrayList<String>();
            for (String keyword : keywords) {
                normalized.add(normalize(keyword));
            }
            this.keywords = Collections.unmodifiableList(normalized);
        }

        private boolean matches(String text) {
            for (String keyword : keywords) {
                if (!keyword.isEmpty() && text.contains(keyword)) {
                    return true;
                }
            }
            return false;
        }
    }
}
