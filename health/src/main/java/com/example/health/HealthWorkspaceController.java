package com.example.health;

import com.example.personalagent.security.LocalSecurity;
import com.example.personalagent.service.HealthArchive;
import com.example.personalagent.service.VaultService;
import org.springframework.web.bind.annotation.*;

import javax.servlet.http.HttpServletRequest;
import java.util.Map;

import static com.example.personalagent.Api.*;

/** 健康应用的本机登录和仓库设置。 */
@RestController
public class HealthWorkspaceController {
    private final LocalSecurity security;
    private final VaultService vault;
    private final HealthArchive archive;

    public HealthWorkspaceController(LocalSecurity security, VaultService vault, HealthArchive archive) {
        this.security=security; this.vault=vault; this.archive=archive;
    }

    @GetMapping("/api/health") public Object health() { return map("success",true,"service","health"); }
    @GetMapping("/api/auth/status") public Object status(HttpServletRequest request) { return ok(security.status(request)); }
    @PostMapping("/api/auth/setup") public Object setup(@RequestBody Map<String,Object> input,HttpServletRequest request) {
        security.authenticate(text(input,"password"),true,request);
        return status(request);
    }
    @PostMapping("/api/auth/login") public Object login(@RequestBody Map<String,Object> input,HttpServletRequest request) {
        security.authenticate(text(input,"password"),false,request);
        return status(request);
    }
    @PostMapping("/api/auth/logout") public Object logout(HttpServletRequest request) {
        request.getSession().invalidate();
        return ok(map("authenticated",false));
    }
    @PostMapping("/api/vault/connect") public Object connect(@RequestBody Map<String,Object> input) throws Exception {
        synchronized (vault) {
            require(!archive.busy(),"请等待报告处理完成，再切换仓库");
            vault.connect(text(input,"path"));
            return ok(map("workspace",vault.root().toString()));
        }
    }
}
