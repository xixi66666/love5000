# Guitar Service Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the generated `guitar` Spring Boot project into a minimal, tested `love530` Maven module on port 8088 with a health endpoint, a service homepage, a Website entry, and complete repository documentation.

**Architecture:** `guitar` inherits dependency and plugin versions from the root Maven parent and remains an independently runnable Spring Boot Web module. It exposes a dependency-free health endpoint and classpath-hosted static homepage; `website` links to it and performs the existing generic cross-port availability check without managing the Guitar process.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Spring MVC, Maven, JUnit 5, MockMvc, HTML, CSS

---

## File Map

- Modify `pom.xml`: add `guitar` to the Maven reactor.
- Replace `guitar/pom.xml`: inherit the root parent and keep only Web/Test dependencies and standard repository plugins.
- Modify `guitar/src/main/resources/application.properties`: set application name and port 8088.
- Delete `guitar/.git`: remove the accidental nested repository boundary.
- Delete `guitar/HELP.md`: remove generated help text.
- Delete `guitar/src/main/java/com/example/guitar/demos/`: remove generated OSS and Web demo classes.
- Delete `guitar/src/main/resources/oss-test.json`: remove OSS demo data.
- Modify `guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java`: cover context loading, health JSON, and the static homepage.
- Create `guitar/src/main/java/com/example/guitar/controller/HealthController.java`: expose the service liveness response.
- Replace `guitar/src/main/resources/static/index.html`: provide the minimal formal Guitar service page.
- Modify `website/src/main/resources/static/index.html`: add the Guitar navigation item and service card.
- Modify `website/src/main/resources/static/css/style.css`: define the Guitar card accent.
- Create `guitar/AGENTS.md`: document module-local rules and commands.
- Modify `AGENTS.md`: document the new module, port, endpoint, commands, and test requirements.

### Task 1: Normalize The Maven Module And Remove Scaffold Artifacts

**Files:**
- Modify: `pom.xml`
- Replace: `guitar/pom.xml`
- Modify: `guitar/src/main/resources/application.properties`
- Delete: `guitar/.git`
- Delete: `guitar/HELP.md`
- Delete: `guitar/src/main/java/com/example/guitar/demos/oss/OssConfig.java`
- Delete: `guitar/src/main/java/com/example/guitar/demos/oss/OssDemoService.java`
- Delete: `guitar/src/main/java/com/example/guitar/demos/web/BasicController.java`
- Delete: `guitar/src/main/java/com/example/guitar/demos/web/PathVariableController.java`
- Delete: `guitar/src/main/java/com/example/guitar/demos/web/User.java`
- Delete: `guitar/src/main/resources/oss-test.json`

- [ ] **Step 1: Add Guitar to the root reactor**

Add the module after `imagetemplate` in root `pom.xml`:

```xml
<modules>
    <module>website</module>
    <module>lovestory</module>
    <module>common</module>
    <module>imagetemplate</module>
    <module>guitar</module>
</modules>
```

- [ ] **Step 2: Replace the generated Guitar POM**

Use this complete `guitar/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.example</groupId>
        <artifactId>love530</artifactId>
        <version>0.0.1-SNAPSHOT</version>
    </parent>

    <artifactId>guitar</artifactId>
    <name>guitar</name>
    <description>Guitar web service</description>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.8.1</version>
                <configuration>
                    <source>${java.version}</source>
                    <target>${java.version}</target>
                    <encoding>${project.build.sourceEncoding}</encoding>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <version>${spring-boot.version}</version>
                <configuration>
                    <mainClass>com.example.guitar.GuitarApplication</mainClass>
                </configuration>
                <executions>
                    <execution>
                        <id>repackage</id>
                        <goals>
                            <goal>repackage</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>2.22.2</version>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 3: Replace the runtime properties**

Use this complete `guitar/src/main/resources/application.properties`:

```properties
spring.application.name=guitar
server.port=8088
```

- [ ] **Step 4: Remove the generated files and nested Git repository**

Delete the listed text files with the patch tool. For the nested Git metadata, resolve and verify the exact path before deletion:

```powershell
$target = (Resolve-Path -LiteralPath 'guitar\.git').Path
if ($target -ne 'D:\Code\Java_Code\love530\guitar\.git') { throw "Unexpected delete target: $target" }
Remove-Item -LiteralPath $target -Recurse -Force
```

- [ ] **Step 5: Run the existing context test**

Run:

```bash
mvn -pl guitar -am test
```

Expected: reactor contains `love530` and `guitar`; `GuitarApplicationTests.contextLoads` passes without OSS configuration or network calls.

- [ ] **Step 6: Commit the module normalization**

Stage only the root POM and Guitar module files, then commit:

```bash
git add pom.xml guitar
git commit --only pom.xml guitar -m "chore: initialize guitar maven module"
```

### Task 2: Add The Health Endpoint With TDD

**Files:**
- Modify: `guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java`
- Create: `guitar/src/main/java/com/example/guitar/controller/HealthController.java`

- [ ] **Step 1: Write the failing health endpoint test**

Replace `GuitarApplicationTests.java` with:

```java
package com.example.guitar;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class GuitarApplicationTests {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void contextLoads() {
    }

    @Test
    void healthEndpointReturnsServiceStatus() throws Exception {
        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.service").value("guitar"));
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
mvn -pl guitar -am -Dtest=GuitarApplicationTests test
```

Expected: FAIL because `/api/health` is handled as a missing static resource and returns 404.

- [ ] **Step 3: Implement the minimal controller**

Create `HealthController.java`:

```java
package com.example.guitar.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class HealthController {

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", true);
        response.put("service", "guitar");
        return response;
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
mvn -pl guitar -am -Dtest=GuitarApplicationTests test
```

Expected: PASS with two Guitar tests.

- [ ] **Step 5: Commit the health endpoint**

```bash
git add guitar/src/main/java/com/example/guitar/controller/HealthController.java guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java
git commit --only guitar/src/main/java/com/example/guitar/controller/HealthController.java guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java -m "feat: add guitar health endpoint"
```

### Task 3: Replace The Generated Homepage With TDD

**Files:**
- Modify: `guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java`
- Replace: `guitar/src/main/resources/static/index.html`

- [ ] **Step 1: Add the failing homepage test**

Add this test method to `GuitarApplicationTests`:

```java
@Test
void homepageIdentifiesTheGuitarService() throws Exception {
    mockMvc.perform(get("/"))
            .andExpect(status().isOk())
            .andExpect(content().contentTypeCompatibleWith("text/html"))
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Guitar Service")))
            .andExpect(content().string(org.hamcrest.Matchers.containsString("8088")));
}
```

- [ ] **Step 2: Run the homepage test to verify it fails**

Run:

```bash
mvn -pl guitar -am -Dtest=GuitarApplicationTests#homepageIdentifiesTheGuitarService test
```

Expected: FAIL because the generated page contains neither `Guitar Service` nor `8088`.

- [ ] **Step 3: Replace the homepage**

Write a valid Chinese `<!doctype html>` page with embedded CSS and these stable elements:

```html
<main>
    <p class="eyebrow">LOVE530 / 8088</p>
    <h1>Guitar Service</h1>
    <p class="status"><span aria-hidden="true"></span>Service online</p>
    <a href="/api/health">Health API</a>
</main>
```

Use a restrained charcoal background, off-white text, a teal status accent, an 8px-or-smaller link radius, responsive padding, and no external assets, scripts, gradients, or feature claims. Include `lang="zh-CN"`, UTF-8, a viewport meta tag, title `Guitar Service`, and accessible focus styles.

- [ ] **Step 4: Run all Guitar tests**

Run:

```bash
mvn -pl guitar -am test
```

Expected: PASS with context, health endpoint, and homepage tests.

- [ ] **Step 5: Commit the homepage**

```bash
git add guitar/src/main/resources/static/index.html guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java
git commit --only guitar/src/main/resources/static/index.html guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java -m "feat: add guitar service homepage"
```

### Task 4: Add Guitar To The Website Service Directory

**Files:**
- Modify: `website/src/main/resources/static/index.html`
- Modify: `website/src/main/resources/static/css/style.css`

- [ ] **Step 1: Add the navigation entry**

Add this link beside the other service links:

```html
<a href="http://127.0.0.1:8088/" target="_blank" rel="noopener">Guitar</a>
```

- [ ] **Step 2: Add the service card**

Add this card to `.service-grid`:

```html
<a class="service-card service-card-guitar" href="http://127.0.0.1:8088/" target="_blank" rel="noopener" data-health-url="http://127.0.0.1:8088/api/health" data-health-mode="no-cors">
    <strong>Guitar · 8088</strong>
    <span class="service-status" aria-label="检测中" title="检测中"></span>
</a>
```

- [ ] **Step 3: Add the card accent**

Add this rule beside the other service-card accent variables:

```css
.service-card-guitar {
    --accent-rgb: 105, 214, 193;
}
```

Do not modify `script.js`; the existing selector `.service-card[data-health-url]` discovers the new card automatically.

- [ ] **Step 4: Run Website tests**

Run:

```bash
mvn -pl website -am test
```

Expected: PASS; tests do not require Guitar to be running because Website only contains a link and browser-side health metadata.

- [ ] **Step 5: Commit Website integration**

```bash
git add website/src/main/resources/static/index.html website/src/main/resources/static/css/style.css
git commit --only website/src/main/resources/static/index.html website/src/main/resources/static/css/style.css -m "feat: add guitar service entry"
```

### Task 5: Document The New Module

**Files:**
- Create: `guitar/AGENTS.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Create module-local instructions**

Write `guitar/AGENTS.md` with these explicit facts:

````markdown
# AGENTS.md

## 模块概述

`guitar` 是 `love530` 的 Java 8 + Spring Boot 2.6.13 Web 子模块，默认端口为 `8088`。当前只提供基础首页和健康检查，不使用数据库、OSS、认证或外部服务。

## 开发命令

从仓库根目录运行：

```bash
mvn -pl guitar -am test
mvn -f guitar/pom.xml spring-boot:run
```

访问地址：

```text
http://127.0.0.1:8088/
http://127.0.0.1:8088/api/health
```

## 模块边界

- 正式代码放在 `com.example.guitar` 下，不把业务代码放入 `demos`。
- 新增跨模块公共能力时优先复用或扩展 `common`。
- 未明确需要前，不引入数据库、MyBatis、OSS、Nacos 或认证。
- 新增数据库能力时遵循根目录 DAO + XML Mapper 约定，不使用 JPA、JdbcTemplate 或 Java 内联 SQL。
- 新增接口响应至少包含 `success` 字段，并覆盖成功路径和主要失败路径。
- 不提交密钥、`target/`、IDE 缓存或运行日志。

## 验证要求

- 修改 Java 代码后运行 `mvn -pl guitar -am test`。
- 修改首页后启动服务并验证 `/` 与 `/api/health`。
- 修改端口、名称或健康地址时，同步更新根 `AGENTS.md` 和 Website 主页入口。
````

Use separate outer four-backtick fences when writing the file so the inner command fences remain valid Markdown.

- [ ] **Step 2: Update root repository instructions**

Apply these exact documentation facts throughout root `AGENTS.md`:

- Add `guitar` to the current Java module list as a minimal Guitar Web service.
- Add `mvn -pl guitar -am test` to module tests.
- Add the start command `mvn -f guitar/pom.xml spring-boot:run` and state default port `8088`.
- Add `guitar/` to the project tree and module responsibility list.
- Add `guitar: 8088` to the port table.
- Add `GET /api/health` under a Guitar API heading.
- State that Guitar currently has no database and its static page lives under `guitar/src/main/resources/static`.
- Add Guitar tests and homepage/health verification to the test strategy and pre-submit checklist.

- [ ] **Step 3: Check documentation consistency**

Run:

```bash
rg -n "guitar|Guitar|8088|/api/health" AGENTS.md guitar/AGENTS.md
```

Expected: root and module documents both contain the module name, port, start/test commands, and health endpoint; no statement describes Guitar as a Python service or a non-Maven module.

- [ ] **Step 4: Commit documentation**

```bash
git add AGENTS.md guitar/AGENTS.md
git commit --only AGENTS.md guitar/AGENTS.md -m "docs: document guitar service"
```

### Task 6: Verify The Integrated Service

**Files:**
- Verify only; no planned file changes.

- [ ] **Step 1: Run Guitar tests from the reactor**

```bash
mvn -pl guitar -am test
```

Expected: BUILD SUCCESS and all Guitar tests pass.

- [ ] **Step 2: Run Website tests**

```bash
mvn -pl website -am test
```

Expected: BUILD SUCCESS. If failures occur only in files already modified before this task, record them separately and do not overwrite those changes.

- [ ] **Step 3: Run the full Maven test suite**

```bash
mvn test
```

Expected: BUILD SUCCESS for all reactor modules including Guitar. Record unrelated pre-existing failures without modifying out-of-scope code.

- [ ] **Step 4: Start Guitar and verify HTTP behavior**

Start the long-running process from the repository root:

```bash
mvn -f guitar/pom.xml spring-boot:run
```

Verify:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8088/ | Select-Object StatusCode
Invoke-RestMethod http://127.0.0.1:8088/api/health | ConvertTo-Json -Compress
```

Expected homepage status: `200`.

Expected health body:

```json
{"success":true,"service":"guitar"}
```

- [ ] **Step 5: Inspect final scope**

```bash
git status --short
git log --oneline -6
```

Expected: implementation commits contain only the files named in this plan. Pre-existing unrelated worktree changes remain untouched, including the already staged deletion of `scripts/start-love5000.ps1`.
