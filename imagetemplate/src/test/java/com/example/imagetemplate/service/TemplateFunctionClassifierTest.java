package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.TemplateFunctionClassification;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * {@link TemplateFunctionClassifier} 的目录与判定规则测试。
 *
 * <p>锁定三件事：目录固定为 15 个一级功能，顺序稳定且一级 slug 与二级场景 slug 在各自层级
 * 内唯一；标题和标签能命中编程、云原生、安全等二级场景，未知模板回落到
 * {@code other-tools/general-prompt}；标题规则的优先级高于泛化标签，Prompt123 这类噪声标签
 * 若得不到标题印证就不得把模板误判为编程类。专业与职场标题按实际职能归类，歧义标题优先
 * 采用显式任务词。</p>
 *
 * <p>隔离手段：分类器是纯函数，用例只在内存中构造 {@link ImagePromptTemplate}，
 * 不读取模板 JSON、不启动 Spring、不联网。</p>
 */
class TemplateFunctionClassifierTest {

    private TemplateFunctionClassifier classifier;

    @BeforeEach
    void setUp() {
        classifier = new TemplateFunctionClassifier();
    }

    @Test
    void exposesFifteenOrderedCategoriesWithProgrammingVisible() {
        assertThat(classifier.getCatalog()).hasSize(15);
        assertThat(classifier.getCatalog())
                .extracting(TemplateFunctionClassifier.CategoryDefinition::getSlug)
                .contains("programming-development");
        // 一级功能顺序是前端导航与 meta 返回顺序的契约，编程与技术开发固定在第 7 位。
        assertThat(classifier.getCatalog().get(6).getName()).isEqualTo("编程与技术开发");
    }

    @Test
    void catalogUsesStableUniqueCategoryAndSceneSlugs() {
        Set<String> categorySlugs = new HashSet<String>();
        for (TemplateFunctionClassifier.CategoryDefinition category : classifier.getCatalog()) {
            assertThat(category.getName()).isNotBlank();
            assertThat(category.getSlug()).isNotBlank();
            assertThat(categorySlugs.add(category.getSlug())).isTrue();

            Set<String> sceneSlugs = new HashSet<String>();
            assertThat(category.getScenes()).isNotEmpty();
            for (TemplateFunctionClassifier.SceneDefinition scene : category.getScenes()) {
                assertThat(scene.getName()).isNotBlank();
                assertThat(scene.getSlug()).isNotBlank();
                assertThat(sceneSlugs.add(scene.getSlug())).isTrue();
            }
        }
    }

    @Test
    void classifiesProgrammingScenariosFromHighConfidenceTitles() {
        assertClassification("Python 自动化脚本生成器", "文本",
                Arrays.asList("编程"), "programming-development", "data-automation");
        assertClassification("Java Bug 调试专家", "角色提示",
                Arrays.asList("专业角色"), "programming-development", "debugging");
        assertClassification("React 前端页面开发助手", "文本",
                Arrays.asList("UI"), "programming-development", "frontend-development");
        assertClassification("SQL 数据库设计助手", "技术与编程",
                Arrays.asList("数据库"), "programming-development", "api-database");
    }

    @Test
    void coversAdditionalProgrammingScenes() {
        assertClassification("Spring Boot 后端接口开发", "文本",
                Arrays.asList("开发"), "programming-development", "backend-development");
        assertClassification("Flutter 移动应用开发", "文本",
                Arrays.asList("开发"), "programming-development", "mobile-development");
        assertClassification("Kubernetes 云原生部署", "文本",
                Arrays.asList("科技"), "programming-development", "devops-cloud");
        assertClassification("渗透测试与漏洞分析", "网络安全",
                Arrays.asList("安全"), "programming-development", "cybersecurity");
    }

    @Test
    void titleRuleWinsOverGenericTagsAndUnknownTemplatesUseFallback() {
        assertClassification("Spring 后端接口开发", "文本",
                Arrays.asList("写作", "商业"), "programming-development", "backend-development");
        assertClassification("没有可识别用途", "未知",
                Collections.<String>emptyList(), "other-tools", "general-prompt");
    }

    @Test
    void ignoresNoisyPrompt123TagsWhenTheTitleDoesNotCorroborateThem() {
        ImagePromptTemplate template = new ImagePromptTemplate();
        template.setId("prompt123-real-estate");
        template.setSourceId("prompt123");
        template.setTitle("房地产行业");
        template.setCategory("kimi");
        template.setTags(Arrays.asList(
                "Prompt123", "编程", "DeepSeek/Kimi", "kimi"));

        TemplateFunctionClassification classification = classifier.classify(template);

        assertThat(classification.getCategorySlug()).isNotEqualTo(
                "programming-development");
    }

    @Test
    void classifiesCommonProfessionalTitlesByTheirActualFunction() {
        assertClassification("税务会计", "kimi",
                Collections.<String>emptyList(),
                "professional-consulting", "finance-tax");
        assertClassification("法律顾问", "kimi",
                Collections.<String>emptyList(),
                "professional-consulting", "legal-compliance");
        assertClassification("房地产行业", "kimi",
                Collections.<String>emptyList(),
                "professional-consulting", "industry-expert");
        assertClassification("物流运输业", "kimi",
                Collections.<String>emptyList(),
                "professional-consulting", "industry-expert");
        assertClassification("职业导航", "kimi",
                Collections.<String>emptyList(),
                "office-workplace", "career-interview");
        assertClassification("项目经理", "精选",
                Collections.<String>emptyList(),
                "office-workplace", "project-management");
    }

    @Test
    void prioritizesTheExplicitTaskInAmbiguousTitles() {
        assertClassification("逻辑漏洞分析与修补器", "精选",
                Collections.<String>emptyList(),
                "writing-content", "rewriting-polish");
        assertClassification("产品经理", "架构",
                Collections.<String>emptyList(),
                "office-workplace", "project-management");
        assertClassification("YouTube 频道、数据库和配置文件的详细数据分析", "开发",
                Collections.<String>emptyList(),
                "data-research", "data-analysis");
    }

    /**
     * 构造最小模板并断言一级功能与二级场景。
     *
     * <p>只用标题、分类和标签驱动判定；ID 由标题哈希生成，便于断言失败时区分用例。同时检查
     * 展示名非空，防止目录缺名字导致 meta 返回空白导航。</p>
     */
    private void assertClassification(String title,
                                      String category,
                                      List<String> tags,
                                      String categorySlug,
                                      String sceneSlug) {
        ImagePromptTemplate template = new ImagePromptTemplate();
        template.setId("test-" + title.hashCode());
        template.setTitle(title);
        template.setCategory(category);
        template.setTags(tags);

        TemplateFunctionClassification classification = classifier.classify(template);

        assertThat(classification.getCategorySlug()).isEqualTo(categorySlug);
        assertThat(classification.getSceneSlug()).isEqualTo(sceneSlug);
        assertThat(classification.getCategoryName()).isNotBlank();
        assertThat(classification.getSceneName()).isNotBlank();
    }
}
