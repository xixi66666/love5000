---
version: 1
slug: "ill-finder-frontend-src-views-dailyreportsview-vue"
primary_target: "website/skill-finder/frontend/src/views/DailyReportsView.vue"
related_targets: ["website/skill-finder/frontend/src/assets/styles/daily-console.css"]
---

Mode: Operate. Scope: /daily-reports, existing Skill Finder visual system.
Audience/job: one operator watches the complete AI video workflow and handles blocked steps.
Primary action: run today once, inspect true phase and per-scene/frame counts, then review the exact artifact before publishing.
Structure: date/action header, collapsible management/environment panel, status strip, process rail and selected-step work surface; horizontal rail on narrow screens.
Proof: durable workflow events, actual Remotion progress, real media artifacts; historical records marked untracked. Samples cannot authorize a daily report.
Constraints: no credentials in browser storage; server writes require admin auth and safe origin; no automatic publication or deployments during validation.
Template development: integrated React/TSX editing and visual theme controls, isolated real Remotion Player, compile diagnostics, save after a render check, immutable versions and restore. Preserve workflow state while switching panels; new templates affect future generation only.
