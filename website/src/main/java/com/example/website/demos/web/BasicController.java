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
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

/**
 * 基础 Spring MVC 示例控制器。
 *
 * <p>属于 {@code demos} 示例包，只演示四种常见写法：查询参数（{@code /hello}）、对象序列化
 * （{@code /user}）、请求参数绑定到对象（{@code /save_user}）和返回视图名（{@code /html}）。
 * 这些路径都不是站点业务接口，接口清单以 {@code /api/**} 下的控制器为准。</p>
 *
 * <p>需要留意 {@link #parseUser}：它标注了 {@code @ModelAttribute}，会在本控制器每次请求前执行，
 * 并把 {@code User} 的 name/age 无条件覆盖为固定值。因此 {@code /save_user} 回显的是
 * {@code zhangsan/18}，而不是请求里传的 {@code name}/{@code age}——这是示例刻意的预填充演示，
 * 不是参数绑定失败。</p>
 */
@Controller
public class BasicController {

    // http://127.0.0.1:8080/hello?name=lisi
    /**
     * 演示查询参数绑定与 {@code @ResponseBody} 文本响应。
     *
     * @param name 查询参数 {@code name}，缺省为 {@code unknown user}
     * @return 直接写入响应体的纯文本问候语，不经过视图解析
     */
    @RequestMapping("/hello")
    @ResponseBody
    public String hello(@RequestParam(name = "name", defaultValue = "unknown user") String name) {
        return "Hello " + name;
    }

    // http://127.0.0.1:8080/user
    /**
     * 演示返回对象时的 JSON 序列化。
     *
     * @return 固定的示例用户（{@code theonefx}/666），由消息转换器序列化为 JSON
     */
    @RequestMapping("/user")
    @ResponseBody
    public User user() {
        User user = new User();
        user.setName("theonefx");
        user.setAge(666);
        return user;
    }

    // http://127.0.0.1:8080/save_user?name=newName&age=11
    /**
     * 演示请求参数按属性名绑定到未注解的对象参数。
     *
     * <p>请求里的 {@code name}/{@code age} 会先绑定到 {@code u}，随后被 {@link #parseUser} 覆盖，
     * 所以回显值固定为 {@code zhangsan}/18。</p>
     *
     * @param u 由 Spring 实例化并填充的模型属性，调用方无需传参
     * @return 回显最终属性值的纯文本
     */
    @RequestMapping("/save_user")
    @ResponseBody
    public String saveUser(User u) {
        return "user will save: name=" + u.getName() + ", age=" + u.getAge();
    }

    // http://127.0.0.1:8080/html
    /**
     * 演示返回视图名（而非 @ResponseBody）。
     *
     * <p>当前模块既没有 {@code index1.html} 也没有模板引擎，因此该映射只能说明视图名的返回方式，
     * 实际访问不会渲染出页面，会落回 404。</p>
     *
     * @return 逻辑视图名 {@code index1.html}
     */
    @RequestMapping("/html")
    public String html() {
        return "index1.html";
    }

    /**
     * 模型属性预处理：为本控制器所有请求准备 {@code User} 并写入固定值。
     *
     * <p>方法无返回值，Spring 会把入参 {@code user} 视为模型属性并加入模型；它先按上面的
     * 默认值绑定请求参数（因此不传参也不会报错），随后被固定值覆盖。三个参数在当前实现里都不会
     * 影响最终结果，保留它们只是示例 @ModelAttribute 的参数绑定能力。</p>
     *
     * @param name 查询参数 {@code name}，缺省 {@code unknown user}；实际未参与赋值
     * @param age  查询参数 {@code age}，缺省 12；实际未参与赋值
     * @param user 待填充的模型属性，由 Spring 创建后传入
     */
    @ModelAttribute
    public void parseUser(@RequestParam(name = "name", defaultValue = "unknown user") String name
            , @RequestParam(name = "age", defaultValue = "12") Integer age, User user) {
        user.setName("zhangsan");
        user.setAge(18);
    }
}
