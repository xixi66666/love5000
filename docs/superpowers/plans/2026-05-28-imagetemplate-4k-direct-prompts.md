# imagetemplate 4K Direct Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add validated GPT Image-2 custom sizes up to 4K and a direct-prompt template category while keeping structured variable JSON for advanced templates.

**Architecture:** The backend normalizes and validates the `size` value before both JSON and multipart OpenAI requests. The frontend exposes recommended sizes plus custom input, performs the same validation for fast feedback, and treats `direct-prompt` templates as prompt-ready templates. Template data remains in `image-prompt-templates.json`.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Jackson, JUnit 5, AssertJ, native HTML/CSS/JavaScript.

---

### Task 1: Backend Size Validation

**Files:**
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/service/OpenAiImageGenerationServiceTest.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/service/OpenAiImageGenerationService.java`

- [ ] **Step 1: Write the failing tests**

Create `OpenAiImageGenerationServiceTest` with reflection tests for the private normalization method that will be added:

```java
package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageGenerationRequest;
import org.junit.jupiter.api.Test;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OpenAiImageGenerationServiceTest {

    @Test
    void normalizeImageSizeAcceptsRecommended4kSize() throws Exception {
        String size = normalizeImageSize("3840x2160");

        assertThat(size).isEqualTo("3840x2160");
    }

    @Test
    void normalizeImageSizeAcceptsUppercaseSeparatorAndWhitespace() throws Exception {
        String size = normalizeImageSize(" 2160X3840 ");

        assertThat(size).isEqualTo("2160x3840");
    }

    @Test
    void normalizeImageSizeDefaultsBlankSize() throws Exception {
        String size = normalizeImageSize("");

        assertThat(size).isEqualTo("1024x1024");
    }

    @Test
    void normalizeImageSizeRejectsNonMultipleOf16() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("1025x1024");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("16");
    }

    @Test
    void normalizeImageSizeRejectsTooManyPixels() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("3840x3840");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("8294400");
    }

    @Test
    void normalizeImageSizeRejectsAspectRatioOverThreeToOne() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("3840x1024");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("3:1");
    }

    private String normalizeImageSize(String value) throws Exception {
        Method method = OpenAiImageGenerationService.class.getDeclaredMethod("normalizeImageSize", String.class);
        method.setAccessible(true);
        try {
            return (String) method.invoke(null, value);
        } catch (InvocationTargetException exception) {
            Throwable cause = exception.getCause();
            if (cause instanceof ImageGenerationException) {
                throw (ImageGenerationException) cause;
            }
            throw exception;
        }
    }
}
```

- [ ] **Step 2: Run tests to verify RED**

Run: `mvn -pl imagetemplate -Dtest=OpenAiImageGenerationServiceTest test`

Expected: compile or test failure because `normalizeImageSize` does not exist.

- [ ] **Step 3: Implement size normalization**

In `OpenAiImageGenerationService`, add constants and a private static method:

```java
private static final String DEFAULT_IMAGE_SIZE = "1024x1024";

private static final int MAX_IMAGE_SIDE = 3840;

private static final int MIN_IMAGE_PIXELS = 655360;

private static final int MAX_IMAGE_PIXELS = 8294400;

private static String normalizeImageSize(String value) {
    String size = hasTextStatic(value) ? value.trim().toLowerCase(Locale.ROOT) : DEFAULT_IMAGE_SIZE;
    if (!size.matches("\\d+x\\d+")) {
        throw new ImageGenerationException("Image size must use WIDTHxHEIGHT format, for example 3840x2160.");
    }
    String[] parts = size.split("x");
    int width = parseImageSide(parts[0], "width");
    int height = parseImageSide(parts[1], "height");
    if (width % 16 != 0 || height % 16 != 0) {
        throw new ImageGenerationException("Image width and height must both be multiples of 16.");
    }
    if (width > MAX_IMAGE_SIDE || height > MAX_IMAGE_SIDE) {
        throw new ImageGenerationException("Image width and height must be 3840px or smaller.");
    }
    int longest = Math.max(width, height);
    int shortest = Math.min(width, height);
    if (longest > shortest * 3) {
        throw new ImageGenerationException("Image aspect ratio must not exceed 3:1.");
    }
    int pixels = width * height;
    if (pixels < MIN_IMAGE_PIXELS || pixels > MAX_IMAGE_PIXELS) {
        throw new ImageGenerationException("Image total pixels must be between 655360 and 8294400.");
    }
    return width + "x" + height;
}
```

Also add:

```java
private static int parseImageSide(String value, String name) {
    try {
        int side = Integer.parseInt(value);
        if (side <= 0) {
            throw new NumberFormatException("non-positive");
        }
        return side;
    } catch (NumberFormatException exception) {
        throw new ImageGenerationException("Image " + name + " must be a positive integer.", exception);
    }
}

private static boolean hasTextStatic(String value) {
    return value != null && !value.trim().isEmpty();
}
```

Replace all `normalizeOption(generationRequest.getSize(), "1024x1024")` usages with one local `String imageSize = normalizeImageSize(generationRequest.getSize())`, and pass `imageSize` into log/request body for both generation and edit flows.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `mvn -pl imagetemplate -Dtest=OpenAiImageGenerationServiceTest test`

Expected: all tests pass.

### Task 2: Direct Prompt Templates

**Files:**
- Modify: `imagetemplate/src/main/resources/templates/image-prompt-templates.json`
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java`

- [ ] **Step 1: Write failing template assertions**

Update `ImagePromptTemplateServiceTest`:

```java
assertThat(imagePromptTemplateService.listTemplates(null, null)).hasSize(29);
assertThat(imagePromptTemplateService.listCategories()).extracting("slug")
        .contains("character", "visual-design", "commerce", "editing", "direct-prompt");
assertThat(imagePromptTemplateService.listTemplates("direct-prompt", null)).hasSize(8);
```

Add a new test:

```java
@Test
void directPromptTemplatesHaveEmptyJsonTemplateAndUsablePrompt() {
    assertThat(imagePromptTemplateService.listTemplates("direct-prompt", null))
            .allSatisfy(template -> {
                assertThat(template.getJsonTemplate()).isEmpty();
                assertThat(template.getPromptTemplate()).isNotBlank();
                assertThat(template.getSourceUrl()).startsWith("https://github.com/");
            });
}
```

- [ ] **Step 2: Run tests to verify RED**

Run: `mvn -pl imagetemplate -Dtest=ImagePromptTemplateServiceTest test`

Expected: failures because template count and category do not yet include `direct-prompt`.

- [ ] **Step 3: Add eight direct-prompt templates**

Append eight JSON objects with unique ids:

- `direct-cinematic-product-hero`
- `direct-editorial-portrait`
- `direct-mobile-wallpaper`
- `direct-fantasy-environment`
- `direct-food-commercial`
- `direct-app-icon`
- `direct-isometric-tech-illustration`
- `direct-luxury-fashion-campaign`

Each object uses:

```json
"category": "直接提示词",
"categorySlug": "direct-prompt",
"jsonTemplate": {},
"sourceUrl": "https://github.com/ZeroLu/awesome-gpt-image"
```

Use polished image prompts in `promptTemplate`, written in Chinese with concrete scene, composition, lighting, style, and constraints.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `mvn -pl imagetemplate -Dtest=ImagePromptTemplateServiceTest test`

Expected: all tests pass.

### Task 3: Frontend Size and Direct Prompt UX

**Files:**
- Modify: `imagetemplate/src/main/resources/static/index.html`
- Modify: `imagetemplate/src/main/resources/static/js/app.js`
- Modify: `imagetemplate/src/main/resources/static/css/app.css`

- [ ] **Step 1: Add recommended and custom size controls**

In `index.html`, replace the size select options with recommended sizes and add a custom input:

```html
<select id="imageSizeSelect">
    <option value="1024x1024">1024 x 1024 · 1:1</option>
    <option value="2048x2048">2048 x 2048 · 1:1</option>
    <option value="1536x1024">1536 x 1024 · 3:2</option>
    <option value="1024x1536">1024 x 1536 · 2:3</option>
    <option value="1920x1088">1920 x 1088 · 16:9</option>
    <option value="2560x1440">2560 x 1440 · 2K 实验</option>
    <option value="3840x2160">3840 x 2160 · 4K 实验</option>
    <option value="1088x1920">1088 x 1920 · 9:16</option>
    <option value="1440x2560">1440 x 2560 · 竖屏实验</option>
    <option value="2160x3840">2160 x 3840 · 4K 竖屏实验</option>
    <option value="custom">自定义尺寸</option>
</select>
<input id="customImageSizeInput" type="text" placeholder="例如 1280x720" hidden>
<small id="imageSizeHint" class="size-hint"></small>
```

- [ ] **Step 2: Wire new DOM elements and validation**

In `app.js`, add elements:

```javascript
customImageSizeInput: document.getElementById('customImageSizeInput'),
imageSizeHint: document.getElementById('imageSizeHint'),
```

Add helper functions:

```javascript
function resolveImageSize() {
    if (elements.imageSizeSelect.value === 'custom') {
        return (elements.customImageSizeInput.value || '').trim();
    }
    return elements.imageSizeSelect.value;
}

function validateImageSize(size) {
    var match = /^(\d+)x(\d+)$/i.exec(size || '');
    if (!match) {
        return '尺寸格式必须是 宽x高，例如 3840x2160。';
    }
    var width = Number(match[1]);
    var height = Number(match[2]);
    if (width <= 0 || height <= 0) {
        return '宽高必须是正整数。';
    }
    if (width % 16 !== 0 || height % 16 !== 0) {
        return '宽高都必须是 16 的倍数。';
    }
    if (width > 3840 || height > 3840) {
        return '单边最大不能超过 3840px。';
    }
    if (Math.max(width, height) / Math.min(width, height) > 3) {
        return '宽高比不能超过 3:1。';
    }
    var pixels = width * height;
    if (pixels < 655360 || pixels > 8294400) {
        return '总像素必须在 655,360 到 8,294,400 之间。';
    }
    return '';
}

function isExperimentalImageSize(size) {
    var match = /^(\d+)x(\d+)$/i.exec(size || '');
    if (!match) {
        return false;
    }
    return Number(match[1]) * Number(match[2]) >= 2560 * 1440;
}

function updateImageSizeControls() {
    var isCustom = elements.imageSizeSelect.value === 'custom';
    elements.customImageSizeInput.hidden = !isCustom;
    var size = resolveImageSize();
    var error = validateImageSize(size);
    if (error) {
        elements.imageSizeHint.textContent = error;
        elements.imageSizeHint.classList.add('error');
        return;
    }
    elements.imageSizeHint.classList.remove('error');
    elements.imageSizeHint.textContent = isExperimentalImageSize(size)
        ? '当前为 2K/4K 实验尺寸，生成可能更慢，稳定性可能略低。'
        : '尺寸符合 GPT Image-2 规则。';
}
```

Use `resolveImageSize()` in `buildGenerationPayload` and `buildMultipartPayload`, and call `validateImageSize(resolveImageSize())` before generation.

- [ ] **Step 3: Add direct-prompt behavior**

In `renderDetail()`, after setting `promptTemplate`, add:

```javascript
if (template.categorySlug === 'direct-prompt') {
    elements.variablesInput.value = '{}';
    elements.renderedPrompt.value = template.promptTemplate || '';
    state.renderedPromptEdited = false;
} else {
    elements.variablesInput.value = buildVariableSeed(template.jsonTemplate);
    elements.renderedPrompt.value = '';
    state.renderedPromptEdited = false;
}
```

Ensure the previous unconditional `variablesInput` and `renderedPrompt` assignments are removed.

- [ ] **Step 4: Add CSS for custom size hint**

In `app.css`:

```css
.size-hint {
    display: block;
    min-height: 18px;
    margin-top: 6px;
    color: var(--muted);
    font-size: 12px;
    line-height: 1.4;
}

.size-hint.error {
    color: var(--warning);
}

#customImageSizeInput {
    margin-top: 8px;
}
```

- [ ] **Step 5: Verify frontend syntax and backend tests**

Run: `mvn -pl imagetemplate -am test`

Expected: all imagetemplate tests pass and static resources package successfully.

### Task 4: Manual Runtime Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Start imagetemplate**

Run: `mvn -pl imagetemplate -am spring-boot:run`

Expected: service starts on `http://localhost:8082/`.

- [ ] **Step 2: Verify APIs**

Run:

```powershell
curl.exe -s http://localhost:8082/api/image-templates/categories
curl.exe -s "http://localhost:8082/api/image-templates?category=direct-prompt"
```

Expected: categories contain `direct-prompt`; direct prompt response contains eight templates.

- [ ] **Step 3: Browser check**

Open `http://localhost:8082/`, verify:

- Size dropdown includes `3840 x 2160` and `2160 x 3840`.
- Custom size input appears only when “自定义尺寸” is selected.
- Invalid custom size shows a local error.
- Selecting a direct-prompt template fills the generated prompt area automatically.

---

## Self-Review Notes

- Spec coverage: backend validation, frontend controls, direct-prompt category, variable JSON positioning, and verification are covered.
- Placeholder scan: no TBD/TODO/fill-later placeholders.
- Type consistency: backend method names, DTO field names, DOM ids, and category slug are consistent across tasks.
