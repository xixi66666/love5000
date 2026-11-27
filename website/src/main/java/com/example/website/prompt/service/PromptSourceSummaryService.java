package com.example.website.prompt.service;

import org.springframework.stereotype.Service;

/**
 * 把抓取到的来源页面压成一句可展示的摘要。
 *
 * <p>不调用任何模型：用正则依次删除 {@code script}/{@code style} 整块和其余标签，解码几个常见
 * HTML 实体，把连续空白折叠成单空格，最后按 180 字截断并补省略号。正则带 {@code (?is)}，
 * 可跨行匹配并忽略大小写，因此多行的 {@code <script>} 也能整段删除。</p>
 */
@Service
public class PromptSourceSummaryService {

    /**
     * 生成摘要文本。
     *
     * <p>截断按 {@code char} 计数，若 180 字边界正好落在代理对（如 emoji）中间，摘要末尾可能出现
     * 半个字符；这里不做字符边界修正。</p>
     *
     * @param content 来源页面的原始内容，允许 {@code null}
     * @return 去标签后的摘要；内容为空时返回固定提示语，说明已保留内置摘要
     */
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
