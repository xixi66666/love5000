package com.example.website.prompt.library.dto;

/**
 * {@code GET /api/prompts} 的查询参数绑定对象，由 Spring MVC 按参数名回填。
 *
 * <p>五个文本条件互不影响、可任意组合；{@code page} 与 {@code size} 的初始值 1/48 是接口默认分页，
 * 但真正的越界纠正发生在 {@code PromptLibraryServiceImpl#search}：页码小于 1 归 1，
 * 每页条数限制在 1 到 100 之间，因此本类只提供声明式默认值，不做校验。</p>
 *
 * <p>查询串里的通配符会被服务端转义，{@code %}/{@code _}/{@code \} 按字面量匹配，不会被当成 LIKE 通配符。</p>
 */
public class PromptSearchRequest {

    private String keyword;
    private String group;
    private String category;
    private String source;
    private String status;
    /** 页码，从 1 开始；请求未提供时取默认值 1。 */
    private int page = 1;
    /** 每页条数，默认 48；服务端最终会限制在 1 到 100 之间。 */
    private int size = 48;

    public String getKeyword() {
        return keyword;
    }

    public void setKeyword(String keyword) {
        this.keyword = keyword;
    }

    public String getGroup() {
        return group;
    }

    public void setGroup(String group) {
        this.group = group;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }
}