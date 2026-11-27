package com.example.imagetemplate.dto;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * prompt 渲染请求体。
 *
 * <p>两个字段都可省略（Controller 的 {@code @RequestBody} 声明为可选）：没有请求体时
 * 按「只使用模板默认值」渲染。渲染规则见
 * {@link com.example.imagetemplate.service.ImagePromptTemplateService#renderPrompt(String, PromptRenderRequest)}。</p>
 */
public class PromptRenderRequest {

    /** 模板变量，key 与 {@code jsonTemplate} 字段同名时覆盖默认值；默认空 LinkedHashMap 保证可写。 */
    private Map<String, Object> variables = new LinkedHashMap<String, Object>();

    /** 追加到最终 prompt 末尾的补充要求；空白视为未填。 */
    private String extraInstruction;

    public Map<String, Object> getVariables() {
        return variables;
    }

    public void setVariables(Map<String, Object> variables) {
        this.variables = variables;
    }

    public String getExtraInstruction() {
        return extraInstruction;
    }

    public void setExtraInstruction(String extraInstruction) {
        this.extraInstruction = extraInstruction;
    }
}

