package com.example.website.prompt.library.service;

import com.example.website.prompt.library.dto.PromptCreateRequest;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.dto.PromptSearchRequest;

public interface PromptLibraryService {

    PromptMetaResponse meta();

    PromptListResponse search(PromptSearchRequest request);

    PromptDetailResponse detail(Long id);

    PromptCreateResponse create(PromptCreateRequest request);
}