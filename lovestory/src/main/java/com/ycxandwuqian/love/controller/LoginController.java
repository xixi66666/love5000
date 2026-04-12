
package com.ycxandwuqian.love.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

import java.util.HashMap;
import java.util.Map;

@Controller
public class LoginController {

    private static final String CORRECT_ANSWER = "我爱你的很";

    @GetMapping("/")
    public String rootPath() {
        return "redirect:/login.html";
    }

    @GetMapping("/login")
    public String loginPage() {
        return "forward:/login.html";
    }

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