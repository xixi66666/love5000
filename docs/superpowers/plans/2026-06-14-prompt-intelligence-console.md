# Prompt Intelligence Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a prompt intelligence console in the `website` module that lets the user navigate prompt sources and generate multi-version prompts from a simple scene.

**Architecture:** Add a focused `com.example.website.prompt` package with registry, fetch, summary, compose, DTO, and controller classes. Add native static frontend files under `website/src/main/resources/static/prompt-console`, then add a homepage entry. Core behavior is rule-based and covered by JUnit tests before implementation.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Spring MVC, JUnit 5, AssertJ, native HTML/CSS/JavaScript.

---

## File Structure

- Create `website/src/main/java/com/example/website/prompt/model/PromptSource.java`: immutable-ish source definition POJO.
- Create `website/src/main/java/com/example/website/prompt/model/PromptSourceSnapshot.java`: runtime status and summary POJO.
- Create `website/src/main/java/com/example/website/prompt/model/PromptInsight.java`: source contribution POJO.
- Create `website/src/main/java/com/example/website/prompt/model/PromptVariant.java`: generated prompt variant POJO.
- Create `website/src/main/java/com/example/website/prompt/dto/PromptSourceRefreshRequest.java`: refresh request body.
- Create `website/src/main/java/com/example/website/prompt/dto/PromptComposeRequest.java`: compose request body.
- Create `website/src/main/java/com/example/website/prompt/service/PromptSourceRegistry.java`: whitelist and defaults.
- Create `website/src/main/java/com/example/website/prompt/service/PromptSourceFetchService.java`: fallback-first refresh service with URL whitelist guard.
- Create `website/src/main/java/com/example/website/prompt/service/PromptComposeService.java`: rule-based prompt generation.
- Create `website/src/main/java/com/example/website/prompt/controller/PromptConsoleController.java`: REST API.
- Create `website/src/test/java/com/example/website/prompt/service/PromptSourceRegistryTest.java`.
- Create `website/src/test/java/com/example/website/prompt/service/PromptSourceFetchServiceTest.java`.
- Create `website/src/test/java/com/example/website/prompt/service/PromptComposeServiceTest.java`.
- Create `website/src/test/java/com/example/website/prompt/controller/PromptConsoleControllerTest.java`.
- Create `website/src/main/resources/static/prompt-console/index.html`.
- Create `website/src/main/resources/static/prompt-console/prompt-console.css`.
- Create `website/src/main/resources/static/prompt-console/prompt-console.js`.
- Modify `website/src/main/resources/static/index.html`: add nav link and service card.
- Modify `website/src/main/resources/static/css/style.css`: add prompt card accent.

## Task 1: Source Registry

**Files:**
- Create: `website/src/test/java/com/example/website/prompt/service/PromptSourceRegistryTest.java`
- Create: `website/src/main/java/com/example/website/prompt/model/PromptSource.java`
- Create: `website/src/main/java/com/example/website/prompt/model/PromptSourceSnapshot.java`
- Create: `website/src/main/java/com/example/website/prompt/service/PromptSourceRegistry.java`

- [ ] **Step 1: Write failing registry tests**

```java
package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PromptSourceRegistryTest {

    private final PromptSourceRegistry registry = new PromptSourceRegistry();

    @Test
    void listSourcesReturnsDefaultWhitelist() {
        List<PromptSource> sources = registry.listSources();

        assertThat(sources).extracting(PromptSource::getId)
                .containsExactly(
                        "prompt123",
                        "awesome-chatgpt-prompts",
                        "awesome-prompts",
                        "youmind-awesome-gpt-image-2",
                        "freestylefly-awesome-gpt-image-2",
                        "evolink-awesome-gpt-image-2-prompts");
    }

    @Test
    void findSourceRejectsUnknownIds() {
        assertThat(registry.findSource("not-allowed")).isNull();
    }

    @Test
    void defaultSnapshotUsesFallbackSummary() {
        assertThat(registry.defaultSnapshot("prompt123").getStatus()).isEqualTo("fallback");
        assertThat(registry.defaultSnapshot("prompt123").getSummary()).contains("提示词");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -pl website -Dtest=PromptSourceRegistryTest test`

Expected: compilation failure because `PromptSourceRegistry` and model classes do not exist.

- [ ] **Step 3: Implement registry and models**

Create simple Java 8 POJOs with getters, setters, constructors, and registry defaults matching the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -pl website -Dtest=PromptSourceRegistryTest test`

Expected: test passes.

## Task 2: Source Refresh Fallback

**Files:**
- Create: `website/src/test/java/com/example/website/prompt/service/PromptSourceFetchServiceTest.java`
- Create: `website/src/main/java/com/example/website/prompt/service/PromptSourceFetchService.java`

- [ ] **Step 1: Write failing fetch service tests**

```java
package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSourceSnapshot;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PromptSourceFetchServiceTest {

    private final PromptSourceRegistry registry = new PromptSourceRegistry();
    private final PromptSourceFetchService service = new PromptSourceFetchService(registry);

    @Test
    void refreshUnknownSourceReturnsFailedSnapshot() {
        List<PromptSourceSnapshot> snapshots = service.refresh(Arrays.asList("unknown-source"));

        assertThat(snapshots).hasSize(1);
        assertThat(snapshots.get(0).getSourceId()).isEqualTo("unknown-source");
        assertThat(snapshots.get(0).getStatus()).isEqualTo("failed");
        assertThat(snapshots.get(0).getMessage()).contains("not allowed");
    }

    @Test
    void listSnapshotsUsesFallbacksBeforeRefresh() {
        List<PromptSourceSnapshot> snapshots = service.listSnapshots();

        assertThat(snapshots).hasSize(6);
        assertThat(snapshots).allSatisfy(snapshot -> assertThat(snapshot.getStatus()).isEqualTo("fallback"));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -pl website -Dtest=PromptSourceFetchServiceTest test`

Expected: compilation failure because `PromptSourceFetchService` does not exist.

- [ ] **Step 3: Implement fallback fetch service**

Implement in-memory snapshots from registry defaults. For first version, `refresh` should keep fallback snapshots for allowed IDs and return failed snapshots for unknown IDs. Do not make network calls yet.

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -pl website -Dtest=PromptSourceFetchServiceTest test`

Expected: test passes.

## Task 3: Prompt Composition

**Files:**
- Create: `website/src/test/java/com/example/website/prompt/service/PromptComposeServiceTest.java`
- Create: `website/src/main/java/com/example/website/prompt/model/PromptInsight.java`
- Create: `website/src/main/java/com/example/website/prompt/model/PromptVariant.java`
- Create: `website/src/main/java/com/example/website/prompt/dto/PromptComposeRequest.java`
- Create: `website/src/main/java/com/example/website/prompt/service/PromptComposeService.java`

- [ ] **Step 1: Write failing compose tests**

```java
package com.example.website.prompt.service;

import com.example.website.prompt.dto.PromptComposeRequest;
import com.example.website.prompt.model.PromptVariant;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PromptComposeServiceTest {

    private final PromptComposeService service = new PromptComposeService(
            new PromptSourceRegistry(),
            new PromptSourceFetchService(new PromptSourceRegistry()));

    @Test
    void composeRejectsBlankScene() {
        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene(" ");

        assertThatThrownBy(() -> service.compose(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("场景不能为空");
    }

    @Test
    void composeImagePromptIncludesVisualStructureAndNegativeLimits() {
        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene("雨夜城市街巷，想做一张电影感海报");
        request.setPurpose("image");
        request.setTone("cinematic");
        request.setLength("balanced");

        List<PromptVariant> variants = service.compose(request);

        assertThat(variants).extracting(PromptVariant::getType)
                .contains("image", "general", "poster", "video", "short");
        assertThat(variants.get(0).getType()).isEqualTo("image");
        assertThat(variants.get(0).getPrompt())
                .contains("雨夜城市街巷")
                .contains("镜头")
                .contains("光线")
                .contains("构图")
                .contains("不要出现乱码文字、水印、额外 logo");
    }

    @Test
    void composeVideoPromptIncludesStoryboardLanguage() {
        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene("未来机器人陪伴孩子看星空");
        request.setPurpose("video");

        List<PromptVariant> variants = service.compose(request);

        assertThat(variants.get(0).getType()).isEqualTo("video");
        assertThat(variants.get(0).getPrompt())
                .contains("分镜")
                .contains("运动")
                .contains("节奏")
                .contains("连续性");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -pl website -Dtest=PromptComposeServiceTest test`

Expected: compilation failure because compose classes do not exist.

- [ ] **Step 3: Implement compose service**

Implement deterministic prompt variants using string templates. Put requested purpose first. Include source IDs and sections for every variant.

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -pl website -Dtest=PromptComposeServiceTest test`

Expected: test passes.

## Task 4: REST Controller

**Files:**
- Create: `website/src/test/java/com/example/website/prompt/controller/PromptConsoleControllerTest.java`
- Create: `website/src/main/java/com/example/website/prompt/dto/PromptSourceRefreshRequest.java`
- Create: `website/src/main/java/com/example/website/prompt/controller/PromptConsoleController.java`

- [ ] **Step 1: Write failing controller tests**

Use `@WebMvcTest(PromptConsoleController.class)` with mocked services. Cover `GET /api/prompt-sources`, `POST /api/prompt-sources/refresh`, `POST /api/prompts/compose`, and blank scene error.

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -pl website -Dtest=PromptConsoleControllerTest test`

Expected: compilation failure because controller does not exist.

- [ ] **Step 3: Implement controller**

Return `Map<String, Object>` responses with `success` and payload keys. Catch `IllegalArgumentException` in compose and return `success: false`.

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -pl website -Dtest=PromptConsoleControllerTest test`

Expected: test passes.

## Task 5: Static Prompt Console Page

**Files:**
- Create: `website/src/main/resources/static/prompt-console/index.html`
- Create: `website/src/main/resources/static/prompt-console/prompt-console.css`
- Create: `website/src/main/resources/static/prompt-console/prompt-console.js`

- [ ] **Step 1: Create page markup**

Use semantic HTML: header, main, section, form, buttons, textarea, segmented controls, source list, results list, and aria-live status region.

- [ ] **Step 2: Create CSS**

Implement dark information-console layout with responsive grid, 8px card radius, 44px controls, focus rings, reduced motion, and mobile stacking.

- [ ] **Step 3: Create JavaScript**

Fetch `/api/prompt-sources` on load, render source cards, refresh sources, submit compose request, render prompt variants, and copy prompt text.

## Task 6: Homepage Entry

**Files:**
- Modify: `website/src/main/resources/static/index.html`
- Modify: `website/src/main/resources/static/css/style.css`

- [ ] **Step 1: Add nav link**

Add `<a href="prompt-console/index.html">Prompt</a>` to the homepage navigation.

- [ ] **Step 2: Add service card**

Add a `service-card service-card-prompt` linking to `/prompt-console/index.html` with `data-health-url="/prompt-console/index.html"`.

- [ ] **Step 3: Add accent style**

Add `.service-card-prompt { --accent-rgb: 94, 231, 255; }`.

## Task 7: Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run website tests**

Run: `mvn -pl website -am test`

Expected: build success and all website tests pass.

- [ ] **Step 2: Start website for manual UI check**

Run: `mvn -pl website -am spring-boot:run`

Visit `http://localhost:8080/prompt-console/index.html`.

- [ ] **Step 3: Browser/UI check**

Check desktop and 375px mobile layout, generate a prompt, verify copy button, verify homepage card.

