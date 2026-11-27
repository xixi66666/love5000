package com.example.imagetemplate.dto;

import com.example.imagetemplate.model.LibraryAggregationStatus;

import java.util.ArrayList;
import java.util.List;

/**
 * {@code GET /api/image-templates/meta} 的响应体。
 *
 * <p>把聚合结果一次性交给前端：先渲染分类导航与来源筛选，再用 {@code total} 校验分页
 * 总数是否自洽。{@code success} 只有 getter 且初始化为 true —— 该接口不返回失败态，
 * 大库异常通过 {@link LibraryAggregationStatus} 的 {@code status} 与 {@code message} 表达。</p>
 *
 * <p>所有字段都是启动装配时算好的快照，不包含任何模板正文。</p>
 */
public class ImageTemplateMetaResponse {

    /** 恒为 true，便于前端沿用统一的成功标志；本类没有对应的 setter。 */
    private boolean success = true;

    /** 聚合后的模板总数 = curatedCount + libraryCount，正常情况下为 4456。 */
    private int total;

    /** 实际加载的精选模板条数；预期 47，不符时 {@code status.status} 变为 DEGRADED。 */
    private int curatedCount;

    /** 实际可用的 Prompt Console 大库条目数（已剔除缺标题或缺 prompt 的记录），预期 4409。 */
    private int libraryCount;

    /** 图片相关模板条数，对应列表 {@code imageOnly=true} 时的总数。 */
    private int imageRelatedCount;

    /** 聚合状态明细：预期/实际条数、总数与中文告警信息，前端据此显示降级提示。 */
    private LibraryAggregationStatus status;

    /** 来源列表，首项固定为「精选模板」，其余按大库来源顺序排列，count 为实际条数。 */
    private List<TemplateSourceResponse> sources = new ArrayList<TemplateSourceResponse>();

    /** 原始分类（categorySlug）计数，兼容旧筛选维度；与两级功能分类是两套体系。 */
    private List<TemplateCategoryResponse> categories =
            new ArrayList<TemplateCategoryResponse>();

    /** 两级功能树：一级功能带二级场景及各自条数，一级 count 之和等于 total。 */
    private List<TemplateFunctionCategoryResponse> functionCategories =
            new ArrayList<TemplateFunctionCategoryResponse>();

    public boolean isSuccess() {
        return success;
    }

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public int getCuratedCount() {
        return curatedCount;
    }

    public void setCuratedCount(int curatedCount) {
        this.curatedCount = curatedCount;
    }

    public int getLibraryCount() {
        return libraryCount;
    }

    public void setLibraryCount(int libraryCount) {
        this.libraryCount = libraryCount;
    }

    public int getImageRelatedCount() {
        return imageRelatedCount;
    }

    public void setImageRelatedCount(int imageRelatedCount) {
        this.imageRelatedCount = imageRelatedCount;
    }

    public LibraryAggregationStatus getStatus() {
        return status;
    }

    public void setStatus(LibraryAggregationStatus status) {
        this.status = status;
    }

    public List<TemplateSourceResponse> getSources() {
        return sources;
    }

    public void setSources(List<TemplateSourceResponse> sources) {
        this.sources = sources;
    }

    public List<TemplateCategoryResponse> getCategories() {
        return categories;
    }

    public void setCategories(List<TemplateCategoryResponse> categories) {
        this.categories = categories;
    }

    public List<TemplateFunctionCategoryResponse> getFunctionCategories() {
        return functionCategories;
    }

    public void setFunctionCategories(
            List<TemplateFunctionCategoryResponse> functionCategories) {
        this.functionCategories = functionCategories;
    }
}

