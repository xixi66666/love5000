# Guitar 吉他谱平台第一期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `guitar` 模块交付手机号账号、公开曲谱检索与预览、OSS 上传与个人管理、多收藏夹、管理员下架恢复，以及完整响应式前端。

**Architecture:** `guitar` 使用 Spring Boot 单体分层架构，业务代码留在 `com.example.guitar`，数据库访问使用 DAO + MyBatis XML。手机号认证由 Guitar 自己实现，复用 `common` 的 BCrypt 与 OSS 能力；数据库只保存 OSS object key，通过独立 URL 服务生成公共读地址。

**Tech Stack:** Java 8、Spring Boot 2.6.13、Spring MVC、MyBatis 2.2.2、MySQL 5.7+、Druid、Aliyun OSS SDK、JUnit 5、Mockito、MockMvc、原生 HTML/CSS/JavaScript、Node.js、Playwright CLI

**Design:** `docs/superpowers/specs/2026-07-21-guitar-sheet-platform-design.md`

---

## File Map

### Build And Configuration

- Modify: `guitar/pom.xml` - add `common`, MySQL and Druid dependencies.
- Modify: `guitar/src/main/java/com/example/guitar/GuitarApplication.java` - enable data source/MyBatis and scheduling.
- Delete: `guitar/src/main/resources/application.properties`.
- Create: `guitar/src/main/resources/application.yml` - environment-backed database, session, multipart and OSS settings.
- Create: `guitar/src/main/resources/db/guitar-schema.sql` - one-time MySQL DDL for both phases.
- Create: `guitar/src/test/resources/application.yml` - H2 and OSS-disabled test isolation.

### Authentication And Users

- Create: `guitar/src/main/java/com/example/guitar/user/model/GuitarUser.java`.
- Create: `guitar/src/main/java/com/example/guitar/user/dao/GuitarUserDao.java`.
- Create: `guitar/src/main/resources/mapper/user/GuitarUserMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/auth/dto/RegisterRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/dto/LoginRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/model/GuitarUserPrincipal.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/service/GuitarAuthService.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/service/GuitarAuthServiceImpl.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/controller/GuitarAuthController.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/web/GuitarAuthInterceptor.java`.
- Create: `guitar/src/main/java/com/example/guitar/auth/web/CsrfTokenService.java`.
- Create: `guitar/src/main/java/com/example/guitar/config/GuitarWebConfig.java`.
- Create: `guitar/src/main/java/com/example/guitar/user/service/GuitarUserService.java`.
- Create: `guitar/src/main/java/com/example/guitar/user/controller/GuitarUserController.java`.

### Sheets And OSS

- Create: `guitar/src/main/java/com/example/guitar/sheet/model/GuitarSheet.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/GuitarSheetFile.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/FileMode.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/SheetStatus.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/SheetType.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/SheetDifficulty.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/dto/SheetSearchRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/dto/SheetSaveRequest.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/vo/SheetSummaryResponse.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/vo/SheetDetailResponse.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetDao.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetFileDao.java`.
- Create: `guitar/src/main/resources/mapper/sheet/GuitarSheetMapper.xml`.
- Create: `guitar/src/main/resources/mapper/sheet/GuitarSheetFileMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/SheetFileValidator.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/SheetFileUrlService.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/PublicOssSheetFileUrlService.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetService.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetServiceImpl.java`.
- Create: `guitar/src/main/java/com/example/guitar/sheet/controller/GuitarSheetController.java`.

### Cleanup, Favorites, And Admin

- Create: `guitar/src/main/java/com/example/guitar/storage/model/OssCleanupTask.java`.
- Create: `guitar/src/main/java/com/example/guitar/storage/dao/OssCleanupTaskDao.java`.
- Create: `guitar/src/main/resources/mapper/storage/OssCleanupTaskMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/storage/service/OssCleanupService.java`.
- Create: `guitar/src/main/java/com/example/guitar/favorite/model/FavoriteFolder.java`.
- Create: `guitar/src/main/java/com/example/guitar/favorite/dao/FavoriteDao.java`.
- Create: `guitar/src/main/resources/mapper/favorite/FavoriteMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/favorite/service/FavoriteService.java`.
- Create: `guitar/src/main/java/com/example/guitar/favorite/controller/FavoriteController.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/model/AdminActionLog.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/dao/AdminActionLogDao.java`.
- Create: `guitar/src/main/resources/mapper/admin/AdminActionLogMapper.xml`.
- Create: `guitar/src/main/java/com/example/guitar/admin/service/SheetAdminService.java`.
- Create: `guitar/src/main/java/com/example/guitar/admin/controller/SheetAdminController.java`.
- Create: `guitar/src/main/java/com/example/guitar/web/ApiResponse.java`.
- Create: `guitar/src/main/java/com/example/guitar/web/GuitarApiException.java`.
- Create: `guitar/src/main/java/com/example/guitar/web/ApiExceptionHandler.java`.

### Frontend

- Replace: `guitar/src/main/resources/static/index.html`.
- Create: `guitar/src/main/resources/static/sheet.html`.
- Create: `guitar/src/main/resources/static/auth.html`.
- Create: `guitar/src/main/resources/static/upload.html`.
- Create: `guitar/src/main/resources/static/favorites.html`.
- Create: `guitar/src/main/resources/static/profile.html`.
- Create: `guitar/src/main/resources/static/admin.html`.
- Create: `guitar/src/main/resources/static/css/app.css`.
- Create: `guitar/src/main/resources/static/js/api.js`.
- Create: `guitar/src/main/resources/static/js/session.js`.
- Create: `guitar/src/main/resources/static/js/index.js`.
- Create: `guitar/src/main/resources/static/js/sheet.js`.
- Create: `guitar/src/main/resources/static/js/auth.js`.
- Create: `guitar/src/main/resources/static/js/upload.js`.
- Create: `guitar/src/main/resources/static/js/favorites.js`.
- Create: `guitar/src/main/resources/static/js/profile.js`.
- Create: `guitar/src/main/resources/static/js/admin.js`.
- Create: `guitar/package.json`.

---

### Task 1: Add The Database Schema And Runtime Configuration

**Files:**
- Modify: `guitar/pom.xml`
- Modify: `guitar/src/main/java/com/example/guitar/GuitarApplication.java`
- Delete: `guitar/src/main/resources/application.properties`
- Create: `guitar/src/main/resources/application.yml`
- Create: `guitar/src/main/resources/db/guitar-schema.sql`
- Create: `guitar/src/test/resources/application.yml`
- Create: `guitar/src/test/java/com/example/guitar/schema/GuitarSchemaSqlTest.java`

- [ ] **Step 1: Write a failing schema contract test**

Create `GuitarSchemaSqlTest` that reads `classpath:db/guitar-schema.sql` and asserts all eight table names, `utf8mb4`, the phone unique index, the favorite unique index, and the administrator update example:

```java
class GuitarSchemaSqlTest {
    @Test
    void schemaContainsBothDeliveryPhases() throws Exception {
        String sql = new String(Files.readAllBytes(
                Paths.get("src/main/resources/db/guitar-schema.sql")), StandardCharsets.UTF_8)
                .toLowerCase(Locale.ROOT);
        assertThat(sql).contains("create database if not exists guitar")
                .contains("create table if not exists guitar_user")
                .contains("create table if not exists guitar_sheet")
                .contains("create table if not exists guitar_sheet_file")
                .contains("create table if not exists guitar_favorite_folder")
                .contains("create table if not exists guitar_favorite")
                .contains("create table if not exists guitar_admin_action_log")
                .contains("create table if not exists guitar_oss_cleanup_task")
                .contains("create table if not exists guitar_daily_stat")
                .contains("uk_guitar_user_phone")
                .contains("uk_guitar_favorite")
                .contains("where phone = '<registered-phone>'")
                .contains("default character set utf8mb4");
    }
}
```

- [ ] **Step 2: Run the schema test and verify RED**

Run:

```bash
mvn -pl guitar -am -Dtest=GuitarSchemaSqlTest -DfailIfNoTests=false test
```

Expected: FAIL because `guitar-schema.sql` does not exist.

- [ ] **Step 3: Create the complete MySQL 5.7+ DDL**

Create the database and these tables with InnoDB/`utf8mb4`:

```sql
CREATE DATABASE IF NOT EXISTS guitar
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
USE guitar;

CREATE TABLE IF NOT EXISTS guitar_user (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  phone VARCHAR(20) NOT NULL,
  password_hash VARCHAR(100) NOT NULL,
  nickname VARCHAR(30) NOT NULL,
  avatar_object_key VARCHAR(500) NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'USER',
  status VARCHAR(20) NOT NULL DEFAULT 'ENABLED',
  ban_reason VARCHAR(500) NULL,
  banned_by BIGINT UNSIGNED NULL,
  banned_at DATETIME NULL,
  ban_expires_at DATETIME NULL,
  last_login_at DATETIME NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_guitar_user_phone (phone),
  KEY idx_guitar_user_status_role (status, role),
  CONSTRAINT fk_guitar_user_banned_by FOREIGN KEY (banned_by) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_sheet (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  uploader_id BIGINT UNSIGNED NOT NULL,
  song_name VARCHAR(120) NOT NULL,
  singer VARCHAR(120) NOT NULL,
  arranger VARCHAR(120) NULL,
  description VARCHAR(1000) NULL,
  keywords VARCHAR(500) NULL,
  sheet_type VARCHAR(30) NOT NULL,
  difficulty VARCHAR(30) NOT NULL,
  key_signature VARCHAR(20) NOT NULL,
  capo_position TINYINT UNSIGNED NULL,
  tuning VARCHAR(80) NOT NULL,
  file_mode VARCHAR(20) NOT NULL,
  storage_uuid CHAR(36) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PUBLISHED',
  offline_reason VARCHAR(500) NULL,
  offline_by BIGINT UNSIGNED NULL,
  offline_at DATETIME NULL,
  view_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  favorite_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_guitar_sheet_storage_uuid (storage_uuid),
  KEY idx_guitar_sheet_public (status, create_time, id),
  KEY idx_guitar_sheet_uploader (uploader_id, status, create_time),
  KEY idx_guitar_sheet_filters (status, sheet_type, difficulty, key_signature),
  CONSTRAINT fk_guitar_sheet_uploader FOREIGN KEY (uploader_id) REFERENCES guitar_user (id),
  CONSTRAINT fk_guitar_sheet_offline_by FOREIGN KEY (offline_by) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_sheet_file (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sheet_id BIGINT UNSIGNED NOT NULL,
  object_key VARCHAR(500) NOT NULL,
  original_filename VARCHAR(255) NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  file_extension VARCHAR(20) NOT NULL,
  file_size BIGINT UNSIGNED NOT NULL,
  sort_order INT UNSIGNED NOT NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_guitar_sheet_file_order (sheet_id, sort_order),
  KEY idx_guitar_sheet_file_sheet (sheet_id),
  CONSTRAINT fk_guitar_sheet_file_sheet FOREIGN KEY (sheet_id) REFERENCES guitar_sheet (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_favorite_folder (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(50) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_guitar_favorite_folder_name (user_id, name),
  KEY idx_guitar_favorite_folder_user (user_id, sort_order, id),
  CONSTRAINT fk_guitar_favorite_folder_user FOREIGN KEY (user_id) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_favorite (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  folder_id BIGINT UNSIGNED NOT NULL,
  sheet_id BIGINT UNSIGNED NOT NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_guitar_favorite (folder_id, sheet_id),
  KEY idx_guitar_favorite_user (user_id, create_time),
  KEY idx_guitar_favorite_sheet (sheet_id),
  CONSTRAINT fk_guitar_favorite_user FOREIGN KEY (user_id) REFERENCES guitar_user (id),
  CONSTRAINT fk_guitar_favorite_folder FOREIGN KEY (folder_id) REFERENCES guitar_favorite_folder (id),
  CONSTRAINT fk_guitar_favorite_sheet FOREIGN KEY (sheet_id) REFERENCES guitar_sheet (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Complete the same file with:

```sql
CREATE TABLE IF NOT EXISTS guitar_admin_action_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  admin_user_id BIGINT UNSIGNED NOT NULL,
  action_type VARCHAR(50) NOT NULL,
  target_type VARCHAR(50) NOT NULL,
  target_id BIGINT UNSIGNED NOT NULL,
  reason VARCHAR(500) NULL,
  before_state VARCHAR(1000) NULL,
  after_state VARCHAR(1000) NULL,
  ip_address VARCHAR(45) NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_guitar_admin_log_admin (admin_user_id, create_time),
  KEY idx_guitar_admin_log_target (target_type, target_id, create_time),
  KEY idx_guitar_admin_log_action (action_type, create_time),
  CONSTRAINT fk_guitar_admin_log_user FOREIGN KEY (admin_user_id) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_oss_cleanup_task (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  object_key VARCHAR(500) NOT NULL,
  business_type VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  retry_count INT UNSIGNED NOT NULL DEFAULT 0,
  next_retry_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_error VARCHAR(1000) NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_guitar_oss_cleanup_poll (status, next_retry_at),
  KEY idx_guitar_oss_cleanup_object (object_key)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_daily_stat (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  stat_date DATE NOT NULL,
  new_user_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  uploaded_sheet_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  sheet_view_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  favorite_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  offline_sheet_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_guitar_daily_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

End with:

```sql
-- Replace the placeholder with an already registered phone number.
UPDATE guitar_user
SET role = 'ADMIN', update_time = CURRENT_TIMESTAMP
WHERE phone = '<registered-phone>';
```

- [ ] **Step 4: Add dependencies and environment-backed configuration**

Add `common`, MySQL connector and Druid to `guitar/pom.xml`, plus H2 in test scope. Remove the data source/MyBatis exclusions from `GuitarApplication` and add `@EnableScheduling`. Replace properties with YAML:

```yaml
spring:
  application:
    name: guitar
  datasource:
    type: com.alibaba.druid.pool.DruidDataSource
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: ${GUITAR_DB_URL:jdbc:mysql://127.0.0.1:3306/guitar?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai}
    username: ${GUITAR_DB_USERNAME:root}
    password: ${GUITAR_DB_PASSWORD:}
  servlet:
    multipart:
      max-file-size: 30MB
      max-request-size: 210MB
  web:
    resources:
      static-locations: classpath:/static/
server:
  port: 8088
  servlet:
    session:
      cookie:
        http-only: true
        same-site: lax
mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.example.guitar
  configuration:
    map-underscore-to-camel-case: true
love530:
  oss:
    enabled: ${LOVE530_OSS_ENABLED:false}
    endpoint: ${LOVE530_OSS_ENDPOINT:}
    access-key-id: ${LOVE530_OSS_ACCESS_KEY_ID:}
    access-key-secret: ${LOVE530_OSS_ACCESS_KEY_SECRET:}
    bucket-name: ${LOVE530_OSS_BUCKET:}
    url-prefix: ${GUITAR_OSS_PUBLIC_BASE_URL:}
    base-dir: love530
    use-https: true
guitar:
  oss:
    public-base-url: ${GUITAR_OSS_PUBLIC_BASE_URL:}
```

Create `guitar/src/test/resources/application.yml` so Spring context tests never connect to a real MySQL or OSS service:

```yaml
spring:
  datasource:
    driver-class-name: org.h2.Driver
    url: jdbc:h2:mem:guitar_test;MODE=MySQL;DB_CLOSE_DELAY=-1
    username: sa
    password:
love530:
  oss:
    enabled: false
```

- [ ] **Step 5: Run the schema and application tests**

Run:

```bash
mvn -pl guitar -am test
```

Expected: BUILD SUCCESS; schema test and existing health/homepage tests pass with test properties disabling real database and OSS.

- [ ] **Step 6: Commit**

```bash
git add guitar/pom.xml guitar/src/main/java/com/example/guitar/GuitarApplication.java guitar/src/main/resources/application.yml guitar/src/main/resources/db/guitar-schema.sql guitar/src/test
git commit -m "feat(guitar): add database schema and runtime config"
```

---

### Task 2: Implement Phone Registration, Login, Session, And CSRF

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/user/model/GuitarUser.java`
- Create: `guitar/src/main/java/com/example/guitar/user/dao/GuitarUserDao.java`
- Create: `guitar/src/main/resources/mapper/user/GuitarUserMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/auth/dto/RegisterRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/dto/LoginRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/model/GuitarUserPrincipal.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/service/GuitarAuthService.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/service/GuitarAuthServiceImpl.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/controller/GuitarAuthController.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/web/GuitarAuthInterceptor.java`
- Create: `guitar/src/main/java/com/example/guitar/auth/web/CsrfTokenService.java`
- Create: `guitar/src/main/java/com/example/guitar/config/GuitarWebConfig.java`
- Create: `guitar/src/main/java/com/example/guitar/web/ApiResponse.java`
- Create: `guitar/src/main/java/com/example/guitar/web/GuitarApiException.java`
- Create: `guitar/src/main/java/com/example/guitar/web/ApiExceptionHandler.java`
- Create: `guitar/src/test/java/com/example/guitar/auth/service/GuitarAuthServiceImplTest.java`
- Create: `guitar/src/test/java/com/example/guitar/auth/controller/GuitarAuthControllerTest.java`

- [ ] **Step 1: Write failing service tests**

Cover valid registration, invalid phone, duplicate phone, weak password, wrong password, disabled user, login session rotation and logout. Use an in-memory fake DAO and `MockHttpServletRequest`. The primary happy-path assertion is:

```java
GuitarUserPrincipal principal = service.register(
        new RegisterRequest("13800138000", "guitar123", "木吉他"), request);
assertThat(principal.getPhone()).isEqualTo("13800138000");
assertThat(repository.savedUser.getPasswordHash()).startsWith("$2");
assertThat(request.getSession(false).getAttribute("GUITAR_AUTH_USER")).isEqualTo(principal);
```

- [ ] **Step 2: Run service tests and verify RED**

Run:

```bash
mvn -pl guitar -am -Dtest=GuitarAuthServiceImplTest -DfailIfNoTests=false test
```

Expected: compilation fails because the Guitar auth classes do not exist.

- [ ] **Step 3: Implement the user persistence contract**

`GuitarUserDao` must expose exactly:

```java
GuitarUser findByPhone(@Param("phone") String phone);
GuitarUser findById(@Param("id") Long id);
int insert(GuitarUser user);
int updateLastLoginAt(@Param("id") Long id, @Param("lastLoginAt") LocalDateTime lastLoginAt);
int updateProfile(@Param("id") Long id, @Param("nickname") String nickname,
                  @Param("avatarObjectKey") String avatarObjectKey);
```

Implement matching XML with explicit column lists and generated keys.

- [ ] **Step 4: Implement authentication**

`GuitarAuthServiceImpl` must:

- normalize phone with `trim()`;
- validate `^1[3-9]\\d{9}$`;
- validate password length 8-72, at least one ASCII letter and one digit, no whitespace;
- call `AuthPasswordService` for BCrypt;
- save role `USER` and status `ENABLED`;
- invalidate an existing session before saving `GuitarUserPrincipal` under `GUITAR_AUTH_USER`;
- reject `BANNED` users with code `USER_BANNED`;
- update `last_login_at` only after successful password verification.

Expose `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout` and `GET /api/auth/session` using request fields `phone`, `password` and `nickname`.

- [ ] **Step 5: Implement the response and exception contract**

`ApiResponse<T>` has `success`, `data`, `code` and `message` factory methods. `GuitarApiException` carries HTTP status and stable code. `ApiExceptionHandler` maps validation, multipart limit, access, OSS and database failures without returning stack traces or internal connection details.

- [ ] **Step 6: Implement CSRF and authorization interceptors**

`CsrfTokenService` creates a 32-byte `SecureRandom` token, Base64 URL encodes it, stores it in Session, and compares with `MessageDigest.isEqual`. `GuitarAuthInterceptor`:

- allows public GET/HEAD/OPTIONS requests;
- requires a valid CSRF token for POST/PUT/PATCH/DELETE;
- requires login for `/api/users/**`, `/api/favorite-folders/**` and non-GET `/api/sheets/**`;
- requires role `ADMIN` for `/api/admin/**`.

Register it in `GuitarWebConfig` while excluding static files and `/api/health`.

`auth.html` must first call public `GET /api/auth/session` to create the Session and obtain the CSRF token before it submits register or login. Do not exempt login/register from CSRF.

- [ ] **Step 7: Add controller tests**

Use `@WebMvcTest` with mocked service. Verify response envelopes, HTTP 400 for invalid registration, HTTP 401 for failed login, and that `GET /api/auth/session` returns both `user` and `csrfToken`.

- [ ] **Step 8: Run auth tests and full module tests**

Run:

```bash
mvn -pl guitar -am -Dtest=GuitarAuthServiceImplTest,GuitarAuthControllerTest -DfailIfNoTests=false test
mvn -pl guitar -am test
```

Expected: all tests pass; no external database or OSS call occurs.

- [ ] **Step 9: Commit**

```bash
git add guitar/src/main/java/com/example/guitar/auth guitar/src/main/java/com/example/guitar/user guitar/src/main/java/com/example/guitar/config guitar/src/main/java/com/example/guitar/web guitar/src/main/resources/mapper/user guitar/src/test/java/com/example/guitar/auth
git commit -m "feat(guitar): add phone session authentication"
```

---

### Task 3: Implement User Profile And Avatar Upload

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/user/service/GuitarUserService.java`
- Create: `guitar/src/main/java/com/example/guitar/user/controller/GuitarUserController.java`
- Create: `guitar/src/main/java/com/example/guitar/storage/model/OssCleanupTask.java`
- Create: `guitar/src/main/java/com/example/guitar/storage/dao/OssCleanupTaskDao.java`
- Create: `guitar/src/main/resources/mapper/storage/OssCleanupTaskMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/storage/service/OssCleanupService.java`
- Create: `guitar/src/test/java/com/example/guitar/user/service/GuitarUserServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/user/controller/GuitarUserControllerTest.java`

- [ ] **Step 1: Write failing avatar tests**

Verify nickname length, ownership from Session, 5MB size cap, JPEG/PNG/WebP magic validation, OSS-disabled error, object key prefix `love530/guitar/avatars/{userId}/`, database update and old-avatar cleanup.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=GuitarUserServiceTest -DfailIfNoTests=false test
```

Expected: FAIL because profile methods do not exist.

- [ ] **Step 3: Implement profile methods**

Expose:

```java
GuitarUserPrincipal updateNickname(long userId, String nickname);
GuitarUserPrincipal uploadAvatar(long userId, MultipartFile avatar);
```

Upload the new avatar before updating MySQL. If the update fails, delete the new object. After a successful update, delete the old object; enqueue cleanup when deletion fails.

Implement `OssCleanupService.deleteOrEnqueue(objectKey, businessType)` now. It calls OSS delete once and inserts a `PENDING` cleanup row with `retry_count=0` when that call fails. The scheduled retry loop is added in Task 6.

- [ ] **Step 4: Add endpoints and tests**

Implement `PUT /api/users/me` with JSON `{"nickname":"..." }` and `POST /api/users/me/avatar` with multipart field `avatar`. Never accept `userId` from the client.

- [ ] **Step 5: Run and commit**

```bash
mvn -pl guitar -am -Dtest=GuitarUserServiceTest,GuitarUserControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/user guitar/src/main/java/com/example/guitar/storage guitar/src/main/resources/mapper/storage guitar/src/test/java/com/example/guitar/user
git commit -m "feat(guitar): add profile and avatar management"
```

---

### Task 4: Implement Public Sheet Search And Detail

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/GuitarSheet.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/GuitarSheetFile.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/FileMode.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/SheetStatus.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/SheetType.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/model/SheetDifficulty.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/dto/SheetSearchRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/dto/SheetSaveRequest.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/vo/SheetSummaryResponse.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/vo/SheetDetailResponse.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetDao.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetFileDao.java`
- Create: `guitar/src/main/resources/mapper/sheet/GuitarSheetMapper.xml`
- Create: `guitar/src/main/resources/mapper/sheet/GuitarSheetFileMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/SheetFileUrlService.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/PublicOssSheetFileUrlService.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetService.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetServiceImpl.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/controller/GuitarSheetController.java`
- Create: `guitar/src/test/java/com/example/guitar/sheet/service/GuitarSheetQueryServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/sheet/controller/GuitarSheetControllerTest.java`

- [ ] **Step 1: Write failing query tests**

Cover default page 1/size 20, max size 50, all professional filters, `LATEST`/`MOST_FAVORITED`/`MOST_VIEWED` mappings, public status restriction, missing/offline detail and view count increment.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=GuitarSheetQueryServiceTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement parameterized MyBatis queries**

`GuitarSheetDao` must include:

```java
List<GuitarSheet> searchPublic(SheetSearchRequest request);
long countPublic(SheetSearchRequest request);
GuitarSheet findPublicById(@Param("id") Long id);
GuitarSheet findById(@Param("id") Long id);
int incrementViewCount(@Param("id") Long id);
int incrementDailyViewCount(@Param("statDate") LocalDate statDate);
List<GuitarSheet> findByUploader(@Param("uploaderId") Long uploaderId,
                                 @Param("offset") int offset, @Param("limit") int limit);
```

The XML must use `<where>`, `<if>` and `#{...}` only. Whitelist sort values in Java and choose fixed SQL branches with `<choose>`; never interpolate `ORDER BY` from user input.

`incrementDailyViewCount` uses the pre-created daily bucket:

```sql
INSERT INTO guitar_daily_stat(stat_date, sheet_view_count)
VALUES (#{statDate}, 1)
ON DUPLICATE KEY UPDATE sheet_view_count = sheet_view_count + 1
```

- [ ] **Step 4: Implement response mapping**

Summary response includes ID, song/singer, arranger, type, difficulty, key, capo, tuning, uploader nickname, counts and timestamps. Detail additionally includes description and ordered files with generated URLs.

`PublicOssSheetFileUrlService` first joins the configured `guitar.oss.public-base-url` and encoded object-key path. If that property is blank, it delegates to an available `OssUtil.getObjectUrl(objectKey)`. If neither source is configured, it throws `OSS_UNAVAILABLE` instead of exposing a local path.

- [ ] **Step 5: Expose public APIs**

Implement `GET /api/sheets` and `GET /api/sheets/{id}`. Return `SHEET_NOT_FOUND` for non-public details. In one transaction after loading a public record, increment both `guitar_sheet.view_count` and the current Asia/Shanghai `guitar_daily_stat.sheet_view_count`. The daily durable counter makes second-phase trends accurate without storing one row per page view.

- [ ] **Step 6: Run and commit**

```bash
mvn -pl guitar -am -Dtest=GuitarSheetQueryServiceTest,GuitarSheetControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/sheet guitar/src/main/resources/mapper/sheet guitar/src/test/java/com/example/guitar/sheet
git commit -m "feat(guitar): add sheet search and detail APIs"
```

---

### Task 5: Implement Safe PDF And Image Upload

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/SheetFileValidator.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetService.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetServiceImpl.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/controller/GuitarSheetController.java`
- Create: `guitar/src/test/java/com/example/guitar/sheet/service/SheetFileValidatorTest.java`
- Create: `guitar/src/test/java/com/example/guitar/sheet/service/GuitarSheetUploadServiceTest.java`

- [ ] **Step 1: Write validator tests**

Use `MockMultipartFile` to prove:

- one valid PDF passes;
- one PDF plus one image fails;
- 21 images fail;
- image >10MB, PDF >30MB fail;
- fake `.pdf` fails;
- valid JPEG, PNG and RIFF/WEBP signatures pass;
- `capoPosition` outside 0-12 fails.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=SheetFileValidatorTest,GuitarSheetUploadServiceTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement file validation and object keys**

Use a server-generated storage UUID and pass only a server-built directory to `OssUtil`. `OssUtil` generates the final dated UUID file name and returns the authoritative object key:

```java
String storageUuid = UUID.randomUUID().toString();
String directory = fileMode == FileMode.PDF
        ? "love530/guitar/sheets/" + storageUuid + "/pdf"
        : "love530/guitar/sheets/" + storageUuid + "/images";
OssUploadResult uploaded = ossUtil.upload(file, directory);
String objectKey = uploaded.getObjectKey();
```

Do not include any client path segment. Preserve image page order in `guitar_sheet_file.sort_order` rather than relying on the generated OSS file name.

- [ ] **Step 4: Implement upload compensation**

Validate everything before the first OSS call. Upload all objects, then insert sheet and file records in one `@Transactional` method. Catch database failure outside that transaction, delete every newly uploaded object, and enqueue deletion failures.

- [ ] **Step 5: Add multipart endpoint**

`POST /api/sheets` consumes `multipart/form-data`:

```java
public ApiResponse<SheetDetailResponse> create(
        @RequestPart("metadata") SheetSaveRequest metadata,
        @RequestPart("files") List<MultipartFile> files,
        HttpServletRequest request)
```

The user ID always comes from Session.

- [ ] **Step 6: Run and commit**

```bash
mvn -pl guitar -am -Dtest=SheetFileValidatorTest,GuitarSheetUploadServiceTest,GuitarSheetControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/sheet guitar/src/test/java/com/example/guitar/sheet
git commit -m "feat(guitar): add safe sheet uploads"
```

---

### Task 6: Implement Edit, Replace, Delete, And OSS Cleanup Retry

**Files:**
- Modify: `guitar/src/main/java/com/example/guitar/storage/dao/OssCleanupTaskDao.java`
- Modify: `guitar/src/main/resources/mapper/storage/OssCleanupTaskMapper.xml`
- Modify: `guitar/src/main/java/com/example/guitar/storage/service/OssCleanupService.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetService.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/service/GuitarSheetServiceImpl.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/controller/GuitarSheetController.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetDao.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetFileDao.java`
- Modify: `guitar/src/main/resources/mapper/sheet/GuitarSheetMapper.xml`
- Modify: `guitar/src/main/resources/mapper/sheet/GuitarSheetFileMapper.xml`
- Create: `guitar/src/test/java/com/example/guitar/sheet/service/GuitarSheetMutationServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/storage/service/OssCleanupServiceTest.java`

- [ ] **Step 1: Write failing ownership and compensation tests**

Cover owner edit, non-owner rejection, upload-new-before-switch replacement, DB failure deleting new objects, successful replacement deleting old objects, soft delete, favorite cleanup and OSS deletion retry.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=GuitarSheetMutationServiceTest,OssCleanupServiceTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement metadata edit and replacement**

Expose:

```java
SheetDetailResponse update(long userId, long sheetId, SheetSaveRequest request);
SheetDetailResponse replaceFiles(long userId, long sheetId, FileMode mode,
                                 List<MultipartFile> files);
void delete(long userId, long sheetId);
```

Each method loads the current sheet and compares `uploaderId` before mutation. `OFFLINE` sheets may be edited but remain offline; only administrators can restore them.

- [ ] **Step 4: Implement cleanup retry**

Poll at most 50 `PENDING` tasks with `next_retry_at <= now()` every five minutes. Configure a 60-second initial delay so context tests do not race an empty H2 schema. On failure, increment attempts and set delays to 5, 30, 120 and 720 minutes. After five failures set status `FAILED` for administrator visibility.

- [ ] **Step 5: Add APIs**

Implement `PUT /api/sheets/{id}`, `PUT /api/sheets/{id}/files` and `DELETE /api/sheets/{id}` with owner-only behavior and stable `FORBIDDEN` errors.

- [ ] **Step 6: Run and commit**

```bash
mvn -pl guitar -am -Dtest=GuitarSheetMutationServiceTest,OssCleanupServiceTest,GuitarSheetControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/sheet guitar/src/main/java/com/example/guitar/storage guitar/src/main/resources/mapper/storage guitar/src/test
git commit -m "feat(guitar): add sheet mutation and OSS cleanup"
```

---

### Task 7: Implement Multiple Favorite Folders

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/favorite/model/FavoriteFolder.java`
- Create: `guitar/src/main/java/com/example/guitar/favorite/dao/FavoriteDao.java`
- Create: `guitar/src/main/resources/mapper/favorite/FavoriteMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/favorite/service/FavoriteService.java`
- Create: `guitar/src/main/java/com/example/guitar/favorite/controller/FavoriteController.java`
- Create: `guitar/src/test/java/com/example/guitar/favorite/service/FavoriteServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/favorite/controller/FavoriteControllerTest.java`

- [ ] **Step 1: Write failing favorite tests**

Cover folder name normalization, duplicate names, owner-only rename/delete, same sheet in multiple folders, duplicate in one folder, offline sheet rejection, add/remove counter transaction and deleting a non-empty folder without deleting sheets.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=FavoriteServiceTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement transactional favorite operations**

The DAO must return affected row counts. Add favorite relation first, then increment the sheet counter. Remove relation first, then decrement using:

```sql
UPDATE guitar_sheet
SET favorite_count = CASE WHEN favorite_count > 0 THEN favorite_count - 1 ELSE 0 END
WHERE id = #{sheetId}
```

Translate duplicate-key exceptions into `FAVORITE_EXISTS` or `FOLDER_NAME_EXISTS`.

- [ ] **Step 4: Expose all approved favorite APIs**

Use Session user ID for every folder query. Never accept or return folders belonging to another user.

- [ ] **Step 5: Run and commit**

```bash
mvn -pl guitar -am -Dtest=FavoriteServiceTest,FavoriteControllerTest -DfailIfNoTests=false test
git add guitar/src/main/java/com/example/guitar/favorite guitar/src/main/resources/mapper/favorite guitar/src/test/java/com/example/guitar/favorite
git commit -m "feat(guitar): add favorite folders"
```

---

### Task 8: Implement Administrator Offline And Restore

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/admin/model/AdminActionLog.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/dao/AdminActionLogDao.java`
- Create: `guitar/src/main/resources/mapper/admin/AdminActionLogMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/admin/service/SheetAdminService.java`
- Create: `guitar/src/main/java/com/example/guitar/admin/controller/SheetAdminController.java`
- Create: `guitar/src/test/java/com/example/guitar/admin/service/SheetAdminServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/admin/controller/SheetAdminControllerTest.java`

- [ ] **Step 1: Write failing admin tests**

Verify ADMIN can list all states, offline a published sheet with a required 1-500 character reason, restore an offline sheet, and create audit rows containing before/after status. Verify USER receives HTTP 403.

- [ ] **Step 2: Run and verify RED**

```bash
mvn -pl guitar -am -Dtest=SheetAdminServiceTest,SheetAdminControllerTest -DfailIfNoTests=false test
```

- [ ] **Step 3: Implement state transitions**

Allow only:

```text
PUBLISHED -> OFFLINE
OFFLINE   -> PUBLISHED
```

Reject `DELETED` restoration. Update the sheet and insert the audit log in one transaction.

- [ ] **Step 4: Expose admin APIs and run tests**

Implement the three approved phase-one admin APIs. Return the updated sheet summary.

- [ ] **Step 5: Commit**

```bash
git add guitar/src/main/java/com/example/guitar/admin guitar/src/main/resources/mapper/admin guitar/src/test/java/com/example/guitar/admin
git commit -m "feat(guitar): add sheet moderation"
```

---

### Task 9: Add The Shared Frontend Foundation And Authentication Pages

**Required skills during execution:** `ui-ux-pro-max`, then `playwright-cli` for verification.

**Files:**
- Replace: `guitar/src/main/resources/static/index.html`
- Create: `guitar/src/main/resources/static/auth.html`
- Create: `guitar/src/main/resources/static/css/app.css`
- Create: `guitar/src/main/resources/static/js/api.js`
- Create: `guitar/src/main/resources/static/js/session.js`
- Create: `guitar/src/main/resources/static/js/auth.js`
- Create: `guitar/package.json`
- Create: `guitar/src/test/js/api.test.js`
- Create: `guitar/src/test/js/auth-validation.test.js`

- [ ] **Step 1: Invoke the UI skill and define the token sheet**

Use `ui-ux-pro-max` to select typography, neutral surface colors, status colors, spacing, focus rings, responsive breakpoints and maximum 8px radii. Keep the first viewport as the actual search application.

- [ ] **Step 2: Write failing Node tests**

Test phone/password/nickname validation, API envelope handling, CSRF header injection and 401 redirect behavior.

Run:

```bash
node guitar/src/test/js/api.test.js
node guitar/src/test/js/auth-validation.test.js
```

Expected: FAIL because the JS modules do not exist.

- [ ] **Step 3: Implement shared API/session modules**

`api.js` exports `apiRequest(path, options)`, reads the token maintained by `session.js`, sends `credentials: "same-origin"`, attaches `X-CSRF-Token` for writes, parses the standard envelope and throws an `ApiError` carrying `status` and `code`.

Create `guitar/package.json` with `"type": "module"` and scripts for the five phase-one Node test files, so Node imports the browser modules consistently.

- [ ] **Step 4: Build the login/register page**

Use accessible Login/Register tabs, labelled phone/password/nickname fields, inline errors, submit loading state and a password visibility icon button with tooltip. Registration redirects to `profile.html` so avatar remains optional.

- [ ] **Step 5: Run JS and MockMvc static tests**

Add static page assertions to `GuitarApplicationTests` for navigation, form labels and module script paths.

- [ ] **Step 6: Commit**

```bash
git add guitar/src/main/resources/static guitar/src/test/js guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java
git commit -m "feat(guitar): add frontend foundation and auth UI"
```

---

### Task 10: Build Search And Sheet Detail UI

**Files:**
- Modify: `guitar/src/main/resources/static/index.html`
- Create: `guitar/src/main/resources/static/sheet.html`
- Create: `guitar/src/main/resources/static/js/index.js`
- Create: `guitar/src/main/resources/static/js/sheet.js`
- Create: `guitar/src/test/js/sheet-search.test.js`

- [ ] **Step 1: Write failing search-state tests**

Test URL parameter serialization for every professional filter, page reset on filter changes, sort mapping, empty/error states and HTML escaping.

- [ ] **Step 2: Implement the search work surface**

Desktop: fixed-width filter column and fluid results. Mobile: filter icon opens a modal drawer. Results display all approved metadata and preserve filter state in the URL. Use stable skeleton dimensions so loading does not shift layout.

- [ ] **Step 3: Implement detail preview**

Render one PDF in a full-width `<object>` with a download fallback. Render image sheets as ordered, lazy-loaded pages. Provide favorite-folder menu, owner actions and admin action based on the session response.

Show the optional arranger/source when present and a fixed platform notice stating that uploaded material is provided by users and rights holders may request removal. Do not claim platform ownership of user uploads.

- [ ] **Step 4: Verify with Playwright**

Start Guitar with isolated test configuration, then capture desktop 1440x900 and mobile 390x844 screenshots. Verify no horizontal scrolling, overlap or clipped labels; exercise search, filter drawer, detail, PDF fallback and image sequence.

- [ ] **Step 5: Commit**

```bash
git add guitar/src/main/resources/static/index.html guitar/src/main/resources/static/sheet.html guitar/src/main/resources/static/js/index.js guitar/src/main/resources/static/js/sheet.js guitar/src/main/resources/static/css/app.css guitar/src/test/js
git commit -m "feat(guitar): add sheet discovery UI"
```

---

### Task 11: Build Upload, Favorites, Profile, And Admin UI

**Files:**
- Create: `guitar/src/main/resources/static/upload.html`
- Create: `guitar/src/main/resources/static/favorites.html`
- Create: `guitar/src/main/resources/static/profile.html`
- Create: `guitar/src/main/resources/static/admin.html`
- Create: `guitar/src/main/resources/static/js/upload.js`
- Create: `guitar/src/main/resources/static/js/favorites.js`
- Create: `guitar/src/main/resources/static/js/profile.js`
- Create: `guitar/src/main/resources/static/js/admin.js`
- Create: `guitar/src/test/js/upload-validation.test.js`
- Create: `guitar/src/test/js/favorite-state.test.js`

- [ ] **Step 1: Write failing client validation tests**

Test PDF/image mode exclusivity, 30MB/10MB limits, 20-image cap, page reordering, duplicate-submit lock, folder name validation and admin reason validation.

- [ ] **Step 2: Build upload/edit**

Use a PDF/多图 segmented control. Multi-image mode provides drag/drop, thumbnail previews, keyboard-accessible move up/down icon buttons and deterministic `files` order. Use XHR upload progress because Fetch does not expose upload progress.

- [ ] **Step 3: Build favorites and profile**

Favorites use folder navigation and a sheet list without nested cards. Profile supports nickname/avatar changes and “我的上传” with edit/delete actions.

- [ ] **Step 4: Build phase-one admin**

Provide status filters, paginated sheet rows, offline/restore commands and a modal requiring a moderation reason. Hide the page for non-admin users and still rely on server authorization.

- [ ] **Step 5: Run JS tests and Playwright workflows**

Exercise register, login, upload validation, favorites, owner edit/delete, admin offline/restore, empty states and API errors at desktop/mobile sizes.

- [ ] **Step 6: Commit**

```bash
git add guitar/src/main/resources/static guitar/src/test/js
git commit -m "feat(guitar): complete phase one frontend"
```

---

### Task 12: Synchronize Documentation And Run Phase-One Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `guitar/AGENTS.md`
- Create: `guitar/README.md`
- Modify: `website/src/main/resources/static/index.html` only if the existing Guitar entry or health URL no longer matches.

- [ ] **Step 1: Update documentation**

Document module responsibilities, database `guitar`, DDL execution, environment variables, OSS public-read assumption, API list, upload limits, administrator promotion SQL, test commands and startup commands. Remove the obsolete statement that Guitar has no database or external service.

- [ ] **Step 2: Run backend and frontend tests**

```bash
mvn -pl common,guitar -am test
node guitar/src/test/js/api.test.js
node guitar/src/test/js/auth-validation.test.js
node guitar/src/test/js/sheet-search.test.js
node guitar/src/test/js/upload-validation.test.js
node guitar/src/test/js/favorite-state.test.js
```

Expected: all commands exit 0; Maven reports zero failures/errors.

- [ ] **Step 3: Run the service**

After the user executes `guitar-schema.sql` and supplies local database credentials:

```bash
mvn -pl common install -DskipTests
mvn -f guitar/pom.xml spring-boot:run
```

Verify:

```text
GET http://127.0.0.1:8088/api/health
GET http://127.0.0.1:8088/
```

Expected: health has `success=true` and the browser shows the search application.

- [ ] **Step 4: Run final Playwright verification**

Verify user-facing workflows with Playwright API route stubs and generated data URLs for PDF/image previews; backend OSS behavior is covered by Mockito service tests. Save no generated screenshots in tracked application directories.

- [ ] **Step 5: Review secrets and worktree**

Run:

```bash
git diff --check
git status --short
git diff --name-only
```

Confirm no password, AccessKey, phone number, `target/` or generated upload artifact is staged.

- [ ] **Step 6: Commit documentation**

```bash
git add AGENTS.md README.md guitar/AGENTS.md guitar/README.md website/src/main/resources/static/index.html
git commit -m "docs: document guitar sheet platform phase one"
```

---

## Phase-One Completion Gate

Do not begin phase two until:

- every Task 1-12 checkbox is complete;
- `mvn -pl common,guitar -am test` passes;
- all Node tests pass;
- desktop and mobile Playwright workflows pass;
- the user has executed the DDL in the intended MySQL environment;
- public OSS URL generation works with object keys and no URL is persisted in MySQL;
- documentation matches the implemented API and configuration.
