package com.example.website.blog.controller;

import com.example.common.auth.dto.AuthRequest;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.service.AuthService;
import com.example.website.blog.dto.BlogArticleCreateRequest;
import com.example.website.blog.dto.BlogArticleResponse;
import com.example.website.blog.service.BlogService;
import org.junit.jupiter.api.Test;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;

class BlogControllerTests {

    @Test
    void shouldReturnArticles() {
        BlogController controller = new BlogController(new FakeBlogService(), new FakeAuthService());

        Map<String, Object> response = controller.listArticles(null, null, null);

        assertEquals(true, response.get("success"));
        assertEquals(1, ((List<?>) response.get("articles")).size());
    }

    @Test
    void shouldReturnArticleDetail() {
        BlogController controller = new BlogController(new FakeBlogService(), new FakeAuthService());

        Map<String, Object> response = controller.getArticle("hello-blog");

        BlogArticleResponse article = (BlogArticleResponse) response.get("article");
        assertEquals(true, response.get("success"));
        assertEquals("hello-blog", article.getSlug());
        assertEquals("<p>Hello</p>", article.getContentHtml());
    }

    @Test
    void shouldReturnCategoriesAndTags() {
        BlogController controller = new BlogController(new FakeBlogService(), new FakeAuthService());

        assertEquals(Collections.singletonList("技术教程"), controller.listCategories().get("categories"));
        assertEquals(Arrays.asList("Java", "Spring Boot"), controller.listTags().get("tags"));
    }

    @Test
    void shouldUpdateAndDeleteArticle() {
        BlogController controller = new BlogController(new FakeBlogService(), new FakeAuthService());

        Map<String, Object> updateResponse = controller.updateArticle(1L, new BlogArticleCreateRequest(), null);
        Map<String, Object> deleteResponse = controller.deleteArticle(1L, null);

        assertEquals(true, updateResponse.get("success"));
        assertEquals("Article updated", updateResponse.get("message"));
        assertEquals(true, deleteResponse.get("success"));
        assertEquals("Article deleted", deleteResponse.get("message"));
    }

    private static class FakeBlogService implements BlogService {

        @Override
        public List<BlogArticleResponse> listArticles(String keyword, String category, String tag) {
            BlogArticleResponse article = article(false);
            return Collections.singletonList(article);
        }

        @Override
        public BlogArticleResponse getArticle(String slug) {
            return article(true);
        }

        @Override
        public BlogArticleResponse createArticle(BlogArticleCreateRequest request, AuthUserPrincipal currentUser) {
            return article(true);
        }

        @Override
        public BlogArticleResponse updateArticle(Long id, BlogArticleCreateRequest request, AuthUserPrincipal currentUser) {
            return article(true);
        }

        @Override
        public void deleteArticle(Long id, AuthUserPrincipal currentUser) {
        }

        @Override
        public List<String> listCategories() {
            return Collections.singletonList("技术教程");
        }

        @Override
        public List<String> listTags() {
            return Arrays.asList("Java", "Spring Boot");
        }

        private BlogArticleResponse article(boolean includeContent) {
            BlogArticleResponse response = new BlogArticleResponse();
            response.setId(1L);
            response.setTitle("Hello Blog");
            response.setSlug("hello-blog");
            response.setSummary("Summary");
            response.setCategory("技术教程");
            response.setTags(Arrays.asList("Java", "Spring Boot"));
            response.setWordCount(100);
            response.setReadMinutes(1);
            response.setPublishedAt("2026-05-05 09:00:00");
            if (includeContent) {
                response.setContentHtml("<p>Hello</p>");
            }
            return response;
        }
    }

    private static class FakeAuthService implements AuthService {

        @Override
        public AuthUserPrincipal register(AuthRequest authRequest, HttpServletRequest request) {
            return user();
        }

        @Override
        public AuthUserPrincipal login(AuthRequest authRequest, HttpServletRequest request) {
            return user();
        }

        @Override
        public void logout(HttpServletRequest request, HttpServletResponse response) {
        }

        @Override
        public Optional<AuthUserPrincipal> currentUser(HttpServletRequest request) {
            return Optional.of(user());
        }

        @Override
        public AuthUserPrincipal requireCurrentUser(HttpServletRequest request) {
            return user();
        }

        private AuthUserPrincipal user() {
            AuthUserPrincipal user = new AuthUserPrincipal();
            user.setId(1L);
            user.setUsername("caleb");
            user.setDisplayName("Caleb");
            user.setRole("USER");
            return user;
        }
    }
}
