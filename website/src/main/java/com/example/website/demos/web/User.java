/*
 * Copyright 2013-2018 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.example.website.demos.web;

/**
 * 基础 Web Demo 的示例用户对象。
 *
 * <p>属于 {@code demos} 示例包，仅用于演示 Spring MVC 的表单/查询参数绑定与 JSON 序列化，
 * 不是站点真实的用户模型；真实账户信息由 {@code common} 模块的 {@code AuthUser} 承载。</p>
 *
 * <p>字段刻意保持可变并配有 getter/setter，因为 {@link BasicController} 依赖
 * {@code @ModelAttribute} 与请求参数按属性名回填。</p>
 */
public class User {

    private String name;

    private Integer age;

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public Integer getAge() {
        return age;
    }

    public void setAge(Integer age) {
        this.age = age;
    }
}
