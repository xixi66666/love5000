package com.example.website.blog.dao;

import com.example.website.blog.model.BlogArticle;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface BlogArticleDao {

    int insert(BlogArticle article);

    List<BlogArticle> findPublished(@Param("keyword") String keyword,
                                    @Param("category") String category,
                                    @Param("tag") String tag);

    BlogArticle findBySlug(@Param("slug") String slug);

    BlogArticle findById(@Param("id") Long id);

    int updateArticle(BlogArticle article);

    int deleteById(@Param("id") Long id);

    List<String> findCategories();

    List<String> findTagValues();
}
