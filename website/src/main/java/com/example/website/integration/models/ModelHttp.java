package com.example.website.integration.models;

import com.fasterxml.jackson.databind.ObjectMapper;

/** 固定上游的非流式 JSON 请求；不跟随重定向，不暴露上游错误正文。 */
public class ModelHttp extends com.example.common.ai.ModelHttp {
    public ModelHttp(ObjectMapper json) { super(json); }
}
