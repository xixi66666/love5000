# ImageTemplate Template Gallery Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the homepage template selection area so browsing templates dominates the discover scene on desktop while remaining readable and naturally scrollable on mobile.

**Architecture:** Preserve the existing four-scene application and JavaScript state flow. Reshape only the discover scene with semantic HTML classes and responsive CSS: a compact horizontal summary above a full-width gallery, one-line scrollable category filters, and a 2/3/4-column template grid selected by viewport width. Apply RunwayML's exact dark neutrals, small radii, minimal borders, single sans-serif hierarchy, and zero card shadows to the discover scene.

**Tech Stack:** Java 8, JUnit 5, AssertJ, static HTML, CSS, vanilla JavaScript, Maven, Playwright CLI.

---

### Task 1: Add a failing layout regression test

**Files:**
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

- [ ] **Step 1: Add a focused test for the expanded selection area**

```java
@Test
void discoverScenePrioritizesTheTemplateSelectionArea() throws Exception {
    String html = read("static/index.html");
    String css = read("static/css/app.css");

    assertThat(html)
            .contains("class=\"discover-summary\"")
            .contains("class=\"discover-summary-copy\"")
            .contains("class=\"discover-summary-actions\"");
    assertThat(css)
            .contains("grid-template-rows: auto minmax(0, 1fr);")
            .contains("grid-template-columns: minmax(0, 1fr);")
            .contains("grid-template-columns: repeat(4, minmax(0, 1fr));")
            .contains("overflow-x: auto;")
            .contains("scrollbar-width: thin;");
}
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: the new test fails because `discover-summary` and the new full-width layout rules do not exist yet.

### Task 2: Expand the discover scene

**Files:**
- Modify: `imagetemplate/src/main/resources/static/index.html`
- Modify: `imagetemplate/src/main/resources/static/css/app.css`

- [ ] **Step 1: Convert the large left intro into a compact summary header**

Rename the discover intro wrapper to `discover-summary`, group the kicker/title/lead in `discover-summary-copy`, and group the primary action plus collection metadata in `discover-summary-actions`. Keep every existing ID, button target, link and displayed value unchanged.

- [ ] **Step 2: Make the gallery consume the discover scene**

Implement the following layout contract in `app.css`:

```css
.discover-layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
    height: 100%;
    min-height: 0;
}

.discover-summary {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
}

.gallery-panel {
    height: 100%;
    min-height: 0;
}
```

Use compact typography and spacing so the summary does not compete with the gallery. Keep the black-gold visual language and existing focus styles.

- [ ] **Step 3: Compact the filters and expand the template grid**

Change `.function-filters` to a single flex row with horizontal overflow and stable button widths. Use two columns by default, three columns from ordinary desktop widths, and four columns from wide desktop widths. Preserve the existing one-column mobile breakpoint.

- [ ] **Step 4: Keep tablet and mobile scrolling coherent**

At `max-width: 900px`, return the discover layout to natural height, stack the summary, remove the nested template list height cap, and let the scene scroll vertically. At `max-width: 620px`, keep the existing select-based category control and one-column cards.

- [ ] **Step 5: Run the focused test and confirm GREEN**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: all tests in `ImageTemplateHomepageStaticAssetsTest` pass.

### Task 3: Verify behavior and responsive layout

**Files:**
- Verify: `imagetemplate/src/main/resources/static/index.html`
- Verify: `imagetemplate/src/main/resources/static/css/app.css`

- [ ] **Step 1: Run the complete module test suite**

Run:

```powershell
mvn -pl imagetemplate -am test
```

Expected: Maven exits with code 0 and reports no test failures.

- [ ] **Step 2: Start or reuse the local service**

Run the module on port `8082` if `/api/health` is not already healthy:

```powershell
mvn -pl imagetemplate -am spring-boot:run
```

Expected health response: top-level `success=true` and `service=imagetemplate`.

- [ ] **Step 3: Inspect desktop and mobile viewports with Playwright**

At `1920x1080`, `1366x768`, `900x900`, and `390x844`, verify:

- the discover gallery uses the available width;
- the desktop grid shows 4 columns on wide screens and at least 2 columns on ordinary desktop;
- a 1366x768 viewport hides the auxiliary summary and shows 3 columns by 2 complete rows;
- category filters scroll horizontally without expanding into multiple rows;
- mobile cards are one column and the full list remains reachable;
- selecting a card, activating “解构已选模板”, and returning preserves the selected card;
- there is no document-level horizontal overflow or console error.

- [ ] **Step 4: Review the final diff**

Run:

```powershell
git diff --check
git diff -- imagetemplate/src/main/resources/static/index.html imagetemplate/src/main/resources/static/css/app.css imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
```

Expected: no whitespace errors and no changes outside the approved discover-scene scope.
