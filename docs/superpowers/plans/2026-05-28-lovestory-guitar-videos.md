# Lovestory Guitar Videos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Memory Cards section with guitar video cards backed by MySQL records and OSS video uploads.

**Architecture:** Add a focused guitar video backend: Controller handles HTTP parameters, Service handles validation, OSS upload/delete, and response shaping, DAO/XML Mapper handles MySQL access. The existing `index.html` section is replaced with a card grid, upload modal, and playback modal that call `/api/guitar-videos`.

**Tech Stack:** Java 8, Spring Boot 2.6.13, MyBatis XML Mapper, MySQL, Aliyun OSS utility from `common`, vanilla HTML/CSS/JavaScript.

---

### Task 1: Backend API and Tests

**Files:**
- Create: `lovestory/src/main/java/com/ycxandwuqian/love/model/GuitarVideoRecord.java`
- Create: `lovestory/src/main/java/com/ycxandwuqian/love/dao/GuitarVideoDao.java`
- Create: `lovestory/src/main/java/com/ycxandwuqian/love/service/GuitarVideoService.java`
- Create: `lovestory/src/main/java/com/ycxandwuqian/love/service/GuitarVideoServiceImpl.java`
- Create: `lovestory/src/main/java/com/ycxandwuqian/love/controller/GuitarVideoController.java`
- Create: `lovestory/src/main/resources/mapper/GuitarVideoMapper.xml`
- Create: `lovestory/src/test/java/com/ycxandwuqian/love/service/GuitarVideoServiceImplTests.java`
- Modify: `lovestory/src/test/java/com/ycxandwuqian/love/LovestoryApplicationTests.java`

- [ ] **Step 1: Write failing service tests**

Test list response ordering shape, valid upload behavior, blank title rejection, unsupported video rejection, and deletion of OSS objects plus database row.

- [ ] **Step 2: Run tests and verify RED**

Run: `mvn -pl lovestory -Dtest=GuitarVideoServiceImplTests test`
Expected: compilation fails because guitar video classes do not exist yet.

- [ ] **Step 3: Implement backend classes**

Use `GuitarVideoService` as the boundary. Store OSS URLs in `video_url` and `cover_url`; use `OssUtil.delete(url)` when deleting.

- [ ] **Step 4: Run service tests and verify GREEN**

Run: `mvn -pl lovestory -Dtest=GuitarVideoServiceImplTests test`
Expected: tests pass.

- [ ] **Step 5: Run lovestory tests**

Run: `mvn -pl lovestory -am test`
Expected: existing tests and new service tests pass.

### Task 2: Frontend Module Replacement

**Files:**
- Modify: `lovestory/src/main/resources/static/index.html`

- [ ] **Step 1: Replace Memory Cards markup**

Remove the `甜蜜回忆 · Memory Cards` heading, card stack, and shuffle controls. Add `吉他小剧场 · Guitar Videos` with a video card grid, upload trigger, upload modal, and player modal.

- [ ] **Step 2: Add scoped CSS**

Add styles for video cards, empty state, upload modal, player modal, and responsive layout without changing unrelated sections.

- [ ] **Step 3: Add JavaScript**

Load `GET /api/guitar-videos`, render cards, call `POST /api/guitar-videos/upload` with `FormData`, open the player modal on card click, and call `DELETE /api/guitar-videos/{id}` from the player modal for uploaded videos.

- [ ] **Step 4: Verify static integration**

Run `mvn -pl lovestory -am test` to catch resource or Java regressions, then start `lovestory` and manually verify `http://localhost:8081/`.

### Task 3: Final Verification

**Files:**
- All touched files from Task 1 and Task 2

- [ ] **Step 1: Run targeted tests**

Run: `mvn -pl lovestory -Dtest=GuitarVideoServiceImplTests test`
Expected: PASS.

- [ ] **Step 2: Run module tests**

Run: `mvn -pl lovestory -am test`
Expected: PASS.

- [ ] **Step 3: Browser smoke test**

Start `lovestory`, open `http://localhost:8081/`, confirm video section renders and no major layout overlap.
