# Website Cinematic Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `website` landing page as a fullscreen cinematic service launcher while preserving authentication and health checks.

**Architecture:** Keep the existing Spring Boot static-resource architecture. HTML owns semantic structure and the eight service mappings, CSS owns the single-viewport liquid-glass presentation, and plain JavaScript owns video switching, mobile navigation, authentication, and service-health state.

**Tech Stack:** Java 8, Spring Boot 2.6.13 static resources, HTML5, CSS3, ES5-compatible browser JavaScript, JUnit 5.

---

### Task 1: Lock the page contract with a static-resource test

**Files:**
- Create: `website/src/test/java/com/example/website/HomepageStaticAssetsTest.java`

- [ ] **Step 1: Write a failing JUnit test**

  Load `static/index.html`, `static/css/style.css`, and `static/js/script.js` from the classpath. Assert the exact four video URLs, all eight `data-health-url` attributes, `data-scene-index="2"`, `liquid-glass`, `mobile-menu`, `setupVideoSwitcher`, `setupMobileMenu`, `setupAuth`, and `setupServiceHealth`.

- [ ] **Step 2: Verify the test fails**

  Run `mvn -pl website -am '-Dtest=HomepageStaticAssetsTest' -DfailIfNoTests=false test`.
  Expected: failure because the current homepage has only one video and no scene switcher/mobile menu contract.

### Task 2: Replace the semantic homepage

**Files:**
- Modify: `website/src/main/resources/static/index.html`

- [ ] **Step 1: Build the four-layer video background**

  Add four `<video>` elements with the supplied CDN URLs, labels, poster/fallback behavior, and a decorative PNG overlay.

- [ ] **Step 2: Build the content shell**

  Add a desktop navigation pill, accessible mobile menu, centered Chinese hero copy, primary service action, scene switcher, and eight service cards with their current ports and health URLs.

- [ ] **Step 3: Preserve authentication**

  Keep login/register/logout actions and the protected image-template link contract using `data-auth-required="true"`.

### Task 3: Implement the visual system

**Files:**
- Modify: `website/src/main/resources/static/css/style.css`

- [ ] **Step 1: Add layout and typography tokens**

  Use Instrument Serif for display type and system UI for controls. Make the page exactly one `100svh` viewport with black fallback.

- [ ] **Step 2: Add liquid glass and cinematic layers**

  Implement `.liquid-glass`, its masked gradient border, the transparent-overlay bob animation, video crossfades, and Deep Woods hero-color transition.

- [ ] **Step 3: Add responsive and accessible states**

  Add desktop/mobile navigation behavior, horizontally scrollable service dock, visible focus states, 44px touch targets, mobile-menu stagger animations, and reduced-motion overrides.

### Task 4: Implement interaction behavior

**Files:**
- Modify: `website/src/main/resources/static/js/script.js`

- [ ] **Step 1: Add the guarded scene switcher**

  Track active scene and a 1000ms transition lock, update `aria-pressed`, active classes, video playback, and the `scene-deep-woods` body class.

- [ ] **Step 2: Add the mobile navigation controller**

  Toggle the menu and icon states, keep `aria-expanded` synchronized, close on Escape/link selection, and restore focus to the trigger.

- [ ] **Step 3: Reconnect existing behavior**

  Retain the `/api/auth/**` login flow, protected-link continuation, video readiness, and 30-second service health checks with corrected Chinese status text.

- [ ] **Step 4: Verify the focused test passes**

  Run `mvn -pl website -am '-Dtest=HomepageStaticAssetsTest' -DfailIfNoTests=false test`.
  Expected: all homepage contract assertions pass.

### Task 5: Synchronize documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `website/README.md`
- Modify: `website/AGENTS.md`

- [ ] **Step 1: Document the new homepage**

  Record the four-scene cinematic background, liquid-glass service dock, eight health-aware entries, mobile menu, and unchanged service addresses.

### Task 6: Full verification

**Files:**
- Verify only

- [ ] **Step 1: Run the full website regression**

  Run `mvn -pl website -am test '-Dmaven.repo.local=D:\Code\Java_Code\love530\.m2'`.
  Expected: Maven exits 0 with zero test failures.

- [ ] **Step 2: Inspect in a real browser**

  Serve the page from the Spring Boot app or a local static server. Verify 1440×900 and 390×844 screenshots, scene switching, Deep Woods color, mobile menu, focus behavior, service links, and no horizontal body overflow.

