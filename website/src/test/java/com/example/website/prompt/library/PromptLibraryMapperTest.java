package com.example.website.prompt.library;

import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.mapping.BoundSql;
import org.apache.ibatis.session.Configuration;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class PromptLibraryMapperTest {

    private static final String SEARCH_PAGE =
            "com.example.website.prompt.library.dao.PromptLibraryDao.searchPage";

    @Test
    void searchPageBindsKeywordAndFiltersAsParameters() throws Exception {
        Configuration configuration = parseMapper();

        Map<String, Object> params = new HashMap<String, Object>();
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

    private String normalize(String sql) {
        return sql.replaceAll("\\s+", " ").trim();
    }
}
