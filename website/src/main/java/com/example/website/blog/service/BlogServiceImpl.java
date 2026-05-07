package com.example.website.blog.service;

import com.example.common.auth.model.AuthUserPrincipal;
import com.example.website.blog.dao.BlogArticleDao;
import com.example.website.blog.dto.BlogArticleCreateRequest;
import com.example.website.blog.dto.BlogArticleResponse;
import com.example.website.blog.model.BlogArticle;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.http.HttpStatus.NOT_FOUND;

@Service
public class BlogServiceImpl implements BlogService {

    private static final Pattern SCRIPT_PATTERN = Pattern.compile("(?is)<script.*?>.*?</script>");

    private static final Pattern SLUG_PATTERN = Pattern.compile("[^a-z0-9-]");

    private final BlogArticleDao blogArticleDao;

    public BlogServiceImpl(BlogArticleDao blogArticleDao) {
        this.blogArticleDao = blogArticleDao;
    }

    @Override
    public List<BlogArticleResponse> listArticles(String keyword, String category, String tag) {
        List<BlogArticle> articles = blogArticleDao.findPublished(
                normalizeFilter(keyword),
                normalizeFilter(category),
                normalizeFilter(tag)
        );
        List<BlogArticleResponse> responses = new ArrayList<BlogArticleResponse>();
        for (BlogArticle article : articles) {
            responses.add(BlogArticleResponse.from(article, false));
        }
        return responses;
    }

    @Override
    public BlogArticleResponse getArticle(String slug) {
        BlogArticle article = requireArticle(blogArticleDao.findBySlug(slug));
        return BlogArticleResponse.from(article, true);
    }

    @Override
    public BlogArticleResponse createArticle(BlogArticleCreateRequest request, AuthUserPrincipal currentUser) {
        validateCreateRequest(request);
        String slug = normalizeSlug(request.getSlug(), request.getTitle());
        if (blogArticleDao.findBySlug(slug) != null) {
            throw new ResponseStatusException(BAD_REQUEST, "Article slug already exists");
        }
        String contentHtml = sanitizeHtml(request.getContentHtml());
        String tags = joinTags(request.getTags());
        int wordCount = calculateWordCount(request.getTitle() + request.getSummary() + contentHtml);
        int readMinutes = Math.max(1, (int) Math.ceil(wordCount / 350.0));
        BlogArticle articleToSave = new BlogArticle();
        articleToSave.setTitle(request.getTitle().trim());
        articleToSave.setSlug(slug);
        articleToSave.setSummary(request.getSummary().trim());
        articleToSave.setContentHtml(contentHtml);
        articleToSave.setCategory(request.getCategory().trim());
        articleToSave.setTags(tags);
        articleToSave.setAuthorId(currentUser.getId());
        articleToSave.setAuthorUsername(currentUser.getUsername());
        articleToSave.setAuthorDisplayName(currentUser.getDisplayName());
        articleToSave.setWordCount(wordCount);
        articleToSave.setReadMinutes(readMinutes);
        blogArticleDao.insert(articleToSave);
        BlogArticle article = requireArticle(blogArticleDao.findBySlug(slug));
        article.setId(articleToSave.getId() == null ? article.getId() : articleToSave.getId());
        return BlogArticleResponse.from(article, true);
    }

    @Override
    public BlogArticleResponse updateArticle(Long id, BlogArticleCreateRequest request, AuthUserPrincipal currentUser) {
        if (id == null) {
            throw new ResponseStatusException(BAD_REQUEST, "Article id is required");
        }
        BlogArticle existing = requireArticle(blogArticleDao.findById(id));
        requireArticleManager(existing, currentUser);
        validateCreateRequest(request);
        String slug = normalizeSlug(request.getSlug(), request.getTitle());
        BlogArticle articleWithSlug = blogArticleDao.findBySlug(slug);
        if (articleWithSlug != null && !articleWithSlug.getId().equals(id)) {
            throw new ResponseStatusException(BAD_REQUEST, "Article slug already exists");
        }
        String contentHtml = sanitizeHtml(request.getContentHtml());
        String tags = joinTags(request.getTags());
        int wordCount = calculateWordCount(request.getTitle() + request.getSummary() + contentHtml);
        int readMinutes = Math.max(1, (int) Math.ceil(wordCount / 350.0));
        BlogArticle articleToUpdate = new BlogArticle();
        articleToUpdate.setId(id);
        articleToUpdate.setTitle(request.getTitle().trim());
        articleToUpdate.setSlug(slug);
        articleToUpdate.setSummary(request.getSummary().trim());
        articleToUpdate.setContentHtml(contentHtml);
        articleToUpdate.setCategory(request.getCategory().trim());
        articleToUpdate.setTags(tags);
        articleToUpdate.setWordCount(wordCount);
        articleToUpdate.setReadMinutes(readMinutes);
        blogArticleDao.updateArticle(articleToUpdate);
        BlogArticle updated = requireArticle(blogArticleDao.findById(id));
        return BlogArticleResponse.from(updated, true);
    }

    @Override
    public void deleteArticle(Long id, AuthUserPrincipal currentUser) {
        if (id == null) {
            throw new ResponseStatusException(BAD_REQUEST, "Article id is required");
        }
        BlogArticle existing = requireArticle(blogArticleDao.findById(id));
        requireArticleManager(existing, currentUser);
        blogArticleDao.deleteById(id);
    }

    @Override
    public List<String> listCategories() {
        return blogArticleDao.findCategories();
    }

    @Override
    public List<String> listTags() {
        Set<String> tags = new LinkedHashSet<String>();
        for (String tagValue : blogArticleDao.findTagValues()) {
            if (tagValue == null || tagValue.trim().isEmpty()) {
                continue;
            }
            String[] parts = tagValue.split(",");
            for (String part : parts) {
                String normalized = part.trim();
                if (!normalized.isEmpty()) {
                    tags.add(normalized);
                }
            }
        }
        return new ArrayList<String>(tags);
    }

    private BlogArticle requireArticle(BlogArticle article) {
        if (article == null) {
            throw new ResponseStatusException(NOT_FOUND, "Blog article not found");
        }
        return article;
    }

    private String normalizeFilter(String value) {
        return value == null ? "" : value.trim();
    }

    private void validateCreateRequest(BlogArticleCreateRequest request) {
        if (request == null) {
            throw new ResponseStatusException(BAD_REQUEST, "Article request is required");
        }
        if (isBlank(request.getTitle()) || request.getTitle().trim().length() > 160) {
            throw new ResponseStatusException(BAD_REQUEST, "Title is required and must be shorter than 160 characters");
        }
        if (isBlank(request.getSummary()) || request.getSummary().trim().length() > 500) {
            throw new ResponseStatusException(BAD_REQUEST, "Summary is required and must be shorter than 500 characters");
        }
        if (isBlank(request.getContentHtml())) {
            throw new ResponseStatusException(BAD_REQUEST, "Content is required");
        }
        if (isBlank(request.getCategory()) || request.getCategory().trim().length() > 80) {
            throw new ResponseStatusException(BAD_REQUEST, "Category is required and must be shorter than 80 characters");
        }
    }

    private void requireArticleManager(BlogArticle article, AuthUserPrincipal currentUser) {
        if (currentUser == null) {
            throw new ResponseStatusException(FORBIDDEN, "Login required");
        }
        if (isAdmin(currentUser)) {
            return;
        }
        if (article.getAuthorId() != null && article.getAuthorId().equals(currentUser.getId())) {
            return;
        }
        throw new ResponseStatusException(FORBIDDEN, "Only the article author or an administrator can manage this article");
    }

    private boolean isAdmin(AuthUserPrincipal currentUser) {
        return currentUser != null && "ADMIN".equalsIgnoreCase(currentUser.getRole());
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private String normalizeSlug(String requestedSlug, String title) {
        String source = isBlank(requestedSlug) ? title : requestedSlug;
        String slug = source.trim().toLowerCase(Locale.ROOT)
                .replaceAll("\\s+", "-")
                .replace("_", "-");
        slug = SLUG_PATTERN.matcher(slug).replaceAll("");
        slug = slug.replaceAll("-+", "-").replaceAll("^-|-$", "");
        if (slug.isEmpty()) {
            slug = "post-" + System.currentTimeMillis();
        }
        return slug.length() > 180 ? slug.substring(0, 180) : slug;
    }

    private String sanitizeHtml(String contentHtml) {
        return SCRIPT_PATTERN.matcher(contentHtml.trim()).replaceAll("");
    }

    private String joinTags(List<String> tags) {
        if (tags == null || tags.isEmpty()) {
            return "";
        }
        Set<String> normalizedTags = new LinkedHashSet<String>();
        for (String tag : tags) {
            if (tag != null && !tag.trim().isEmpty()) {
                normalizedTags.add(tag.trim());
            }
        }
        return String.join(",", normalizedTags);
    }

    private int calculateWordCount(String text) {
        String plainText = text == null ? "" : text.replaceAll("<[^>]+>", "").trim();
        return plainText.length();
    }
}
