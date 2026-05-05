package com.example.website.blog.service;

import com.example.common.auth.model.AuthUserPrincipal;
import com.example.website.blog.dto.BlogArticleCreateRequest;
import com.example.website.blog.dto.BlogArticleResponse;

import java.util.List;

public interface BlogService {

    List<BlogArticleResponse> listArticles(String keyword, String category, String tag);

    BlogArticleResponse getArticle(String slug);

    BlogArticleResponse createArticle(BlogArticleCreateRequest request, AuthUserPrincipal currentUser);

    List<String> listCategories();

    List<String> listTags();
}
