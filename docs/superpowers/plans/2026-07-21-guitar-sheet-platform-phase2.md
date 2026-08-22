# Guitar 吉他谱平台第二期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在第一期用户端闭环之上交付用户封禁、完整管理后台、每日统计聚合、趋势展示和可查询审计记录。

**Architecture:** 第二期不改变 Guitar 单体分层边界，复用第一期表结构、Session、DAO + MyBatis XML 和前端基础模块。写请求通过数据库状态守卫即时识别已封禁用户；统计使用可重算的每日聚合表，不保存无限增长的访问明细。

**Tech Stack:** Java 8、Spring Boot 2.6.13、Spring MVC、MyBatis、MySQL 5.7+、JUnit 5、Mockito、MockMvc、原生 HTML/CSS/JavaScript、Node.js、Playwright CLI

**Prerequisite:** `docs/superpowers/plans/2026-07-21-guitar-sheet-platform-phase1.md` completion gate is fully satisfied.

**Design:** `docs/superpowers/specs/2026-07-21-guitar-sheet-platform-design.md`

---

## File Map

### User Administration

- Modify: `guitar/src/main/java/com/example/guitar/user/dao/GuitarUserDao.java`.
- Modify: `guitar/src/main/resources/mapper/user/GuitarUserMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/admin/dto/AdminUserSearchRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/dto/UserBanRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/vo/AdminUserResponse.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/service/UserAdminService.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/service/UserAdminServiceImpl.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/controller/UserAdminController.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/web/ActiveUserGuard.java`.
- Modify: `guitar/src/main/java/com/example/guitar/auth/web/GuitarAuthInterceptor.java`.

### Audit And Statistics

- Modify: `guitar/src/main/java/com/example/guitar/admin/dao/AdminActionLogDao.java`.
- Modify: `guitar/src/main/resources/mapper/admin/AdminActionLogMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/admin/dto/AuditLogSearchRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/service/AdminAuditService.java`.
- Create: `guitar/src/main/java/com/example/guitar/statistics/model/GuitarDailyStat.java`.
- Create: `guitar/src/main/java/com/example/guitar/statistics/dao/GuitarStatisticsDao.java`.
- Create: `guitar/src/main/resources/mapper/statistics/GuitarStatisticsMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/statistics/service/GuitarStatisticsService.java`.
- Create: `guitar/src/main/java/com/example/guitar/statistics/service/GuitarStatisticsServiceImpl.java`.
- Create: `guitar/src/main/java/com/example/guitar/statistics/job/GuitarDailyStatisticsJob.java`.
- Create: `guitar/src/main/java/com/example/guitar/statistics/controller/GuitarStatisticsController.java`.

### Frontend And Documentation

- Modify: `guitar/src/main/resources/static/admin.html`.
- Modify: `guitar/src/main/resources/static/js/admin.js`.
- Modify: `guitar/src/main/resources/static/css/app.css`.
- Modify: `AGENTS.md`.
- Modify: `README.md`.
- Modify: `guitar/AGENTS.md`.
- Modify: `guitar/README.md`.

---

### Task 1: Add Immediate Banned-User Enforcement

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/auth/web/ActiveUserGuard.java`
- Modify: `guitar/src/main/java/com/example/guitar/auth/web/GuitarAuthInterceptor.java`
- Modify: `guitar/src/main/java/com/example/guitar/user/dao/GuitarUserDao.java`
- Modify: `guitar/src/main/resources/mapper/user/GuitarUserMapper.xml`
- Create: `guitar/src/test/java/com/example/guitar/auth/web/ActiveUserGuardTest.java`
- Modify: `guitar/src/test/java/com/example/guitar/auth/service/GuitarAuthServiceImplTest.java`

- [ ] **Step 1: Write failing tests for active and stale sessions**

Test these exact cases:

- `ENABLED` user may execute a write request;
- `BANNED` user with a pre-existing Session receives `USER_BANNED` immediately;
- expired temporary ban is treated as enabled and cleared in MySQL;
- deleted/missing user invalidates Session and receives `AUTH_REQUIRED`;
- a banned user cannot log in.

The stale-session assertion must call the guard after putting an enabled-looking principal in Session, while the DAO returns `BANNED`:

```java
request.getSession(true).setAttribute("GUITAR_AUTH_USER", principal);
when(userDao.findById(principal.getId())).thenReturn(bannedUser);

assertThatThrownBy(() -> guard.requireActive(request))
        .isInstanceOf(GuitarApiException.class)
        .extracting("code")
        .isEqualTo("USER_BANNED");
```

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=ActiveUserGuardTest,GuitarAuthServiceImplTest -DfailIfNoTests=false test
```

Expected: FAIL because `ActiveUserGuard` and ban-expiry DAO methods do not exist.

- [ ] **Step 3: Implement the database-backed guard**

`ActiveUserGuard.requireActive(request)` must:

1. load the principal from Session;
2. query `guitar_user` by ID;
3. invalidate Session when the user is missing;
4. if `status=BANNED` and `ban_expires_at` is null or future, throw `USER_BANNED`;
5. if the expiry is past, atomically clear ban fields and return an updated principal;
6. update the Session principal when nickname, avatar or role changed.

Add DAO method:

```java
int clearExpiredBan(@Param("id") Long id, @Param("now") LocalDateTime now);
```

Its SQL must include `status = 'BANNED' AND ban_expires_at IS NOT NULL AND ban_expires_at <= #{now}` so concurrent requests remain safe.

- [ ] **Step 4: Wire the guard into every authenticated write**

`GuitarAuthInterceptor` invokes the guard for authenticated POST/PUT/PATCH/DELETE requests before the Controller. GET profile/admin endpoints also use the guard so a banned Session cannot read private data.

- [ ] **Step 5: Run and commit**

```bash
mvn -pl guitar -am -Dtest=ActiveUserGuardTest,GuitarAuthServiceImplTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/auth guitar/src/main/java/com/example/guitar/user guitar/src/main/resources/mapper/user guitar/src/test/java/com/example/guitar/auth
git commit -m "feat(guitar): enforce user bans for active sessions"
```

---

### Task 2: Implement Administrator User Search, Ban, And Unban

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/admin/dto/AdminUserSearchRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/dto/UserBanRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/vo/AdminUserResponse.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/service/UserAdminService.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/service/UserAdminServiceImpl.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/controller/UserAdminController.java`
- Modify user DAO and XML.
- Create: `guitar/src/test/java/com/example/guitar/admin/service/UserAdminServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/admin/controller/UserAdminControllerTest.java`

- [ ] **Step 1: Write failing user-administration tests**

Cover paginated search by phone/nickname/status/role, size cap 50, required 1-500 character ban reason, permanent and expiring bans, unban, self-ban rejection, last-ADMIN protection, duplicate transitions and audit rows.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=UserAdminServiceTest,UserAdminControllerTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Add parameterized user queries**

DAO contract:

```java
List<GuitarUser> searchForAdmin(AdminUserSearchRequest request);
long countForAdmin(AdminUserSearchRequest request);
int ban(@Param("id") Long id, @Param("reason") String reason,
        @Param("adminId") Long adminId, @Param("bannedAt") LocalDateTime bannedAt,
        @Param("expiresAt") LocalDateTime expiresAt);
int unban(@Param("id") Long id);
long countEnabledAdmins();
```

Use fixed sort `create_time DESC, id DESC` and parameterized filters.

- [ ] **Step 4: Implement safe state transitions**

`ban` accepts only `ENABLED -> BANNED`. `unban` accepts only `BANNED -> ENABLED`. Reject an administrator banning their own account with `ADMIN_SELF_BAN_FORBIDDEN`. If the target is an ADMIN and only one enabled administrator remains, reject with `LAST_ADMIN_REQUIRED`.

Write the user update and `guitar_admin_action_log` insert in one transaction.

- [ ] **Step 5: Expose APIs**

```text
GET  /api/admin/users
POST /api/admin/users/{id}/ban
POST /api/admin/users/{id}/unban
```

`UserBanRequest` contains `reason` and optional ISO-8601 `expiresAt`. Reject expiry values not later than server time.

- [ ] **Step 6: Run and commit**

```bash
mvn -pl guitar -am -Dtest=UserAdminServiceTest,UserAdminControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/admin guitar/src/main/java/com/example/guitar/user guitar/src/main/resources/mapper/user guitar/src/test/java/com/example/guitar/admin
git commit -m "feat(guitar): add user administration"
```

---

### Task 3: Add Queryable Administrator Audit Logs

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/admin/dto/AuditLogSearchRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/service/AdminAuditService.java`
- Modify: `guitar/src/main/java/com/example/guitar/admin/dao/AdminActionLogDao.java`
- Modify: `guitar/src/main/resources/mapper/admin/AdminActionLogMapper.xml`
- Create: `guitar/src/test/java/com/example/guitar/admin/service/AdminAuditServiceTest.java`

- [ ] **Step 1: Write failing audit query tests**

Cover filters for administrator ID, action type, target type, target ID and inclusive date range. Test default size 20, maximum 50, newest-first order and invalid date ranges.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=AdminAuditServiceTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement audit search**

DAO contract:

```java
List<AdminActionLog> search(AuditLogSearchRequest request);
long count(AuditLogSearchRequest request);
```

Return administrator nickname/phone by joining `guitar_user`. Keep target IDs and before/after states from the audit record even if the target is now soft-deleted.

- [ ] **Step 4: Expose and test**

Add `GET /api/admin/audit-logs` to an admin controller. Validate `startDate <= endDate` and cap a range to 366 days.

- [ ] **Step 5: Commit**

```bash
git add guitar/src/main/java/com/example/guitar/admin guitar/src/main/resources/mapper/admin guitar/src/test/java/com/example/guitar/admin
git commit -m "feat(guitar): add audit log queries"
```

---

### Task 4: Implement Idempotent Daily Statistics

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/statistics/model/GuitarDailyStat.java`
- Create: `guitar/src/main/java/com/example/guitar/statistics/dao/GuitarStatisticsDao.java`
- Create: `guitar/src/main/resources/mapper/statistics/GuitarStatisticsMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/statistics/service/GuitarStatisticsService.java`
- Create: `guitar/src/main/java/com/example/guitar/statistics/service/GuitarStatisticsServiceImpl.java`
- Create: `guitar/src/main/java/com/example/guitar/statistics/job/GuitarDailyStatisticsJob.java`
- Create: `guitar/src/main/java/com/example/guitar/statistics/controller/GuitarStatisticsController.java`
- Create: `guitar/src/test/java/com/example/guitar/statistics/service/GuitarStatisticsServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/statistics/job/GuitarDailyStatisticsJobTest.java`
- Create: `guitar/src/test/java/com/example/guitar/statistics/controller/GuitarStatisticsControllerTest.java`

- [ ] **Step 1: Write failing aggregation tests**

For a supplied `LocalDate`, verify counts use `[startOfDay, nextDayStart)` for:

- users created;
- sheets uploaded;
- favorites created;
- sheets offlined.

Seed `sheet_view_count` as the durable value written by the phase-one detail endpoint. Verify running aggregation twice updates the other columns, preserves `sheet_view_count`, and produces identical values.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=GuitarStatisticsServiceTest,GuitarDailyStatisticsJobTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement aggregation queries and upsert**

DAO contract:

```java
long countNewUsers(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
long countNewSheets(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
long countNewFavorites(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
long countOfflinedSheets(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
int upsertDailyStat(GuitarDailyStat stat);
List<GuitarDailyStat> findRange(@Param("startDate") LocalDate startDate,
                                @Param("endDate") LocalDate endDate);
```

Use `INSERT ... ON DUPLICATE KEY UPDATE` keyed by `stat_date`. Its update clause sets `new_user_count`, `uploaded_sheet_count`, `favorite_count` and `offline_sheet_count` but deliberately does not overwrite `sheet_view_count`. Views are incremented online in the same database as sheet detail access, so no per-view event table is required.

- [ ] **Step 4: Implement scheduled aggregation and bounded recovery**

The scheduled job runs daily at 00:10 Asia/Shanghai. It recomputes the previous seven calendar days in oldest-first order, so a transient failure is retried without a separate queue. `GuitarStatisticsService.recompute(LocalDate)` remains a service method used by the job and tests; it is not exposed as a public HTTP API. One failed date is logged and does not prevent the remaining dates from running.

- [ ] **Step 5: Expose overview and trends**

`GET /api/admin/statistics/overview` returns current totals plus today and previous-day values. `GET /api/admin/statistics/trends?startDate=&endDate=` returns at most 366 daily rows and fills missing dates with zeros in Service.

- [ ] **Step 6: Run and commit**

```bash
mvn -pl guitar -am -Dtest=GuitarStatisticsServiceTest,GuitarDailyStatisticsJobTest,GuitarStatisticsControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/statistics guitar/src/main/resources/mapper/statistics guitar/src/test/java/com/example/guitar/statistics
git commit -m "feat(guitar): add daily platform statistics"
```

---

### Task 5: Build The Complete Administrator UI

**Required skills during execution:** `ui-ux-pro-max`, then `playwright-cli`.

**Files:**
- Modify: `guitar/src/main/resources/static/admin.html`
- Modify: `guitar/src/main/resources/static/js/admin.js`
- Modify: `guitar/src/main/resources/static/css/app.css`
- Create: `guitar/src/test/js/admin-users.test.js`
- Create: `guitar/src/test/js/admin-statistics.test.js`

- [ ] **Step 1: Invoke the UI skill and extend the existing design system**

Use `ui-ux-pro-max` without replacing the phase-one visual language. Add restrained dashboard data visualization colors that remain distinguishable from normal/offline/danger status colors.

- [ ] **Step 2: Write failing frontend state tests**

Test user query serialization, ban expiry validation, self-ban button suppression, audit filters, date range validation, zero-filled trend points and API error recovery.

- [ ] **Step 3: Add admin tabs**

Use tabs for:

```text
曲谱管理
用户管理
数据概览
审计日志
```

User rows expose ban/unban commands with a confirmation modal, reason and optional expiry. Never place destructive actions directly adjacent without spacing and confirmation.

- [ ] **Step 4: Add statistics**

Use compact metric bands for current totals and an unframed line/bar chart area for daily trends. Add accessible table fallback containing the same values. Do not use decorative chart data.

- [ ] **Step 5: Add audit log view**

Provide filters, paginated rows, before/after state display and readable timestamps. Long reasons wrap without expanding action columns.

- [ ] **Step 6: Verify with Playwright**

At 1440x900, 1024x768 and 390x844:

- ban and unban a user;
- confirm a stale Session loses write access;
- filter audit rows;
- change statistics range;
- verify charts are nonblank and table fallback is reachable;
- verify no overlap, clipped text or horizontal page scrolling.

- [ ] **Step 7: Run tests and commit**

```bash
node guitar/src/test/js/admin-users.test.js
node guitar/src/test/js/admin-statistics.test.js
git add guitar/src/main/resources/static/admin.html guitar/src/main/resources/static/js/admin.js guitar/src/main/resources/static/css/app.css guitar/src/test/js
git commit -m "feat(guitar): complete administration UI"
```

---

### Task 6: Synchronize Documentation And Run Phase-Two Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `guitar/AGENTS.md`
- Modify: `guitar/README.md`

- [ ] **Step 1: Update documentation**

Document user ban semantics, existing-Session invalidation, admin user APIs, statistics APIs, audit API, daily job schedule, recompute behavior and administrator UI.

- [ ] **Step 2: Run all Guitar tests**

```bash
mvn -pl common,guitar -am test
node guitar/src/test/js/api.test.js
node guitar/src/test/js/auth-validation.test.js
node guitar/src/test/js/sheet-search.test.js
node guitar/src/test/js/upload-validation.test.js
node guitar/src/test/js/favorite-state.test.js
node guitar/src/test/js/admin-users.test.js
node guitar/src/test/js/admin-statistics.test.js
```

Expected: every command exits 0 and Maven reports zero failures/errors.

- [ ] **Step 3: Run end-to-end role and statistics checks**

Using isolated local test data:

1. register USER and ADMIN accounts;
2. promote ADMIN with the documented SQL;
3. ban USER while USER has an active Session;
4. prove the next USER write receives `USER_BANNED`;
5. unban and log in again;
6. recompute a date twice and compare identical rows;
7. inspect matching audit entries.

- [ ] **Step 4: Run Playwright desktop/mobile verification**

Capture the final user and admin workflows without committing screenshots. Verify charts have rendered pixels, tables are readable, modals trap focus and all long Chinese text wraps correctly.

- [ ] **Step 5: Review repository safety**

```bash
git diff --check
git status --short
git diff --name-only
```

Confirm no database password, OSS key, real phone, runtime log, uploaded sheet, avatar, `target/` or browser artifact is tracked.

- [ ] **Step 6: Commit documentation**

```bash
git add AGENTS.md README.md guitar/AGENTS.md guitar/README.md
git commit -m "docs: document guitar sheet platform phase two"
```

---

## Final Completion Gate

The full two-phase platform is complete only when:

- all phase-one and phase-two checkboxes are complete;
- fresh Maven, Node and Playwright verification passes;
- active Sessions respect bans immediately;
- administrator state changes create audit rows in the same transaction;
- daily aggregation is idempotent and missing dates render as zero;
- MySQL stores object keys rather than public OSS URLs;
- root and Guitar documentation match code, DDL, APIs and operational commands.
