# AI Anime MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python CLI that initializes AI anime projects, validates local assets, generates subtitles, renders a preview MP4 through FFmpeg, and outputs Jianying editing guides.

**Architecture:** Keep business logic in a small `anime_tools` package and expose commands through `anime_cli.py`. Tests use temporary directories and avoid requiring FFmpeg by testing command construction separately from command execution.

**Tech Stack:** Python standard library, `unittest`, external FFmpeg executable for actual rendering.

---

## Files

- Create `anime_tools/__init__.py`: package marker and version.
- Create `anime_tools/project.py`: project paths, templates, storyboard parsing, asset validation, subtitles, render command, guide generation.
- Create `anime_cli.py`: command-line entry point.
- Create `tests/test_project.py`: unit tests for project initialization, validation, subtitles, render command, and guide output.

## Tasks

### Task 1: Project Initialization

- [x] Write tests for creating the expected directory tree and template files.
- [x] Implement `init_project`.
- [x] Run tests and confirm pass.

### Task 2: Storyboard Loading And Validation

- [x] Write tests for loading `storyboard.json` and reporting missing assets.
- [x] Implement `load_storyboard` and `check_project`.
- [x] Run tests and confirm pass.

### Task 3: Subtitle Generation

- [x] Write tests for SRT time formatting and shot subtitles.
- [x] Implement `generate_subtitles`.
- [x] Run tests and confirm pass.

### Task 4: Render Command

- [x] Write tests for FFmpeg command construction without executing FFmpeg.
- [x] Implement `build_render_command` and `render_project`.
- [x] Run tests and confirm pass.

### Task 5: Draft Guide

- [x] Write tests for manual cutting guide output.
- [x] Implement `create_draft_guide`.
- [x] Run tests and confirm pass.

### Task 6: CLI

- [x] Write tests through direct function coverage and keep CLI thin.
- [x] Implement `anime_cli.py`.
- [x] Manually verify `init` and `check`.

## Verification

Run:

```bash
python -m unittest discover -s tests -v
python anime_cli.py init "001_雨夜妖刀少女"
python anime_cli.py check "001_雨夜妖刀少女"
```
