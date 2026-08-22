# Unified Service Health Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize `/api/health` across six independent services, centralize Java-side remote probing, and expose a parallel aggregate health endpoint from `website`.

**Architecture:** `website` owns a configuration-driven service registry and a single `ServiceHealthChecker` that validates HTTP 2xx plus top-level JSON `success=true`. The three Python auto-start runners reuse the checker, while a bounded executor lets `ServiceHealthAggregator` check all configured services concurrently and return ordered results through `/api/services/health`.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Spring MVC, Jackson, `HttpURLConnection`, JUnit 5, MockMvc, Python `unittest`/pytest.

---

## File map

Create in `website/src/main/java/com/example/website/integration/health/`:

- `ServiceHealthDefinition.java`: immutable service name and URL.
- `ServiceHealthResult.java`: one probe's safe, serializable result.
- `ServiceHealthSummary.java`: aggregate API response.
- `ServiceHealthProperties.java`: timeout and configured service registry binding with startup validation.
- `ServiceHealthChecker.java`: HTTP request, strict JSON validation, URL construction, and readiness polling.
- `ServiceHealthConfiguration.java`: bounded application-managed executor.
- `ServiceHealthAggregator.java`: concurrent checks with stable configured ordering.
- `ServiceHealthController.java`: `GET /api/services/health`.

Modify:

- `website/src/main/java/com/example/website/integration/{PythonAAutoStartRunner,QuantAAutoStartRunner,VideoAutoStartRunner}.java`
- `website/src/main/resources/application.yml`
- `lovestory/src/main/java/com/ycxandwuqian/love/controller/HealthController.java` (new)
- `imagetemplate/src/main/java/com/example/imagetemplate/controller/HealthController.java` (new)
- `website/python-a/server.py`
- `website/quant-a/quant/api/routes.py`
- service and root documentation listed in Task 8.

Tests:

- New health package unit and MVC tests under `website/src/test/java/com/example/website/integration/health/`
- Existing `*AutoStartRunnerTest`
- New Java endpoint tests in `lovestory` and `imagetemplate`
- Existing Guitar and Quant tests
- New focused Python-A and Video health tests.

### Task 1: Standardize the six service endpoints

**Files:**

- Create: `lovestory/src/main/java/com/ycxandwuqian/love/controller/HealthController.java`
- Create: `lovestory/src/test/java/com/ycxandwuqian/love/controller/HealthControllerTests.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/controller/HealthController.java`
- Create: `imagetemplate/src/test/java/com/example/imagetemplate/controller/HealthControllerTest.java`
- Verify: `guitar/src/main/java/com/example/guitar/controller/HealthController.java`
- Verify: `guitar/src/test/java/com/example/guitar/GuitarApplicationTests.java`
- Modify: `website/python-a/server.py`
- Create: `website/python-a/tests/test_health.py`
- Modify: `website/quant-a/quant/api/routes.py`
- Modify: `website/quant-a/tests/test_health.py`
- Verify: `website/video/python/anime_tools/web_api.py`
- Create: `website/video/tests/test_health.py`

- [ ] **Step 1: Write failing Java endpoint tests**

Use standalone MockMvc tests that assert HTTP 200, JSON content type, top-level
`success=true`, and the stable service name:

```java
mockMvc.perform(get("/api/health"))
        .andExpect(status().isOk())
        .andExpect(content().contentTypeCompatibleWith("application/json"))
        .andExpect(jsonPath("$.success").value(true))
        .andExpect(jsonPath("$.service").value("lovestory"));
```

Repeat for `imagetemplate`; keep the existing equivalent Guitar assertion.

- [ ] **Step 2: Run Java tests and verify RED**

Run:

```powershell
mvn -pl lovestory,imagetemplate,guitar -am '-Dtest=HealthControllerTests,HealthControllerTest,GuitarApplicationTests' -DfailIfNoTests=false test
```

Expected: lovestory and imagetemplate fail with 404; Guitar passes.

- [ ] **Step 3: Add the minimal Java controllers**

Each new controller returns a `LinkedHashMap` with `success` and `service`, matching
the existing Guitar controller:

```java
@RestController
@RequestMapping("/api")
public class HealthController {
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", true);
        response.put("service", "lovestory");
        return response;
    }
}
```

Use `"imagetemplate"` in the imagetemplate module.

- [ ] **Step 4: Run Java endpoint tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Write failing Python endpoint assertions**

Python-A's focused handler test must start its HTTP server on an ephemeral port and
assert:

```python
assert payload["success"] is True
assert payload["service"] == "python-a"
```

Extend Quant's expected object with top-level `"service": "quant-a"`. Video's
focused test starts the existing server fixture/helper and asserts top-level
`success` and `service`.

- [ ] **Step 6: Run Python tests and verify RED**

Run:

```powershell
Push-Location website/python-a
python -m unittest tests.test_health
Pop-Location
Push-Location website/quant-a
python -m pytest tests/test_health.py -q
Pop-Location
Push-Location website/video
python -m pytest tests/test_health.py -q
Pop-Location
```

Expected: Python-A and Quant fail because the top-level contract is missing;
Video passes if its existing response is exercised correctly.

- [ ] **Step 7: Make Python responses conform without removing compatible fields**

Python-A retains existing metadata and adds:

```python
{
    "success": True,
    "service": "python-a",
    "ok": True,
    # existing time, obsidian_root and data_source
}
```

Quant returns:

```python
return {
    **success({
        "service": "quant-a",
        "status": "ok",
        "port": 5175,
    }),
    "service": "quant-a",
}
```

Video already returns `{"success": True, "service": "video"}` and needs no
production change unless its focused test exposes a discrepancy.

- [ ] **Step 8: Run all focused endpoint tests and verify GREEN**

Run Steps 4 and 6 commands. Expected: all pass.

- [ ] **Step 9: Commit endpoint standardization**

```powershell
git add -- lovestory/src/main/java/com/ycxandwuqian/love/controller/HealthController.java lovestory/src/test/java/com/ycxandwuqian/love/controller/HealthControllerTests.java imagetemplate/src/main/java/com/example/imagetemplate/controller/HealthController.java imagetemplate/src/test/java/com/example/imagetemplate/controller/HealthControllerTest.java website/python-a/server.py website/python-a/tests/test_health.py website/quant-a/quant/api/routes.py website/quant-a/tests/test_health.py website/video/tests/test_health.py
git commit -m "feat: standardize service health endpoints"
```

### Task 2: Add configuration-driven health definitions

**Files:**

- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthDefinition.java`
- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthProperties.java`
- Create: `website/src/test/java/com/example/website/integration/health/ServiceHealthPropertiesTest.java`
- Modify: `website/src/main/resources/application.yml`

- [ ] **Step 1: Write failing configuration tests**

Cover defaults, stable configured order, duplicate names, blank names, and
non-HTTP(S) URLs. The desired API is:

```java
ServiceHealthProperties properties = new ServiceHealthProperties();
properties.setServices(Arrays.asList(
        new ServiceHealthDefinition("guitar", "http://127.0.0.1:8088/api/health"),
        new ServiceHealthDefinition("video", "http://127.0.0.1:5176/api/health")));
properties.validate();
assertThat(properties.getServices()).extracting(ServiceHealthDefinition::getName)
        .containsExactly("guitar", "video");
```

Invalid definitions must throw `IllegalStateException` with the offending service
index or name but without printing credentials embedded in a URL.

- [ ] **Step 2: Run the test and verify RED**

```powershell
mvn -pl website -am '-Dtest=ServiceHealthPropertiesTest' -DfailIfNoTests=false test
```

Expected: compilation fails because the types do not exist.

- [ ] **Step 3: Implement the minimal property model**

`ServiceHealthDefinition` is a JavaBean-compatible value object with `name` and
`url`, no networking behavior. `ServiceHealthProperties` uses:

```java
@Component
@ConfigurationProperties(prefix = "website.service-health")
public class ServiceHealthProperties {
    private int connectTimeoutMs = 2000;
    private int readTimeoutMs = 3000;
    private List<ServiceHealthDefinition> services = new ArrayList<>();

    @PostConstruct
    public void validate() { /* positive timeouts, unique names, http/https URLs */ }
}
```

Validation must use `new URI(url).getScheme()` and must not include raw URLs in
exception messages.

- [ ] **Step 4: Add all six definitions to `application.yml`**

Add the exact registry from the approved design under
`website.service-health.services`, preserving this order:
lovestory, imagetemplate, guitar, python-a, quant-a, video.

- [ ] **Step 5: Run test and verify GREEN**

Run Step 2. Expected: all property tests pass.

- [ ] **Step 6: Commit the registry**

```powershell
git add -- website/src/main/java/com/example/website/integration/health/ServiceHealthDefinition.java website/src/main/java/com/example/website/integration/health/ServiceHealthProperties.java website/src/test/java/com/example/website/integration/health/ServiceHealthPropertiesTest.java website/src/main/resources/application.yml
git commit -m "feat: configure service health registry"
```

### Task 3: Implement the unified checker

**Files:**

- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthResult.java`
- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthChecker.java`
- Create: `website/src/test/java/com/example/website/integration/health/ServiceHealthCheckerTest.java`

- [ ] **Step 1: Write failing protocol tests with an ephemeral HTTP server**

Use `com.sun.net.httpserver.HttpServer` and assert the desired API:

```java
ServiceHealthResult result = checker.check(
        new ServiceHealthDefinition("demo", serverUrl("/api/health")));
assertThat(result.isHealthy()).isTrue();
assertThat(result.getStatusCode()).isEqualTo(200);
assertThat(result.getDurationMs()).isGreaterThanOrEqualTo(0);
assertThat(result.getMessage()).isNull();
```

Add separate tests for non-2xx, malformed JSON, missing `success`, boolean false,
string `"true"`, connection failure, and read timeout. Failure messages must be
stable categories such as `HTTP 503`, `Invalid health response`, `Timed out`, and
`Connection failed`; never assert platform-specific exception text.

- [ ] **Step 2: Run protocol tests and verify RED**

```powershell
mvn -pl website -am '-Dtest=ServiceHealthCheckerTest' -DfailIfNoTests=false test
```

Expected: compilation fails because checker/result do not exist.

- [ ] **Step 3: Implement strict checking**

Constructor:

```java
public ServiceHealthChecker(ObjectMapper objectMapper,
                            ServiceHealthProperties properties)
```

Public methods:

```java
public ServiceHealthResult check(ServiceHealthDefinition definition)
public boolean waitUntilHealthy(ServiceHealthDefinition definition,
                                int timeoutSeconds)
public String buildLocalUrl(int port, String healthPath)
```

`check` uses `HttpURLConnection`, configured timeouts, one `getResponseCode()`
call, and try-with-resources for the success body. Parse with `ObjectMapper` and
accept only `root.path("success").isBoolean() && root.path("success").booleanValue()`.
Disconnect in `finally`. Record duration with `System.nanoTime()`.

`ServiceHealthResult` supplies exact static factories:

```java
public static ServiceHealthResult healthy(ServiceHealthDefinition definition,
                                          int statusCode,
                                          long durationMs)
public static ServiceHealthResult unhealthy(ServiceHealthDefinition definition,
                                            Integer statusCode,
                                            long durationMs,
                                            String message)
```

`waitUntilHealthy` performs at least one attempt, retries every second until the
configured number of seconds is exhausted, and preserves interrupt status.

`buildLocalUrl` normalizes a missing leading slash and returns
`http://127.0.0.1:{port}/{path}`.

- [ ] **Step 4: Run protocol tests and verify GREEN**

Run Step 2. Expected: all checker tests pass.

- [ ] **Step 5: Add polling and URL tests**

Add tests that assert normalized paths, immediate success, eventual success, timeout,
and interruption. Add a package-private constructor receiving this focused strategy:

```java
interface Sleeper {
    void sleep(long millis) throws InterruptedException;
}

ServiceHealthChecker(ObjectMapper objectMapper,
                     ServiceHealthProperties properties,
                     Sleeper sleeper)
```

The public Spring constructor delegates with `Thread::sleep`. Tests inject a no-op
or interrupting sleeper, so no test waits for real one-second intervals.

- [ ] **Step 6: Run all checker tests and verify GREEN**

Run Step 2. Expected: all pass without warnings.

- [ ] **Step 7: Commit the checker**

```powershell
git add -- website/src/main/java/com/example/website/integration/health/ServiceHealthResult.java website/src/main/java/com/example/website/integration/health/ServiceHealthChecker.java website/src/test/java/com/example/website/integration/health/ServiceHealthCheckerTest.java
git commit -m "feat: add unified service health checker"
```

### Task 4: Migrate the Python auto-start runners

**Files:**

- Modify: `website/src/main/java/com/example/website/integration/PythonAAutoStartRunner.java`
- Modify: `website/src/main/java/com/example/website/integration/QuantAAutoStartRunner.java`
- Modify: `website/src/main/java/com/example/website/integration/VideoAutoStartRunner.java`
- Modify: `website/src/test/java/com/example/website/integration/PythonAAutoStartRunnerTest.java`
- Modify: `website/src/test/java/com/example/website/integration/QuantAAutoStartRunnerTest.java`
- Modify: `website/src/test/java/com/example/website/integration/VideoAutoStartRunnerTest.java`

- [ ] **Step 1: Rewrite runner tests against the shared checker and verify RED**

Construct each runner with a mocked or recording `ServiceHealthChecker`. Assert:

- existing healthy service prevents `ProcessBuilder.start()`;
- unhealthy service starts the existing command;
- startup readiness calls `waitUntilHealthy`;
- the definition uses the expected service name and normalized URL.

Remove tests that directly call runner-owned `isHealthy`, because that behavior now
belongs to `ServiceHealthCheckerTest`. Keep work-directory and command tests.

- [ ] **Step 2: Run runner tests and verify RED**

```powershell
mvn -pl website -am '-Dtest=PythonAAutoStartRunnerTest,QuantAAutoStartRunnerTest,VideoAutoStartRunnerTest' -DfailIfNoTests=false test
```

Expected: compilation or assertion failures because runners do not inject/use the checker.

- [ ] **Step 3: Inject and use `ServiceHealthChecker`**

Each runner builds:

```java
ServiceHealthDefinition definition = new ServiceHealthDefinition(
        "python-a", healthChecker.buildLocalUrl(port, healthPath));
```

Use `healthChecker.check(definition).isHealthy()` before starting and
`healthChecker.waitUntilHealthy(definition, startupTimeoutSeconds)` afterward.
Use `"quant-a"` and `"video"` in the other runners.

Delete duplicated `buildHealthUrl`, `isHealthy`, `readResponseBody`, and
`waitUntilHealthy` methods and their now-unused imports. Preserve process commands,
working-directory resolution, log routing, shutdown, and warning behavior.

- [ ] **Step 4: Run runner tests and verify GREEN**

Run Step 2. Expected: all runner tests pass.

- [ ] **Step 5: Commit migration**

```powershell
git add -- website/src/main/java/com/example/website/integration/PythonAAutoStartRunner.java website/src/main/java/com/example/website/integration/QuantAAutoStartRunner.java website/src/main/java/com/example/website/integration/VideoAutoStartRunner.java website/src/test/java/com/example/website/integration/PythonAAutoStartRunnerTest.java website/src/test/java/com/example/website/integration/QuantAAutoStartRunnerTest.java website/src/test/java/com/example/website/integration/VideoAutoStartRunnerTest.java
git commit -m "refactor: reuse service health checker in auto-start runners"
```

### Task 5: Add parallel aggregation

**Files:**

- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthConfiguration.java`
- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthSummary.java`
- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthAggregator.java`
- Create: `website/src/test/java/com/example/website/integration/health/ServiceHealthAggregatorTest.java`

- [ ] **Step 1: Write failing aggregation tests**

Desired call:

```java
ServiceHealthSummary summary = aggregator.checkAll();
assertThat(summary.isSuccess()).isTrue();
assertThat(summary.isHealthy()).isFalse();
assertThat(summary.getServices()).extracting(ServiceHealthResult::getName)
        .containsExactly("lovestory", "guitar", "video");
```

Cover all healthy, partial failure, checker exception isolation, and configured
ordering. Use latches in a concurrency test to prove two checks start before either
is released.

- [ ] **Step 2: Run test and verify RED**

```powershell
mvn -pl website -am '-Dtest=ServiceHealthAggregatorTest' -DfailIfNoTests=false test
```

Expected: compilation fails because aggregation types do not exist.

- [ ] **Step 3: Add the bounded executor**

`ServiceHealthConfiguration` creates a `ThreadPoolTaskExecutor` bean named
`serviceHealthExecutor`. Set core/max pool size to
`Math.max(1, properties.getServices().size())`, queue capacity to the same size,
thread prefix `service-health-`, and `setWaitForTasksToCompleteOnShutdown(true)`.

- [ ] **Step 4: Implement ordered concurrent aggregation**

`ServiceHealthAggregator` constructor injects properties, checker, and the qualified
executor. `checkAll()` creates one `CompletableFuture` per definition, maps unexpected
exceptions to `ServiceHealthResult.unhealthy(...)`, joins all futures in original
list order, and sets:

```java
success = true;
healthy = results.stream().allMatch(ServiceHealthResult::isHealthy);
```

- [ ] **Step 5: Run aggregation tests and verify GREEN**

Run Step 2. Expected: all pass, including the concurrency test.

- [ ] **Step 6: Commit aggregation**

```powershell
git add -- website/src/main/java/com/example/website/integration/health/ServiceHealthConfiguration.java website/src/main/java/com/example/website/integration/health/ServiceHealthSummary.java website/src/main/java/com/example/website/integration/health/ServiceHealthAggregator.java website/src/test/java/com/example/website/integration/health/ServiceHealthAggregatorTest.java
git commit -m "feat: aggregate service health checks in parallel"
```

### Task 6: Expose the aggregate API

**Files:**

- Create: `website/src/main/java/com/example/website/integration/health/ServiceHealthController.java`
- Create: `website/src/test/java/com/example/website/integration/health/ServiceHealthControllerTest.java`

- [ ] **Step 1: Write failing MockMvc tests**

Use `@WebMvcTest(ServiceHealthController.class)` with a mocked aggregator. Assert
HTTP 200 and:

```java
jsonPath("$.success").value(true);
jsonPath("$.healthy").value(false);
jsonPath("$.services[0].name").value("guitar");
jsonPath("$.services[0].statusCode").value(200);
jsonPath("$.services[1].message").value("Connection failed");
```

Also assert `statusCode` is JSON null when no response was received and healthy
items omit/null `message`.

- [ ] **Step 2: Run controller test and verify RED**

```powershell
mvn -pl website -am '-Dtest=ServiceHealthControllerTest' -DfailIfNoTests=false test
```

Expected: compilation fails because the controller does not exist.

- [ ] **Step 3: Add the minimal controller**

```java
@RestController
@RequestMapping("/api/services")
public class ServiceHealthController {
    private final ServiceHealthAggregator aggregator;

    public ServiceHealthController(ServiceHealthAggregator aggregator) {
        this.aggregator = aggregator;
    }

    @GetMapping("/health")
    public ServiceHealthSummary health() {
        return aggregator.checkAll();
    }
}
```

- [ ] **Step 4: Run controller and website context tests**

```powershell
mvn -pl website -am '-Dtest=ServiceHealthControllerTest,WebsiteApplicationTests' -DfailIfNoTests=false test
```

Expected: tests pass with all auto-start switches disabled by the existing test
configuration.

- [ ] **Step 5: Commit the API**

```powershell
git add -- website/src/main/java/com/example/website/integration/health/ServiceHealthController.java website/src/test/java/com/example/website/integration/health/ServiceHealthControllerTest.java
git commit -m "feat: expose aggregate service health endpoint"
```

### Task 7: Run focused and full regression tests

**Files:** No production changes expected.

- [ ] **Step 1: Run all Java health-focused tests**

```powershell
mvn -pl website,lovestory,imagetemplate,guitar -am '-Dtest=*Health*Test,*Health*Tests,*AutoStartRunnerTest,GuitarApplicationTests' -DfailIfNoTests=false test
```

Expected: BUILD SUCCESS.

- [ ] **Step 2: Run complete affected Java modules**

```powershell
mvn -pl website,lovestory,imagetemplate,guitar -am test
```

Expected: BUILD SUCCESS with no real MySQL, OSS, OpenAI, Nacos, or Python process
dependency.

- [ ] **Step 3: Run Python regressions**

Use each micro-application's actual supported test command:

```powershell
Push-Location website/python-a
python -m unittest discover -s tests
Pop-Location
Push-Location website/quant-a
python -m pytest
Pop-Location
Push-Location website/video
python -m pytest
Pop-Location
```

Expected: all suites pass. If optional external dependencies cause documented skips,
record the skips; do not weaken assertions.

- [ ] **Step 4: Inspect the final production diff**

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated pre-existing untracked files remain
unstaged and untouched.

### Task 8: Synchronize documentation

**Files:**

- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `website/AGENTS.md`
- Modify: `website/README.md`
- Modify: `lovestory/AGENTS.md`
- Modify: `lovestory/README.md`
- Modify: `imagetemplate/AGENTS.md`
- Modify: `imagetemplate/README.md`
- Modify: `guitar/AGENTS.md`
- Modify: `guitar/README.md`
- Modify: `website/python-a/AGENTS.md`
- Modify: `website/python-a/README.md`
- Modify: `website/quant-a/AGENTS.md`
- Modify: `website/quant-a/README.md`
- Modify: `website/video/AGENTS.md`
- Modify: `website/video/README.md`

- [ ] **Step 1: Update API and responsibility documentation**

Document:

- every independent service exposes `GET /api/health`;
- response requires top-level `success=true` and stable `service`;
- `website` exposes `GET /api/services/health`;
- configured services, order, ports, and timeout properties;
- aggregate HTTP 200 means aggregation succeeded while `healthy` means all services
  are available;
- `website` auto-starts only the three Python services.

- [ ] **Step 2: Update testing documentation**

Add the focused and full verification commands from Task 7 to the appropriate root
and module documents. Do not replace unrelated module-specific commands.

- [ ] **Step 3: Check documentation consistency**

```powershell
rg -n "/api/services/health|ServiceHealthChecker|/api/health" AGENTS.md README.md website/AGENTS.md website/README.md lovestory/AGENTS.md lovestory/README.md imagetemplate/AGENTS.md imagetemplate/README.md guitar/AGENTS.md guitar/README.md website/python-a/AGENTS.md website/python-a/README.md website/quant-a/AGENTS.md website/quant-a/README.md website/video/AGENTS.md website/video/README.md
git diff --check
```

Expected: each affected service documents its health endpoint and the root/website
documents describe the aggregate endpoint and checker.

- [ ] **Step 4: Commit documentation**

```powershell
git add -- AGENTS.md README.md website/AGENTS.md website/README.md lovestory/AGENTS.md lovestory/README.md imagetemplate/AGENTS.md imagetemplate/README.md guitar/AGENTS.md guitar/README.md website/python-a/AGENTS.md website/python-a/README.md website/quant-a/AGENTS.md website/quant-a/README.md website/video/AGENTS.md website/video/README.md
git commit -m "docs: document unified service health checks"
```

### Task 9: Final verification and handoff

**Files:** All files changed in Tasks 1-8.

- [ ] **Step 1: Re-run the complete affected test matrix**

Repeat Task 7 Steps 2 and 3 after documentation edits. Expected: all supported
suites pass.

- [ ] **Step 2: Verify commit and worktree scope**

```powershell
git log --oneline -10
git status --short
```

Expected: feature commits contain only planned files; unrelated pre-existing changes
remain untouched.

- [ ] **Step 3: Report the result**

Handoff must list:

- unified endpoint contract;
- aggregate endpoint and response semantics;
- checker/runner integration;
- exact test commands and outcomes;
- any documented test skips;
- unrelated dirty-worktree files that were deliberately left untouched.
