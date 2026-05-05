package com.example.website.blog.repository;

import com.example.website.blog.model.BlogArticle;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.sql.Timestamp;
import java.util.List;
import java.util.Optional;

@Repository
public class BlogArticleRepository {

    private static final RowMapper<BlogArticle> ARTICLE_ROW_MAPPER = (rs, rowNum) -> {
        BlogArticle article = new BlogArticle();
        article.setId(rs.getLong("id"));
        article.setTitle(rs.getString("title"));
        article.setSlug(rs.getString("slug"));
        article.setSummary(rs.getString("summary"));
        article.setContentHtml(rs.getString("content_html"));
        article.setCategory(rs.getString("category"));
        article.setTags(rs.getString("tags"));
        article.setWordCount(rs.getInt("word_count"));
        article.setReadMinutes(rs.getInt("read_minutes"));
        Timestamp publishedAt = rs.getTimestamp("published_at");
        Timestamp createdAt = rs.getTimestamp("created_at");
        Timestamp updatedAt = rs.getTimestamp("updated_at");
        article.setPublishedAt(publishedAt == null ? null : publishedAt.toLocalDateTime());
        article.setCreatedAt(createdAt == null ? null : createdAt.toLocalDateTime());
        article.setUpdatedAt(updatedAt == null ? null : updatedAt.toLocalDateTime());
        return article;
    };

    private final JdbcTemplate jdbcTemplate;

    public BlogArticleRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void createTableIfAbsent() {
        jdbcTemplate.execute("create table if not exists blog_article (" +
                "id bigint primary key auto_increment," +
                "title varchar(160) not null," +
                "slug varchar(180) not null unique," +
                "summary varchar(500) not null," +
                "content_html text not null," +
                "category varchar(80) not null," +
                "tags varchar(300) not null," +
                "word_count int not null default 0," +
                "read_minutes int not null default 1," +
                "published_at datetime not null," +
                "created_at datetime not null default current_timestamp," +
                "updated_at datetime not null default current_timestamp on update current_timestamp" +
                ") charset=utf8mb4");
    }

    public int count() {
        Integer count = jdbcTemplate.queryForObject("select count(*) from blog_article", Integer.class);
        return count == null ? 0 : count;
    }

    public void saveSeedArticle(String title, String slug, String summary, String contentHtml,
                                String category, String tags, int wordCount, int readMinutes, String publishedAt) {
        jdbcTemplate.update(
                "insert into blog_article(title, slug, summary, content_html, category, tags, word_count, read_minutes, published_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                title, slug, summary, contentHtml, category, tags, wordCount, readMinutes, publishedAt
        );
    }

    public Long saveArticle(String title, String slug, String summary, String contentHtml,
                            String category, String tags, int wordCount, int readMinutes) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement(
                    "insert into blog_article(title, slug, summary, content_html, category, tags, word_count, read_minutes, published_at) values (?, ?, ?, ?, ?, ?, ?, ?, now())",
                    Statement.RETURN_GENERATED_KEYS
            );
            statement.setString(1, title);
            statement.setString(2, slug);
            statement.setString(3, summary);
            statement.setString(4, contentHtml);
            statement.setString(5, category);
            statement.setString(6, tags);
            statement.setInt(7, wordCount);
            statement.setInt(8, readMinutes);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        return key == null ? null : key.longValue();
    }

    public List<BlogArticle> findPublished(String keyword, String category, String tag) {
        String normalizedKeyword = keyword == null ? "" : keyword.trim();
        String normalizedCategory = category == null ? "" : category.trim();
        String normalizedTag = tag == null ? "" : tag.trim();
        String likeKeyword = "%" + normalizedKeyword + "%";
        String likeTag = "%" + normalizedTag + "%";
        return jdbcTemplate.query(
                "select id, title, slug, summary, content_html, category, tags, word_count, read_minutes, published_at, created_at, updated_at " +
                        "from blog_article where (? = '' or title like ? or summary like ? or category like ? or tags like ?) " +
                        "and (? = '' or category = ?) and (? = '' or tags like ?) order by published_at desc, id desc",
                ARTICLE_ROW_MAPPER,
                normalizedKeyword, likeKeyword, likeKeyword, likeKeyword, likeKeyword,
                normalizedCategory, normalizedCategory,
                normalizedTag, likeTag
        );
    }

    public Optional<BlogArticle> findBySlug(String slug) {
        List<BlogArticle> articles = jdbcTemplate.query(
                "select id, title, slug, summary, content_html, category, tags, word_count, read_minutes, published_at, created_at, updated_at " +
                        "from blog_article where slug = ?",
                ARTICLE_ROW_MAPPER,
                slug
        );
        return articles.stream().findFirst();
    }

    public List<String> findCategories() {
        return jdbcTemplate.queryForList(
                "select distinct category from blog_article order by category",
                String.class
        );
    }

    public List<String> findTagValues() {
        return jdbcTemplate.queryForList("select tags from blog_article", String.class);
    }
}
