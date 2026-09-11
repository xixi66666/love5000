package com.example.website.prompt.library.dao;

import com.example.website.prompt.library.model.PromptCategoryStat;
import com.example.website.prompt.library.model.PromptEntry;
import com.example.website.prompt.library.model.PromptGroupStat;
import com.example.website.prompt.library.model.PromptSourceStat;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PromptLibraryDao {

    long countAll();

    long countByFilter(@Param("keyword") String keyword,
                       @Param("group") String group,
                       @Param("category") String category,
                       @Param("source") String source,
                       @Param("status") String status);

    List<PromptEntry> searchPage(@Param("keyword") String keyword,
                                 @Param("group") String group,
                                 @Param("category") String category,
                                 @Param("source") String source,
                                 @Param("status") String status,
                                 @Param("offset") int offset,
                                 @Param("size") int size);

    PromptEntry findById(@Param("id") Long id);

    int insert(PromptEntry entry);

    String findGroupSlugByCategory(@Param("category") String category);

    int upsertManualSource();

    List<PromptGroupStat> selectGroupCounts();

    List<PromptCategoryStat> selectCategoryCounts();

    List<PromptSourceStat> selectSourceStats();
}