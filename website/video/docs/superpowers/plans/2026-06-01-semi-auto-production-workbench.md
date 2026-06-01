# Semi-Auto Production Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Linear-style Web workbench for browsing anime projects, editing dynamic shot lists, regenerating single keyframes, rerendering videos, and viewing task logs.

**Architecture:** Add a small standard-library HTTP layer around existing `anime_tools` modules. Keep file/project operations in `anime_tools.web_api`, long-running operations in `anime_tools.task_manager`, and static browser UI in `web/`.

**Tech Stack:** Python standard library `http.server`, `threading`, `unittest`, existing `anime_tools`, native HTML/CSS/JavaScript.

---

## Files

- Create `anime_tools/task_manager.py`: in-memory single-worker task manager with logs and status.
- Create `anime_tools/web_api.py`: workbench service, path safety, project listing/detail, storyboard saving, keyframe regeneration, render/resume/auto task helpers, and HTTP handler factory.
- Create `web_server.py`: local server entry point bound to `127.0.0.1:5175`.
- Create `web/index.html`: three-column workbench shell.
- Create `web/app.css`: Linear-inspired dark UI.
- Create `web/app.js`: fetch API, render project list/detail, save shots, trigger tasks, poll status.
- Create `tests/test_task_manager.py`: task manager behavior.
- Create `tests/test_web_api.py`: project listing, detail, storyboard save, path safety, fake keyframe regeneration, and HTTP smoke tests.

## Tasks

### Task 1: Task Manager

- [ ] Write tests for successful task execution, failed task execution, and single active task rejection.
- [ ] Implement `TaskManager`, `TaskRecord`, and `TaskBusyError`.
- [ ] Run `python -m unittest tests.test_task_manager -v`.

### Task 2: Workbench Service

- [ ] Write tests for listing projects, rejecting unsafe names, loading dynamic shot details, and saving a storyboard with more than four shots.
- [ ] Implement `WorkbenchService.list_projects`, `get_project`, `save_storyboard`, and path helpers.
- [ ] Run `python -m unittest tests.test_web_api -v`.

### Task 3: Asset And Generation Operations

- [ ] Write tests for regenerating a single keyframe through a fake client and rendering through a fake runner.
- [ ] Implement `regenerate_keyframe`, `generate_subtitles_for_project`, `render_project_video`, `resume_project`, and `auto_project`.
- [ ] Run `python -m unittest tests.test_web_api -v`.

### Task 4: HTTP API

- [ ] Write HTTP smoke tests for `GET /api/projects`, `GET /api/projects/{name}`, `POST /api/projects/{name}/storyboard`, and static file serving.
- [ ] Implement request routing, JSON response helpers, safe file responses, and task submission endpoints.
- [ ] Run `python -m unittest tests.test_web_api -v`.

### Task 5: Frontend Workbench

- [ ] Create the native HTML shell.
- [ ] Implement Linear-style CSS tokens and three-column layout.
- [ ] Implement JavaScript project loading, detail rendering, shot save, keyframe regeneration, subtitle generation, rerender, resume, auto generation, and task polling.
- [ ] Verify the page loads through `python web_server.py`.

### Task 6: Final Verification

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Start `python web_server.py`.
- [ ] Open `http://127.0.0.1:5175` and verify the workbench renders in the in-app browser.
