# Video Structure Config Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `website/video` so Python code, scripts, and config files have clear boundaries while preserving existing root startup commands.

**Architecture:** Keep root `web_server.py` and `anime_cli.py` as compatibility wrappers. Move real Python implementation into `python/`, centralize config under `config/`, add local config read/write APIs, and remove formal tests as requested.

**Tech Stack:** Python standard library `http.server`, native HTML/CSS/JavaScript, existing `anime_tools`.

---

## Files

- Move: `website/video/anime_tools/` -> `website/video/python/anime_tools/`
- Move: `website/video/anime_cli.py` -> `website/video/python/cli/anime_cli.py`
- Move: `website/video/web_server.py` -> `website/video/python/server/web_server.py`
- Move: `website/video/scripts/*.py` -> `website/video/python/scripts/`
- Rename: `website/video/python/scripts/test_modelscope_i2v.py` -> `website/video/python/scripts/smoke_modelscope_i2v.py`
- Move: `website/video/config.example.json` -> `website/video/config/config.example.json`
- Create: `website/video/anime_cli.py` compatibility wrapper
- Create: `website/video/web_server.py` compatibility wrapper
- Modify: `website/video/python/anime_tools/config.py` to support default config paths and safe config editing
- Modify: `website/video/python/anime_tools/web_api.py` to expose `GET /api/config` and `POST /api/config`
- Modify: `website/video/web/index.html` to add a config panel
- Modify: `website/video/web/app.js` to load/save config and default to `config/config.local.json`
- Modify: `website/video/web/app.css` for config form layout
- Modify: `website/video/.gitignore`, root `.gitignore`, `website/video/README.md`, `AGENTS.md`
- Delete: `website/video/tests/`

## Tasks

### Task 1: Move Files And Preserve Entrypoints

- [ ] Create `config/`, `python/cli/`, `python/server/`, and `python/scripts/`.
- [ ] Move implementation files into the new locations.
- [ ] Create root wrappers that insert `website/video/python` into `sys.path` and call the moved entrypoints.
- [ ] Update script imports so helpers can import `anime_tools` after the move.

### Task 2: Centralize Config And Add Config API

- [ ] Add constants for `WORKSPACE_ROOT`, `CONFIG_DIR`, `DEFAULT_CONFIG_PATH`, `LEGACY_CONFIG_PATH`, and `EXAMPLE_CONFIG_PATH`.
- [ ] Add helpers to resolve default config paths, load editable config, mask sensitive fields, merge updates, and atomically save `config/config.local.json`.
- [ ] Add `WorkbenchService.get_config()` and `WorkbenchService.save_config()`.
- [ ] Add `GET /api/config` and `POST /api/config` routes.

### Task 3: Add UI Config Editing

- [ ] Add a compact config panel in the left sidebar.
- [ ] Load `/api/config` on page startup.
- [ ] Save config through `/api/config`.
- [ ] Use `config/config.local.json` as the default config path for generation, resume, and keyframe regeneration.
- [ ] Keep password fields blank unless the user enters a replacement secret.

### Task 4: Delete Tests And Update Docs

- [ ] Delete `website/video/tests/`.
- [ ] Update ignore rules for `config/config.local.json`.
- [ ] Update README and AGENTS path, startup, config, script, and verification instructions.

### Task 5: Verify Manually

- [ ] Run Python compile checks for moved Python files.
- [ ] Start `python web_server.py`.
- [ ] Check `GET /api/health`.
- [ ] Check `GET /api/config` returns masked config.
- [ ] Check static page loads.
- [ ] Inspect `git status` to confirm deleted tests and moved files are expected.

