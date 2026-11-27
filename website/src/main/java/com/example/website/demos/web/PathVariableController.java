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

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.ResponseBody;

/**
 * 路径变量绑定的示例控制器。
 *
 * <p>属于 {@code demos} 示例包，只演示 {@code @PathVariable} 与“路径变量内嵌正则约束”两种写法，
 * 不是站点业务接口。</p>
 *
 * <p>第二个映射的路径片段被限制为 {@code [a-z-]+}：含大写字母、数字或下划线时不会匹配该处理器，
 * 请求会直接得到 404，可用于对比“路径不匹配”和“参数校验失败”的区别。</p>
 */
@Controller
public class PathVariableController {

    // http://127.0.0.1:8080/user/123/roles/222
    /**
     * 演示从两层路径中分别取值。
     *
     * @param userId 路径变量 {@code userId}，按字符串接收，不做数字校验
     * @param roleId 路径变量 {@code roleId}，按字符串接收
     * @return 拼好的纯文本，用于确认绑定结果
     */
    @RequestMapping(value = "/user/{userId}/roles/{roleId}", method = RequestMethod.GET)
    @ResponseBody
    public String getLogin(@PathVariable("userId") String userId, @PathVariable("roleId") String roleId) {
        return "User Id : " + userId + " Role Id : " + roleId;
    }

    // http://127.0.0.1:8080/javabeat/somewords
    /**
     * 演示用正则约束路径片段。
     *
     * @param regexp1 已由 {@code [a-z-]+} 约束的小写片段；大写、数字等字符会使请求不匹配而返回 404
     * @return 回显该路径片段
     */
    @RequestMapping(value = "/javabeat/{regexp1:[a-z-]+}", method = RequestMethod.GET)
    @ResponseBody
    public String getRegExp(@PathVariable("regexp1") String regexp1) {
        return "URI Part : " + regexp1;
    }
}
