# Last 30 Days Module

This module adapts the user-level `last30days` skill to Skill Finder. It runs the installed engine as a subprocess and returns its agent JSON profile instead of maintaining a separate Hacker News-only implementation.

The primary use case is the **近 30 天最热** page: per-direction (`agent` / `skill`) Top 20 rankings of the hottest discussions and projects over the last 30 days. Refreshing a direction runs the engine with a fixed query (`AI agents` / `AI agent skills`), ranks results by total engagement, and caches the Top 20 in the `last30days_reports` table so page loads are instant.

## API

- `GET /api/v1/last30days/status` checks the installed skill/runtime and lists currently available sources.
- `GET /api/v1/last30days/rankings?direction=agent|skill` returns the cached ranking for a direction (empty state when never refreshed).
- `POST /api/v1/last30days/rankings/refresh` with `{ "direction": "agent" }` synchronously reruns the engine and updates the cached ranking. This can take several minutes.
- `POST /api/v1/last30days` runs research for an arbitrary topic (kept for debugging; not used by the UI).

```json
{
  "query": "OpenAI Codex",
  "limit": 20
}
```

Ranking responses contain `items` (Top 20), `clusters`, `sources`, per-source status, and `fetched_at`. The UI is available from the primary navigation as **近 30 天最热**.

## Runtime discovery

By default the adapter searches these user-level installations:

1. `~/.codex/skills/last30days`
2. `~/.agents/skills/last30days`
3. `~/.claude/skills/last30days`

It also discovers Python 3.12+ from the current interpreter, `PATH`, or a bundled Codex runtime. Override discovery only when necessary:

| Variable | Purpose |
| --- | --- |
| `LAST30DAYS_ENABLED` | Enable or disable the module |
| `LAST30DAYS_SKILL_DIR` | Explicit installed skill directory |
| `LAST30DAYS_PYTHON` | Explicit Python 3.12+ executable |
| `LAST30DAYS_MEMORY_DIR` | Optional research artifact directory |
| `LAST30DAYS_TIMEOUT_SECONDS` | Subprocess timeout, default 600 seconds |

The subprocess receives only basic operating-system variables, `LAST30DAYS_*` configuration, and credential variables understood by the skill. Skill Finder database and admin configuration are not forwarded.

## Data access

Submitting research sends the topic to the external sources enabled by the user's `last30days` installation. The status endpoint exposes those sources before a run. Source availability depends on the local skill configuration and optional credentials.
