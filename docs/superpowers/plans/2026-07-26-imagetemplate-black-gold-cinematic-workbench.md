# Imagetemplate Black-Gold Cinematic Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `imagetemplate` static frontend as a responsive four-scene black-gold cinematic workbench without changing its existing APIs or generation behavior.

**Architecture:** Keep the current vanilla HTML/CSS/JavaScript delivery model and existing business-control IDs. Add a semantic scene shell and bottom Dock in HTML, isolate the visual system in CSS, and extend the current JavaScript state with one `activeScene` controller so scene navigation never resets template or generation state.

**Tech Stack:** Java 8, Spring Boot static resources, JUnit 5, AssertJ, vanilla HTML5, CSS3, JavaScript ES5-compatible syntax.

---

## File map

- `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`: static contract tests for the four scenes, Dock, critical control IDs, reduced-motion styles, and scene controller.
- `imagetemplate/src/main/resources/static/index.html`: semantic four-scene application shell while retaining every existing functional element ID.
- `imagetemplate/src/main/resources/static/css/app.css`: black-gold design tokens, cinematic background, scene layout, transitions, responsive behavior, focus states, and reduced-motion fallback.
- `imagetemplate/src/main/resources/static/js/app.js`: active scene state, Dock/previous/next navigation, scene accessibility state, and existing template/generation behavior.
- `README.md`, `AGENTS.md`, `imagetemplate/README.md`, `imagetemplate/AGENTS.md`: synchronized description of the new homepage structure and maintenance boundaries.

### Task 1: Lock the static UI contract with a failing test

**Files:**
- Create: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

- [ ] **Step 1: Write the failing static-resource test**

```java
package com.example.imagetemplate;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import static org.assertj.core.api.Assertions.assertThat;

class ImageTemplateHomepageStaticAssetsTest {

    @Test
    void homepageDefinesFourScenesDockAndExistingBusinessControls() throws Exception {
        String html = read("static/index.html");

        assertThat(html)
                .contains("data-scene=\"discover\"")
                .contains("data-scene=\"deconstruct\"")
                .contains("data-scene=\"direct\"")
                .contains("data-scene=\"render\"")
                .contains("class=\"scene-dock\"")
                .contains("id=\"sceneStatus\"")
                .contains("id=\"scenePrevButton\"")
                .contains("id=\"sceneNextButton\"");

        String[] existingIds = {
                "keywordInput", "categoryTabs", "templateList", "templateCount",
                "detailCategory", "detailTitle", "detailSummary", "jsonTemplate",
                "promptTemplate", "variablesInput", "extraInstructionInput",
                "renderedPrompt", "renderPromptButton", "copyPromptButton",
                "openAiApiKeyInput", "referenceImageInput", "imageSizeSelect",
                "generateImageButton", "generatedImage", "downloadImageButton"
        };
        for (String id : existingIds) {
            assertThat(html).contains("id=\"" + id + "\"");
        }
    }

    @Test
    void cinematicStylesAndSceneControllerHaveAccessibilityFallbacks() throws Exception {
        String css = read("static/css/app.css");
        String js = read("static/js/app.js");

        assertThat(css)
                .contains("--gold:")
                .contains(".cinematic-backdrop")
                .contains(".scene.is-active")
                .contains("@media (prefers-reduced-motion: reduce)");
        assertThat(js)
                .contains("activeScene")
                .contains("setActiveScene")
                .contains("aria-selected")
                .contains("scenePrevButton")
                .contains("sceneNextButton");
    }

    private String read(String path) throws Exception {
        return new String(
                Files.readAllBytes(new ClassPathResource(path).getFile().toPath()),
                StandardCharsets.UTF_8
        );
    }
}
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
mvn -pl imagetemplate -am "-Dtest=ImageTemplateHomepageStaticAssetsTest" -DfailIfNoTests=false test
```

Expected: FAIL because the current page does not contain four scenes, Dock controls, cinematic CSS, or `setActiveScene`.

- [ ] **Step 3: Commit the failing contract**

```powershell
git add imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
git commit -m "test: define imagetemplate cinematic homepage contract"
```

### Task 2: Build the semantic four-scene HTML shell

**Files:**
- Modify: `imagetemplate/src/main/resources/static/index.html`

- [ ] **Step 1: Add the fixed cinematic shell**

Add a decorative background with `aria-hidden="true"`, a Chinese top bar, `sceneStatus`, and a `<main class="scene-stage">`. Use four `<section class="scene">` elements with:

```html
<section class="scene is-active" data-scene="discover" aria-labelledby="discoverTitle">
<section class="scene" data-scene="deconstruct" aria-labelledby="deconstructTitle" aria-hidden="true">
<section class="scene" data-scene="direct" aria-labelledby="directTitle" aria-hidden="true">
<section class="scene" data-scene="render" aria-labelledby="renderTitle" aria-hidden="true">
```

Move the current controls without renaming their IDs:

- `keywordInput`, `categoryTabs`, `templateList`, `templateCount` → `discover`
- template detail, `jsonTemplate`, `promptTemplate`, `copyPromptButton` → `deconstruct`
- `variablesInput`, `extraInstructionInput`, `renderedPrompt`, `renderPromptButton`, `statusLine` → `direct`
- API key, reference images, generation options, result and `imageStatusLine` → `render`

- [ ] **Step 2: Add explicit scene actions and the bottom Dock**

Add `data-scene-target` actions inside scenes and a navigation element:

```html
<nav class="scene-dock" aria-label="工作台场景">
    <button class="dock-step is-active" type="button" data-scene-target="discover" aria-selected="true">灵感大厅</button>
    <button class="dock-step" type="button" data-scene-target="deconstruct" aria-selected="false">模板解构</button>
    <button class="dock-step" type="button" data-scene-target="direct" aria-selected="false">Prompt 编导台</button>
    <button class="dock-step" type="button" data-scene-target="render" aria-selected="false">图片生成舱</button>
    <button id="scenePrevButton" type="button" aria-label="上一幕">←</button>
    <button id="sceneNextButton" type="button" aria-label="下一幕">→</button>
</nav>
```

Keep external links using `target="_blank" rel="noopener"`, and keep the JavaScript include at the end of `<body>`.

- [ ] **Step 3: Run the focused contract test**

Run:

```powershell
mvn -pl imagetemplate -am "-Dtest=ImageTemplateHomepageStaticAssetsTest" -DfailIfNoTests=false test
```

Expected: the HTML assertions pass; the CSS/JavaScript assertion still fails.

- [ ] **Step 4: Commit the scene markup**

```powershell
git add imagetemplate/src/main/resources/static/index.html
git commit -m "feat: add imagetemplate cinematic scene structure"
```

### Task 3: Implement the black-gold responsive visual system

**Files:**
- Modify: `imagetemplate/src/main/resources/static/css/app.css`

- [ ] **Step 1: Replace the light dashboard tokens and shell**

Define the palette and fixed stage:

```css
:root {
    --ink: #070604;
    --surface: rgba(20, 17, 12, 0.72);
    --surface-strong: rgba(28, 23, 15, 0.92);
    --gold: #d6b36a;
    --gold-bright: #f4d99b;
    --ivory: #f6f0e4;
    --muted: #aaa08f;
    --danger: #ff8f7d;
    --success: #9ed8ad;
}

body {
    min-height: 100vh;
    min-height: 100svh;
    overflow: hidden;
    color: var(--ivory);
    background: var(--ink);
}

.scene {
    position: absolute;
    inset: 0;
    visibility: hidden;
    opacity: 0;
    transform: translateY(24px) scale(.985);
    pointer-events: none;
}

.scene.is-active {
    visibility: visible;
    opacity: 1;
    transform: none;
    pointer-events: auto;
}
```

- [ ] **Step 2: Add cinematic background and glass surfaces**

Create `.cinematic-backdrop`, `.backdrop-orb`, `.golden-trace`, and a subtle noise overlay using gradients and pseudo-elements. Style panels with dark translucent backgrounds, `backdrop-filter`, gold borders, restrained shadows, and no external assets.

- [ ] **Step 3: Style all existing controls and content states**

Cover the existing dynamically generated classes from `app.js`, including template/category buttons, selected states, code/prompt blocks, inputs, textareas, selects, reference thumbnails, loading result, download state, status text, and validation hints. Ensure `:focus-visible` has a high-contrast gold outline.

- [ ] **Step 4: Add responsive and reduced-motion rules**

At `max-width: 900px`, allow body/stage content scrolling, change multi-column grids to one column, and make `.scene-dock` horizontally scrollable. Add:

```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        scroll-behavior: auto !important;
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: .01ms !important;
    }
}
```

- [ ] **Step 5: Run the focused contract test**

Run:

```powershell
mvn -pl imagetemplate -am "-Dtest=ImageTemplateHomepageStaticAssetsTest" -DfailIfNoTests=false test
```

Expected: only JavaScript scene-controller assertions remain failing.

- [ ] **Step 6: Commit the visual system**

```powershell
git add imagetemplate/src/main/resources/static/css/app.css
git commit -m "feat: style imagetemplate black gold workbench"
```

### Task 4: Add scene state without changing business behavior

**Files:**
- Modify: `imagetemplate/src/main/resources/static/js/app.js`

- [ ] **Step 1: Register scene elements and state**

Extend `elements` with `sceneStatus`, `scenePrevButton`, `sceneNextButton`, scene nodes, and Dock buttons. Add:

```javascript
var sceneOrder = ['discover', 'deconstruct', 'direct', 'render'];
var activeScene = 'discover';

function setActiveScene(sceneName, shouldFocus) {
    if (sceneOrder.indexOf(sceneName) < 0) {
        return;
    }
    activeScene = sceneName;
    // Toggle is-active, aria-hidden, aria-selected and previous/next disabled state.
    // Update sceneStatus with the selected scene's numbered Chinese label.
    // Focus the scene heading only when shouldFocus is true.
}
```

Implement the comment body explicitly with `forEach`, `classList.toggle`, `setAttribute`, and `removeAttribute`, using the target heading's temporary `tabindex="-1"` for focus.

- [ ] **Step 2: Wire Dock, previous, next, and contextual actions**

Use delegated click handling for every `[data-scene-target]`. Previous and next use `sceneOrder.indexOf(activeScene)` and clamp at the endpoints. Initialize with:

```javascript
setActiveScene('discover', false);
```

Do not clear template, prompt, API key, upload, or result state from `setActiveScene`.

- [ ] **Step 3: Preserve existing template and generation flows**

Keep all current API functions and event listeners. When a template is selected, continue loading details without automatically changing scenes. Existing `renderPrompt`, `generateImage`, dimension validation, session-key behavior, reference-image limits, download setup, and error messages must remain intact.

- [ ] **Step 4: Run syntax and focused tests**

Run:

```powershell
node --check imagetemplate/src/main/resources/static/js/app.js
mvn -pl imagetemplate -am "-Dtest=ImageTemplateHomepageStaticAssetsTest" -DfailIfNoTests=false test
```

Expected: JavaScript syntax check exits 0 and the focused test passes.

- [ ] **Step 5: Commit scene navigation**

```powershell
git add imagetemplate/src/main/resources/static/js/app.js
git commit -m "feat: navigate imagetemplate cinematic scenes"
```

### Task 5: Synchronize project documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `imagetemplate/README.md`
- Modify: `imagetemplate/AGENTS.md`

- [ ] **Step 1: Update module-facing documentation**

Document that the frontend is a black-gold four-scene single-view workbench:

```text
灵感大厅 → 模板解构 → Prompt 编导台 → 图片生成舱
```

State that the bottom Dock controls scenes, scene changes retain entered/generated state, the frontend remains dependency-free vanilla HTML/CSS/JavaScript, and reduced-motion/mobile fallbacks are required.

- [ ] **Step 2: Update root project documentation**

In the root module description and static-resource conventions, describe `imagetemplate` as the first microservice page aligned with the `website` cinematic homepage. Do not change ports, API lists, startup commands, or module ownership.

- [ ] **Step 3: Verify documentation consistency**

Run:

```powershell
rg -n "灵感大厅|模板解构|Prompt 编导台|图片生成舱|黑金" README.md AGENTS.md imagetemplate/README.md imagetemplate/AGENTS.md
git diff --check
```

Expected: all four files mention the new design where appropriate, and `git diff --check` exits 0.

- [ ] **Step 4: Commit documentation**

```powershell
git add README.md AGENTS.md imagetemplate/README.md imagetemplate/AGENTS.md
git commit -m "docs: describe imagetemplate cinematic workbench"
```

### Task 6: Full regression and browser acceptance

**Files:**
- Modify if needed: `imagetemplate/src/main/resources/static/index.html`
- Modify if needed: `imagetemplate/src/main/resources/static/css/app.css`
- Modify if needed: `imagetemplate/src/main/resources/static/js/app.js`
- Modify if needed: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

- [ ] **Step 1: Run the complete module regression**

Run:

```powershell
mvn -pl imagetemplate -am test
node --check imagetemplate/src/main/resources/static/js/app.js
git diff --check
```

Expected: all Maven tests pass, JavaScript syntax check exits 0, and no whitespace errors are reported.

- [ ] **Step 2: Start the service for local acceptance**

Run:

```powershell
mvn -pl imagetemplate -am spring-boot:run
```

Expected: Spring Boot serves `http://127.0.0.1:8082/` and `/api/health` reports success.

- [ ] **Step 3: Verify the desktop workflow**

At a desktop viewport, verify:

- initial scene is 灵感大厅;
- categories and search filter template cards;
- template selection remains selected while moving through all four scenes;
- template detail, JSON and prompt data display;
- Prompt rendering updates `renderedPrompt`;
- invalid custom dimensions prevent generation and explain the rule;
- failed generation retains Prompt and form values;
- Dock and previous/next controls update active and disabled states.

- [ ] **Step 4: Verify mobile and reduced-motion behavior**

At a phone viewport, verify content is reachable by scrolling, the Dock scrolls horizontally, all controls remain at least 44px high, and no critical field overflows. Emulate reduced motion and confirm the workbench remains fully usable without background motion.

- [ ] **Step 5: Commit any acceptance fixes**

If acceptance required tracked-file corrections, stage only the files listed under this task and commit:

```powershell
git commit -m "fix: polish imagetemplate cinematic workbench"
```

If no corrections were needed, do not create an empty commit.
