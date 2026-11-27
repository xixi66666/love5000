
package com.ycxandwuqian.love.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

import java.util.HashMap;
import java.util.Map;

/**
 * 恋爱相册的入口门禁控制器。
 *
 * <p>用一道"暗号问答"代替正式登录：{@code POST /api/login/verify} 将用户输入与硬编码的
 * {@link #CORRECT_ANSWER} 比较，命中即返回 {@code success=true}。校验结果只被页面脚本使用，
 * 服务端既不签发 Session、也不写 Cookie，后续接口不做任何鉴权，因此它只是氛围性的入口提示，
 * 不能当作访问控制。</p>
 *
 * <p>根路径 {@code /} 在本类中返回 redirect，但实际请求通常先被
 * {@link com.ycxandwuqian.love.config.WebConfig} 中 order 为 -1 的视图控制器截获并改为 forward，
 * 两者对用户可见的差异仅是浏览器地址栏的内容。</p>
 */
@Controller
public class LoginController {

    /** 门禁暗号的正确答案；比较时忽略大小写并去除首尾空白。 */
    private static final String CORRECT_ANSWER = "我爱你的很";

    /**
     * 根路径跳转兜底。
     *
     * @return 指向登录页的重定向视图名；仅在视图控制器未被装配时才会走到这里
     */
    @GetMapping("/")
    public String rootPath() {
        return "redirect:/login.html";
    }

    /**
     * 登录页入口。
     *
     * @return 转发到静态资源 {@code login.html} 的视图名，转发不改变浏览器地址栏
     */
    @GetMapping("/login")
    public String loginPage() {
        return "forward:/login.html";
    }

    /**
     * 校验门禁答案。
     *
     * <p>只做去空白后的忽略大小写比较，不记录尝试次数、不做限流、不写日志，
     * 因此猜错可以无限重试。答案为空或缺失时由 Spring MVC 的必填参数校验直接返回 400，
     * 不会进入本方法。</p>
     *
     * @param answer 用户输入的答案，会先去除首尾空白再比较
     * @return {@code success=true} 表示通过并附带"验证成功"，否则为 {@code success=false}
     *         与"答案不正确"；两种结果都返回 HTTP 200
     */
    @PostMapping("/api/login/verify")
    @ResponseBody
    public Map<String, Object> verifyAnswer(@RequestParam String answer) {
        Map<String, Object> response = new HashMap<>();

        if (CORRECT_ANSWER.equalsIgnoreCase(answer.trim())) {
            response.put("success", true);
            response.put("message", "验证成功");
        } else {
            response.put("success", false);
            response.put("message", "答案不正确");
        }

        return response;
    }
}