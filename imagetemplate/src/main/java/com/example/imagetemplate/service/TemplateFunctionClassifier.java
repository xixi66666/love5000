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

/**
 * 模板功能树判定器：把任意模板归到一个一级功能与一个二级场景。
 *
 * <p>功能树固定为 15 个一级功能（写作、社交媒体、商业营销、视觉设计、摄影、
 * 视频叙事、编程开发、AI 自动化、数据研究、办公职场、教育学习、专业咨询、
 * 生活方式、角色互动、其他工具），其下二级场景由 {@link #getCatalog()} 暴露给前端导航。</p>
 *
 * <p>判定是纯确定性的关键词规则，只读取模板的 ID、标题、原始分类、标签与来源，
 * <b>绝不扫描完整 Prompt</b>——大库 Prompt 动辄上万字，逐条解析会让启动时间和内存不可接受。
 * 优先级自上而下，先命中先返回：</p>
 * <ol>
 *   <li>{@link #ID_OVERRIDES}：少数精选模板的标题含义模糊，用 ID 直接钉死分类；</li>
 *   <li>{@link #HIGH_TITLE_RULES}：强特征标题词，例如“调试”“小红书”“分镜”；</li>
 *   <li>{@link #METADATA_RULES}：分类与标签的弱特征词，例如“技术与编程”“插画与艺术”；</li>
 *   <li>{@link #GENERAL_TITLE_RULES}：泛化标题词，例如“总结”“小说”；</li>
 *   <li>三个图片专用来源兜底为“视觉设计与图片 / 插画艺术”；</li>
 *   <li>全部未命中时归入“其他工具 / 通用提示词”。</li>
 * </ol>
 *
 * <p>规则里的关键词在构造期统一小写，匹配时用子串包含，因此中文无需分词。
 * 目录与规则表都是静态不可变结构；目录里的重复 {@code 一级/二级} 组合在类初始化阶段就会抛错，
 * 规则里写错的 slug 会在该规则首次命中时立刻抛 {@link IllegalStateException}，
 * 聚合启动过程即可暴露问题，不会静默产出空分类。</p>
 */
@Component
public class TemplateFunctionClassifier {

    /** 一级功能与二级场景的完整目录（15 个一级功能，顺序即前端导航顺序）。 */
    private static final List<CategoryDefinition> CATALOG = buildCatalog();

    /** {@code 一级slug/二级slug} 到分类结果的索引，兼作 slug 合法性校验表。 */
    private static final Map<String, TemplateFunctionClassification> CLASSIFICATIONS =
            buildClassificationIndex(CATALOG);

    /** 精选模板的 ID 到 {@code 一级slug/二级slug} 的强制覆盖，优先于所有关键词规则。 */
    private static final Map<String, String> ID_OVERRIDES = buildIdOverrides();

    /** 最高优先级的标题规则：特征是“看到就该归此类”的强词。 */
    private static final List<Rule> HIGH_TITLE_RULES = buildHighTitleRules();

    /** 元数据规则：只在标题规则未命中时，用原始分类与标签做较弱判定。 */
    private static final List<Rule> METADATA_RULES = buildMetadataRules();

    /** 泛化标题规则：最后兜底的低特异性词，避免过早抢占强规则。 */
    private static final List<Rule> GENERAL_TITLE_RULES = buildGeneralTitleRules();

    /** 图片专用来源：标题与元数据都无特征时，这些来源的条目默认归入插画艺术场景。 */
    private static final List<String> IMAGE_SOURCE_IDS = Arrays.asList(
            "youmind-awesome-gpt-image-2",
            "freestylefly-awesome-gpt-image-2",
            "evolink-awesome-gpt-image-2-prompts");

    /**
     * 返回功能树目录。
     *
     * @return 不可变目录，顺序即前端展示顺序
     */
    public List<CategoryDefinition> getCatalog() {
        return CATALOG;
    }

    /**
     * 判定单条模板所属的一级功能与二级场景。
     *
     * <p>按“ID 覆盖 → 强标题 → 元数据 → 泛化标题 → 图片来源兜底 → 其他工具”的顺序匹配，
     * 命中即返回。空模板不会抛异常，直接归入“其他工具 / 通用提示词”，
     * 保证聚合阶段任何异常数据都不会中断启动。</p>
     *
     * @param template 待分类模板，可为 {@code null}
     * @return 非空的分类结果，包含中英文名称与 slug
     */
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

    /**
     * 按顺序尝试一组规则。
     *
     * <p>文本为空时不匹配任何规则（避免空串被 {@code contains} 命中）；
     * 规则表第一个命中即返回，因此插入顺序就是优先级，不要随意重排。</p>
     *
     * @param rules 规则表
     * @param text  已小写的待匹配文本
     * @return 命中的分类；全部未命中返回 {@code null}
     */
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

    /**
     * 拼接用于元数据规则匹配的文本。
     *
     * <p>普通条目由原始分类加全部标签组成。{@code prompt123} 来源的标签噪声较大，
     * 只保留分类，避免宽泛标签把条目误判到无关功能。</p>
     *
     * @param template 模板
     * @return 空格分隔的元数据文本（未归一化）
     */
    private String joinMetadata(ImagePromptTemplate template) {
        StringBuilder text = new StringBuilder();
        append(text, template.getCategory());
        if ("prompt123".equals(normalize(template.getSourceId()))) {
            return text.toString();
        }
        if (template.getTags() != null) {
            for (String tag : template.getTags()) {
                append(text, tag);
            }
        }
        return text.toString();
    }

    /**
     * 追加一个非空白字段到拼接串，前置空格作为分隔。
     *
     * @param text  拼接缓冲
     * @param value 待追加字段，可为 {@code null}
     */
    private void append(StringBuilder text, String value) {
        if (value != null && !value.trim().isEmpty()) {
            text.append(' ').append(value);
        }
    }

    /**
     * 按 {@code 一级slug/二级slug} 取分类结果。
     *
     * <p>只按第一个斜杠切分两段，因此多写斜杠不会被静默忽略：多出的部分会留在第二段，
     * 查表时命中不到并抛错，等于顺带校验了路径格式。</p>
     *
     * @param path 形如 {@code visual-design-images/poster-layout} 的路径
     * @return 分类结果
     * @throws IllegalStateException 路径不在目录中（启动期规则书写错误的信号）
     */
    private TemplateFunctionClassification classification(String path) {
        String[] parts = path.split("/", 2);
        return classification(parts[0], parts[1]);
    }

    /**
     * 按一级与二级 slug 取分类结果。
     *
     * <p>结果来自 {@link #CLASSIFICATIONS}，因此返回对象是共享的不可变实例，
     * 调用方不要修改它。</p>
     *
     * @param categorySlug 一级功能 slug
     * @param sceneSlug    二级场景 slug
     * @return 分类结果
     * @throws IllegalStateException 组合不在目录中
     */
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

    /**
     * 构造 15 个一级功能及其二级场景目录。
     *
     * <p>这里的顺序就是前端导航顺序，也是 {@code /meta} 功能树的输出顺序；
     * 场景 slug 是前端筛选参数，一旦发布就应保持稳定，否则页面保存的筛选条件会失效。
     * 返回列表不可变，避免运行期被修改。</p>
     *
     * @return 不可变目录
     */
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

    /**
     * 由目录生成 {@code 一级slug/二级slug} 到分类结果的索引。
     *
     * <p>重复组合（同一 slug 被两个场景复用）会让筛选结果串味，
     * 因此在类初始化阶段直接抛错。返回索引不可变，分类结果在其中复用，
     * 使 {@link #classify} 不必每次新建对象。</p>
     *
     * @param categories 功能目录
     * @return 不可变索引
     * @throws IllegalStateException 存在重复的 {@code 一级/二级} 组合
     */
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

    /**
     * 精选模板的 ID 级分类覆盖。
     *
     * <p>这些模板的标题偏商业表述（例如“商品海报 / 电商图生成”），关键词规则容易把它们
     * 分散到营销、视觉或摄影多个分类。用 ID 直接钉死可以保证导航计数稳定，
     * 也说明新增精选模板若要固定分类，应该在这里登记而不是放宽规则。</p>
     *
     * @return 不可变的 ID 到 {@code 一级/二级} 路径映射
     */
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

    /**
     * 强特征标题规则表。
     *
     * <p>顺序即优先级，并且刻意让“具体技术栈/具体文体”先于“宽泛领域”：
     * 调试、测试、前端、后端、移动端、DevOps 等编程场景排在通用的“代码生成”之前，
     * 否则任何含“代码”的标题都会落进代码生成。同一条规则内的关键词是“或”关系。</p>
     *
     * @return 不可变规则表
     */
    private static List<Rule> buildHighTitleRules() {
        List<Rule> rules = new ArrayList<Rule>();

        rules.add(rule("writing-content", "rewriting-polish",
                "逻辑漏洞分析", "逻辑漏洞修补"));
        rules.add(rule("office-workplace", "project-management",
                "产品经理", "产品管理"));
        rules.add(rule("data-research", "data-analysis",
                "数据分析", "统计分析", "数据洞察"));

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

        rules.add(rule("professional-consulting", "legal-compliance",
                "法律顾问", "律师", "法务", "法律咨询", "合规顾问"));
        rules.add(rule("professional-consulting", "finance-tax",
                "税务", "会计", "财务", "金融顾问", "投资顾问", "审计师"));
        rules.add(rule("professional-consulting", "health-psychology",
                "心理咨询", "心理健康", "医生", "医疗顾问", "营养师"));
        rules.add(rule("professional-consulting", "business-management",
                "企业管理", "风险管理", "采购管理", "人力资源"));
        rules.add(rule("professional-consulting", "industry-expert",
                "房地产行业", "物流运输", "供应链", "行业顾问", "行业专家"));
        rules.add(rule("office-workplace", "career-interview",
                "职业导航", "职业顾问", "职业发展"));
        rules.add(rule("office-workplace", "project-management",
                "项目经理", "项目管理"));

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

    /**
     * 分类与标签的元数据规则表。
     *
     * <p>大库原始分类名（如“技术与编程”“插画与艺术”“摄影与真实感”）比标题更能代表主题，
     * 但特异性低于强标题词，因此只在标题规则全部未命中时启用。
     * 顺序即优先级，靠前的具体分类优先于靠后的宽泛分类。</p>
     *
     * @return 不可变规则表
     */
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

    /**
     * 泛化标题规则表，只在前两级规则全部未命中时使用。
     *
     * <p>这里的词（如“文章”“计划”“角色”）覆盖面广、特异性低，放在最后可以兜住
     * “标题里只有一个宽泛名词”的条目，又不会抢走更精确的分类。
     * 若某天需要更准确的归属，应把新词加到强标题规则，而不是继续扩充本表。</p>
     *
     * @return 不可变规则表
     */
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

    /**
     * 构造一个一级功能节点。
     *
     * @param name   中文名（前端展示）
     * @param slug   英文 slug（前端筛选参数）
     * @param scenes 二级场景，顺序即展示顺序
     * @return 不可变分类定义
     */
    private static CategoryDefinition category(String name,
                                               String slug,
                                               SceneDefinition... scenes) {
        return new CategoryDefinition(name, slug, Arrays.asList(scenes));
    }

    /**
     * 构造一个二级场景节点。
     *
     * @param name 中文名
     * @param slug 英文 slug
     * @return 场景定义
     */
    private static SceneDefinition scene(String name, String slug) {
        return new SceneDefinition(name, slug);
    }

    /**
     * 构造一条分类规则。
     *
     * <p>关键词在 {@link Rule} 构造期统一小写，因此这里可以按最自然的中英文写法录入。</p>
     *
     * @param categorySlug 目标一级功能 slug
     * @param sceneSlug    目标二级场景 slug
     * @param keywords     触发关键词，任意一个被包含即命中
     * @return 规则实例
     */
    private static Rule rule(String categorySlug,
                             String sceneSlug,
                             String... keywords) {
        return new Rule(categorySlug, sceneSlug, Arrays.asList(keywords));
    }

    /**
     * 归一化待匹配文本：去首尾空白并转小写。
     *
     * <p>规则关键词与模板字段都走同一套归一化，因此匹配不区分大小写；
     * 使用 {@link Locale#ROOT} 避免区域相关的转换差异。{@code null} 归一为空串，
     * 使后续 {@code contains} 不必判空。</p>
     *
     * @param value 原始文本，可为 {@code null}
     * @return 归一化结果；{@code null} 返回空串
     */
    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    /**
     * 一级功能定义。
     *
     * <p>由 {@link #buildCatalog()} 构造后不再变化；{@code slug} 同时是前端筛选参数与
     * 分类索引的键，改名会让已收藏的链接失效。</p>
     */
    public static final class CategoryDefinition {

        /** 中文显示名。 */
        private final String name;

        /** 英文 slug，用于 URL 参数与索引键。 */
        private final String slug;

        /** 该功能下的二级场景，顺序即展示顺序。 */
        private final List<SceneDefinition> scenes;

        /**
         * @param name   中文显示名
         * @param slug   英文 slug
         * @param scenes 二级场景
         */
        private CategoryDefinition(String name,
                                   String slug,
                                   List<SceneDefinition> scenes) {
            this.name = name;
            this.slug = slug;
            this.scenes = Collections.unmodifiableList(
                    new ArrayList<SceneDefinition>(scenes));
        }

        /**
         * @return 中文显示名
         */
        public String getName() {
            return name;
        }

        /**
         * @return 英文 slug
         */
        public String getSlug() {
            return slug;
        }

        /**
         * @return 不可变的二级场景列表
         */
        public List<SceneDefinition> getScenes() {
            return scenes;
        }
    }

    /**
     * 二级场景定义。
     *
     * <p>场景必须挂在一级功能下，前端用它做第二级筛选；同一个场景 slug 不应跨一级功能复用。</p>
     */
    public static final class SceneDefinition {

        /** 中文显示名。 */
        private final String name;

        /** 英文 slug，在同一一级功能内唯一。 */
        private final String slug;

        /**
         * @param name 中文显示名
         * @param slug 英文 slug
         */
        private SceneDefinition(String name, String slug) {
            this.name = name;
            this.slug = slug;
        }

        /**
         * @return 中文显示名
         */
        public String getName() {
            return name;
        }

        /**
         * @return 英文 slug
         */
        public String getSlug() {
            return slug;
        }
    }

    /**
     * 一条分类规则：一组关键词命中任意一个，就把模板归到目标场景。
     *
     * <p>关键词在构造期统一小写，保证与模板文本的归一化方式一致。</p>
     */
    private static final class Rule {

        /** 目标一级功能 slug。 */
        private final String categorySlug;

        /** 目标二级场景 slug。 */
        private final String sceneSlug;

        /** 已小写的触发关键词。 */
        private final List<String> keywords;

        /**
         * @param categorySlug 目标一级功能 slug
         * @param sceneSlug    目标二级场景 slug
         * @param keywords     触发关键词，允许混合中英文
         */
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

        /**
         * 判断文本是否包含任一关键词。
         *
         * <p>空关键词会被忽略，否则空串会被任何文本包含而使规则恒真。</p>
         *
         * @param text 已小写的待匹配文本
         * @return {@code true} 表示命中
         */
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
