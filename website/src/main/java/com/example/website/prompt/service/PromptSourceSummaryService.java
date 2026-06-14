package com.example.website.prompt.service;

import org.springframework.stereotype.Service;

@Service
public class PromptSourceSummaryService {

    public String summarize(String content) {
        if (content == null || content.trim().isEmpty()) {
            return "实时来源没有返回可读内容，已保留内置摘要。";
        }
        String text = content
                .replaceAll("(?is)<script.*?</script>", " ")
                .replaceAll("(?is)<style.*?</style>", " ")
                .replaceAll("(?is)<title[^>]*>", " ")
                .replaceAll("(?is)</title>", " ")
                .replaceAll("(?is)<[^>]+>", " ")
                .replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replaceAll("\\s+", " ")
                .trim();
        if (text.length() > 180) {
            return text.substring(0, 180) + "...";
        }
        return text;
    }
}
