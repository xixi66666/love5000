package com.example.website.prompt.library;

import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.mapping.BoundSql;
import org.apache.ibatis.session.Configuration;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 提示词库 MyBatis Mapper 的 SQL 文本测试。
 *
 * <p>用 {@link XMLMapperBuilder} 直接解析 {@code mapper/prompt/PromptLibraryMapper.xml}，
 * 再从 {@link BoundSql} 检查生成的 SQL：关键词匹配是四个
 * {@code like concat('%', ?, '%')} 占位参数，SQL 文本里没有字符串直拼，也不含已转义的关键字
 * 字面量，因此 LIKE 转义由 Service 负责、SQL 侧没有拼接注入面；过滤条件为空时整段 {@code like}
 * 消失，只剩 {@code limit ?, ?} 两个参数；{@code findGroupSlugByCategory} 用参数化分类、
 * 按出现次数降序取第一条，作为新增提示词的大分类归属。</p>
 *
 * <p>隔离：只做 XML 解析与 SQL 文本比对，不建数据源、不连 MySQL、不执行任何语句；
 * 参数个数用 {@code getParameterMappings()} 校验，能发现条件块被漏写或多写。</p>
 */
class PromptLibraryMapperTest {

    private static final String SEARCH_PAGE =
            "com.example.website.prompt.library.dao.PromptLibraryDao.searchPage";

    @Test
    void searchPageBindsKeywordAndFiltersAsParameters() throws Exception {
        Configuration configuration = parseMapper();

        Map<String, Object> params = new HashMap<String, Object>();
        // 已由 Service 转义的关键字：反斜杠、%、_ 都带上了转义符。
        params.put("keyword", "50\\%\\_off\\\\x");
        params.put("group", "writing-content");
        params.put("category", "小红书");
        params.put("source", "manual");
        params.put("status", "imported");
        params.put("offset", 48L);
        params.put("size", 48);

        BoundSql boundSql = configuration.getMappedStatement(SEARCH_PAGE).getBoundSql(params);
        String sql = normalize(boundSql.getSql());

        assertThat(sql)
                .contains("e.title like concat('%', ?, '%')")
                .contains("or e.prompt like concat('%', ?, '%')")
                .contains("or e.tags like concat('%', ?, '%')")
                .contains("or e.category like concat('%', ?, '%')")
                .contains("limit ?, ?")
                .doesNotContain("${")
                .doesNotContain("50\\%");
        assertThat(boundSql.getParameterMappings()).hasSize(10);
    }

    @Test
    void searchPageOmitsBlankFiltersAndKeepsOnlyPaginationParameters() throws Exception {
        Configuration configuration = parseMapper();

        Map<String, Object> params = new HashMap<String, Object>();
        params.put("offset", 0L);
        params.put("size", 48);

        BoundSql boundSql = configuration.getMappedStatement(SEARCH_PAGE).getBoundSql(params);
        String sql = normalize(boundSql.getSql());

        assertThat(sql)
                .doesNotContain("like concat")
                .contains("limit ?, ?");
        assertThat(boundSql.getParameterMappings()).hasSize(2);
    }

    @Test
    void findGroupSlugByCategoryUsesParameterizedCategory() throws Exception {
        Configuration configuration = parseMapper();

        Map<String, Object> params = new HashMap<String, Object>();
        params.put("category", "小红书");

        BoundSql boundSql = configuration
                .getMappedStatement("com.example.website.prompt.library.dao.PromptLibraryDao.findGroupSlugByCategory")
                .getBoundSql(params);
        String sql = normalize(boundSql.getSql());

        assertThat(sql)
                .contains("where category = ?")
                .contains("group by group_slug")
                .contains("order by count(*) desc")
                .contains("limit 1")
                .doesNotContain("${");
        assertThat(boundSql.getParameterMappings()).hasSize(1);
    }

    /**
     * 从 classpath 解析 Mapper XML 到独立的 {@link Configuration}。
     *
     * <p>不构建 SqlSessionFactory、也不注册数据源，因此只验证 SQL 生成，不会真的执行；
     * 资源缺失时先断言失败，报错信息会带上资源路径。</p>
     */
    private Configuration parseMapper() throws Exception {
        Configuration configuration = new Configuration();
        String resource = "mapper/prompt/PromptLibraryMapper.xml";
        try (InputStream input = getClass().getClassLoader().getResourceAsStream(resource)) {
            assertThat(input).as("mapper resource").isNotNull();
            XMLMapperBuilder builder = new XMLMapperBuilder(
                    input, configuration, resource, configuration.getSqlFragments());
            builder.parse();
        }
        return configuration;
    }

    /** 把多行 XML 里的 SQL 压成单行，便于用 contains 断言片段。 */
    private String normalize(String sql) {
        return sql.replaceAll("\\s+", " ").trim();
    }
}
