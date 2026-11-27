package com.example.imagetemplate.service;

/**
 * 指定 ID 在聚合模板集中不存在时抛出。
 *
 * <p>由 {@link ImagePromptTemplateService#findById(String)} 在详情、渲染和图片生成入口抛出，
 * Controller 将其映射为 HTTP 404 与 {@code success=false}。消息格式固定为英文前缀
 * {@code Image prompt template not found: } 加 ID，测试与前端错误提示依赖该格式。</p>
 */
public class ImagePromptTemplateNotFoundException extends RuntimeException {

    /**
     * 用缺失的模板 ID 构造异常。
     *
     * @param id 未命中的模板 ID，同时作为错误消息的一部分回传
     */
    public ImagePromptTemplateNotFoundException(String id) {
        super("Image prompt template not found: " + id);
    }
}
