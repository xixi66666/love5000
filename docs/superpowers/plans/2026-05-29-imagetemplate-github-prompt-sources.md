# imagetemplate GitHub Prompt Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand imagetemplate with curated GPT Image-2 prompt templates from three GitHub source projects.

**Architecture:** Keep templates as static JSON data. Update service tests first to define the new template count and data contracts, then append curated direct-prompt and structured templates. Update AGENTS docs to preserve long-term project rules.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Jackson, JUnit 5, AssertJ, static JSON.

---

### Task 1: Test Contract

**Files:**
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java`

- [ ] Update total template count from 29 to 47.
- [ ] Update direct-prompt count from 8 to 20.
- [ ] Add assertions that templates include GitHub source URLs for `YouMind-OpenLab`, `EvoLinkAI`, and `freestylefly`.
- [ ] Add assertions that new structured templates have non-empty `jsonTemplate`.
- [ ] Run `mvn -pl imagetemplate -Dtest=ImagePromptTemplateServiceTest test` and confirm it fails before JSON changes.

### Task 2: Template Data

**Files:**
- Modify: `imagetemplate/src/main/resources/templates/image-prompt-templates.json`

- [ ] Append 12 direct-prompt templates using complete Chinese prompts and GitHub source URLs.
- [ ] Append 6 structured templates with stable ids, categories, tags, `jsonTemplate`, and `promptTemplate`.
- [ ] Keep JSON valid with no comments and no trailing commas.
- [ ] Run `mvn -pl imagetemplate -Dtest=ImagePromptTemplateServiceTest test` and confirm it passes.

### Task 3: Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `imagetemplate/AGENTS.md`

- [ ] Update template count to 47.
- [ ] Update direct-prompt count to 20.
- [ ] Document the three GitHub prompt sources and source URL requirement.
- [ ] Run `mvn -pl imagetemplate -am test`.

### Task 4: Final Verification

**Files:**
- No source edits expected.

- [ ] Run `mvn -pl imagetemplate -am test`.
- [ ] Optionally package and query `/api/image-templates/categories` to confirm `direct-prompt` count is 20.
