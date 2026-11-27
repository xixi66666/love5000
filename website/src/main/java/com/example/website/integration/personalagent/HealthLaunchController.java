package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.servlet.http.HttpServletRequest;
import java.util.Map;

/** 健康管理通过同一套本机 Java 启动与来源检查，维护自己的进程。 */
@RestController
@RequestMapping("/api/services/health")
@ConditionalOnProperty(prefix="health.click-start",name="enabled",havingValue="true")
public class HealthLaunchController {
    private final PersonalAgentController localLauncher;

    public HealthLaunchController(ObjectMapper json, ServiceHealthProperties checks,
                                  @Value("${health.click-start.work-dir:health}") String directory,
                                  @Value("${health.click-start.port:5180}") int port,
                                  @Value("${health.click-start.command:}") String command) {
        PersonalAgentProperties settings = new PersonalAgentProperties();
        settings.setPort(port);
        settings.setWorkDir(directory);
        settings.setCommand(command);
        localLauncher = new PersonalAgentController(new PersonalAgentProcessManager(json,checks,settings,"health","健康管理"));
    }

    @PostMapping("/start") public ResponseEntity<Map<String,Object>> start(HttpServletRequest request) {
        return localLauncher.start(request);
    }

    @GetMapping("/status") public ResponseEntity<Map<String,Object>> status(HttpServletRequest request) {
        return localLauncher.status(request);
    }
}
