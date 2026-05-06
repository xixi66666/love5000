package com.example.website.blog.controller;

import com.example.common.auth.annotation.AuthRequired;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.service.AuthService;
import com.example.website.blog.dto.BlogArticleCreateRequest;
import com.example.website.blog.dto.BlogArticleResponse;
import com.example.website.blog.service.BlogService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/blog")
public class BlogController {

    private final BlogService blogService;

    private final AuthService authService;

    public BlogController(BlogService blogService, AuthService authService) {
        this.blogService = blogService;
        this.authService = authService;
    }

    @GetMapping("/articles")
    public Map<String, Object> listArticles(@RequestParam(name = "keyword", required = false) String keyword,
                                            @RequestParam(name = "category", required = false) String category,
                                            @RequestParam(name = "tag", required = false) String tag) {
        List<BlogArticleResponse> articles = blogService.listArticles(keyword, category, tag);
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("articles", articles);
        return response;
    }

    @GetMapping("/articles/{slug}")
    public Map<String, Object> getArticle(@PathVariable String slug) {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("article", blogService.getArticle(slug));
        return response;
    }

    @PostMapping("/articles")
    @AuthRequired
    public Map<String, Object> createArticle(@RequestBody BlogArticleCreateRequest createRequest,
                                             HttpServletRequest request) {
        AuthUserPrincipal currentUser = authService.requireCurrentUser(request);
        BlogArticleResponse article = blogService.createArticle(createRequest, currentUser);
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("message", "Article created");
        response.put("article", article);
        return response;
    }

    @PutMapping("/articles/{id}")
    @AuthRequired
    public Map<String, Object> updateArticle(@PathVariable Long id,
                                             @RequestBody BlogArticleCreateRequest updateRequest,
                                             HttpServletRequest request) {
        AuthUserPrincipal currentUser = authService.requireCurrentUser(request);
        BlogArticleResponse article = blogService.updateArticle(id, updateRequest, currentUser);
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("message", "Article updated");
        response.put("article", article);
        return response;
    }

    @DeleteMapping("/articles/{id}")
    @AuthRequired
    public Map<String, Object> deleteArticle(@PathVariable Long id, HttpServletRequest request) {
        AuthUserPrincipal currentUser = authService.requireCurrentUser(request);
        blogService.deleteArticle(id, currentUser);
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("message", "Article deleted");
        return response;
    }

    @GetMapping("/categories")
    public Map<String, Object> listCategories() {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("categories", blogService.listCategories());
        return response;
    }

    @GetMapping("/tags")
    public Map<String, Object> listTags() {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("tags", blogService.listTags());
        return response;
    }
}
