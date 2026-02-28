# PRD — Mission Control V1 (Website Dashboard)

> **Status:** COMPLETED — Deployed February 2026
>
> **Companion PRD:** See [open-claw-external-services.prd.md](./open-claw-external-services.prd.md) for the Telemetry Exporter, CLI Tool, Email Control Plane, Mac Mini Hardening, and Agent Integration specs.

## 0. Build Philosophy and Quality Bar

### Reliability goal

Mission Control must work out of the box on first deploy and remain stable as usage scales.

### Testing approach

We will use TDD where it makes sense, specifically for:

* Telemetry ingestion and idempotency
* State transitions (jobs, sessions, connectors)
* Cost and rollup calculations
* Access control and authorization boundaries
* Any parsing or transformation logic

UI testing will be targeted:

* Critical pages render in empty and seeded states
* Core flows work end to end
* Avoid brittle snapshot overuse

Testing infrastructure: Jest 30 + React Testing Library (already configured in the project).

### Definition of Done (global)

A feature is done only when:

* It is covered by the required tests for its module
* It has clear error handling and user-visible failure states
* It produces expected database writes and can be verified in the UI
* It is documented in the internal runbook (short, practical)



## 1. Overview

Mission Control is the centralized operational dashboard and task system for:

* AI agents (Rachel AI, Vanessa AI)
* Sessions and token usage
* Jobs and execution tracking
* System health (via telemetry exporter)
* Projects and tasks (replacing Notion)

It lives inside the existing MBrowne website (`website/`) as a self-contained dashboard area within the admin panel. It uses **Supabase Auth** for authentication and **Supabase** (PostgreSQL) for all data.

No direct Mission Control ↔ Mac Mini connectivity in V1. The Mac Mini pushes telemetry to the Mission Control API on a schedule.

Mission Control becomes the source of truth. Agents become workers that read and write to it.

### Primary model

The current primary model for both agents is **GPT Codex 5.1** (`gpt-codex-5.1`). Pricing: $1.25 / 1M input tokens, $10.00 / 1M output tokens.



## 2. Architecture

### Existing stack (already in place)

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v4 |
| Database | Supabase (PostgreSQL, ca-central-1) |
| Auth | Supabase Auth |
| Validation | Zod 4 |
| Charts | Recharts 3 |
| Testing | Jest 30 + React Testing Library |
| Deployment | Vercel |

### Existing admin panel (integration points)

| Item | Path |
|---|---|
| Admin layout | `website/src/app/(admin)/admin/layout.tsx` |
| Auth guard | `website/src/components/admin/AdminGuard.tsx` |
| Sign-out button | `website/src/components/admin/AdminSignOutButton.tsx` |
| Login page | `website/src/app/(admin)/admin/login/` |
| Supabase clients | `website/src/lib/supabaseClient.ts` |
| Type definitions | `website/src/types/` |
| API route pattern | `website/src/app/api/admin/` |
| Stub mode env var | `NEXT_PUBLIC_USE_SUPABASE_STUB` |

Mission Control **reuses** the Supabase client layer (`getSupabaseClient` / `getSupabaseServiceClient`), the `AdminGuard` for auth gating, and the existing stub-mode pattern for local development.

### Components

1. **Mac Mini** — OpenClaw runs here. Telemetry Exporter (new, separate service) pushes metrics to the Mission Control ingest API on a schedule.

2. **Supabase** — Stores observability, jobs, projects, tasks. All Mission Control tables live in the same Supabase project as the rest of the website.

3. **Website (Mission Control)** — Self-contained dashboard area with its own layout. Reads from Supabase for display. Exposes API routes for telemetry ingestion and CRUD.

### Data flow

```
Mac Mini exporter → POST /api/mission-control/telemetry/ingest → Supabase → Mission Control UI
Admin user → Mission Control UI → API routes → Supabase
Agents (via CLI) → API routes → Supabase → Mission Control UI
```



## 3. Goals

### Primary goals

1. Visibility into token burn and session sprawl
2. Replace Notion with a first-party projects/tasks system
3. Create a job dispatch and job tracking system
4. Reduce operational dependency on chat connectors

### Non-goals (V1)

* Live streaming and WebSocket status
* Remotely controlling OpenClaw from Mission Control
* Slack/Discord integrations
* Exposing the Mac Mini or OpenClaw Gateway publicly



## 4. Telemetry Model

### Update frequency

Telemetry exporter schedule (configurable via env on Mac Mini):

* Every 60 seconds during business hours
* Every 300 seconds after hours

### Telemetry payload principles

* Metrics only
* No transcripts
* No client docs
* No message bodies
* Only IDs and aggregates needed for visibility

### Freshness and "stale" semantics

* Agent stale threshold: no heartbeat in 3× polling interval
* System stale threshold: no system_health update in 3× polling interval
* Session stale threshold: no session activity update in 60 minutes (configurable)

These thresholds are stored in the `mc_settings` table and editable from the admin UI.

### Telemetry payload structure

```json
{
  "timestamp": "2026-02-27T14:30:00Z",
  "agents": [
    {
      "name": "Rachel AI",
      "model": "gpt-codex-5.1",
      "last_heartbeat_at": "2026-02-27T14:29:55Z",
      "sessions": [
        {
          "openclaw_session_id": "abc123",
          "model": "gpt-codex-5.1",
          "started_at": "2026-02-27T09:15:00Z",
          "last_activity_at": "2026-02-27T14:29:50Z",
          "input_tokens": 12000,
          "output_tokens": 4000,
          "total_tokens": 16000,
          "compaction_count": 2,
          "last_error": null
        }
      ]
    }
  ],
  "system_health": {
    "cpu_percent": 32.5,
    "memory_percent": 54.1,
    "disk_percent": 62.2,
    "uptime_seconds": 921233
  }
}
```



## 5. Data Model (Supabase)

All tables use `uuid` primary keys with `gen_random_uuid()` defaults, `timestamptz` for timestamps, and `now()` defaults for `created_at`. All tables have RLS enabled.

### mc_agents

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| name | text | not null, unique |
| role | text | not null |
| default_model | text | not null |
| status | text | not null, default 'offline', check in ('online','stale','offline') |
| last_heartbeat_at | timestamptz | |
| last_error | text | |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

### mc_sessions

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| agent_id | uuid | FK → mc_agents.id, not null |
| openclaw_session_id | text | not null |
| model | text | not null |
| started_at | timestamptz | not null |
| last_activity_at | timestamptz | |
| input_tokens | integer | default 0 |
| output_tokens | integer | default 0 |
| total_tokens | integer | default 0 |
| compaction_count | integer | default 0 |
| status | text | not null, default 'active', check in ('active','stale','archived') |
| last_error | text | |
| is_watched | boolean | default false |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

Unique constraint on `(agent_id, openclaw_session_id)` for idempotent upserts.

### mc_daily_costs

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| date | date | not null |
| agent_id | uuid | FK → mc_agents.id, not null |
| model | text | not null |
| input_tokens | integer | default 0 |
| output_tokens | integer | default 0 |
| total_tokens | integer | default 0 |
| estimated_cost_usd | numeric(10,4) | default 0 |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

Unique constraint on `(date, agent_id, model)` for idempotent upserts.

### mc_system_health

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| cpu_percent | numeric(5,2) | |
| memory_percent | numeric(5,2) | |
| disk_percent | numeric(5,2) | |
| uptime_seconds | integer | |
| recorded_at | timestamptz | not null |
| created_at | timestamptz | default now() |

Dedupe: reject inserts where `recorded_at` is within 30 seconds of the most recent row.

### mc_connectors

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| name | text | not null |
| type | text | not null |
| status | text | not null, default 'unknown', check in ('connected','disconnected','error','unknown') |
| last_seen_at | timestamptz | |
| config | jsonb | default '{}' |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

### mc_jobs

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| title | text | not null |
| description | text | |
| agent_id | uuid | FK → mc_agents.id |
| priority | text | not null, default 'normal', check in ('low','normal','high','urgent') |
| status | text | not null, default 'queued', check in ('queued','running','completed','failed','cancelled') |
| input_payload | jsonb | |
| input_hash | text | for duplicate detection |
| output_ref | text | |
| error_message | text | |
| queued_at | timestamptz | default now() |
| started_at | timestamptz | |
| completed_at | timestamptz | |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

### mc_job_runs

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| job_id | uuid | FK → mc_jobs.id, not null |
| attempt | integer | not null |
| status | text | not null, check in ('running','completed','failed') |
| started_at | timestamptz | not null |
| completed_at | timestamptz | |
| output_ref | text | |
| error_message | text | |
| created_at | timestamptz | default now() |

Unique constraint on `(job_id, attempt)`.

### mc_projects

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| name | text | not null |
| description | text | |
| status | text | not null, default 'active', check in ('active','paused','completed','archived') |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

### mc_tasks

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| project_id | uuid | FK → mc_projects.id |
| title | text | not null |
| description | text | |
| status | text | not null, default 'todo', check in ('todo','in_progress','in_review','done','cancelled') |
| priority | text | not null, default 'normal', check in ('low','normal','high','urgent') |
| assigned_agent_id | uuid | FK → mc_agents.id |
| due_date | date | |
| completed_at | timestamptz | |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | default now() |

### mc_task_comments

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| task_id | uuid | FK → mc_tasks.id, not null |
| author | text | not null |
| body | text | not null |
| created_at | timestamptz | default now() |

### mc_task_links

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| task_id | uuid | FK → mc_tasks.id, not null |
| label | text | not null |
| url | text | not null |
| created_at | timestamptz | default now() |

### mc_model_pricing

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| model | text | not null, unique |
| input_cost_per_1m | numeric(10,4) | not null |
| output_cost_per_1m | numeric(10,4) | not null |
| effective_from | date | not null, default current_date |
| created_at | timestamptz | default now() |

Cost estimation formula: `(input_tokens / 1_000_000 * input_cost_per_1m) + (output_tokens / 1_000_000 * output_cost_per_1m)`.

### mc_settings

| column | type | constraints |
|---|---|---|
| key | text | PK |
| value | jsonb | not null |
| updated_at | timestamptz | default now() |

Stores configurable thresholds (stale intervals, business hours definition, etc.) in a key-value format. Editable from the admin UI.

### mc_ingest_log

| column | type | constraints |
|---|---|---|
| id | uuid | PK, default gen_random_uuid() |
| status | text | not null, check in ('success','error') |
| payload_size_bytes | integer | |
| error_message | text | |
| created_at | timestamptz | default now() |

Tracks every telemetry ingest attempt for observability. Older rows can be pruned on a schedule.

### Table naming convention

All Mission Control tables are prefixed with `mc_` to avoid collisions with existing website tables (`posts`, `questionnaires`, `landing_pages`, etc.).



## 6. UI Layout and Navigation

### Dashboard layout

Mission Control has its **own layout**, separate from the standard admin content-management layout. It uses a sidebar navigation pattern suited for dashboard workflows.

**Route group:** `website/src/app/(admin)/admin/mission-control/`

**Layout file:** `website/src/app/(admin)/admin/mission-control/layout.tsx`

The layout includes:

* **Sidebar** — Navigation links for all Mission Control screens, plus a back link to `/admin`
* **Header** — Page title, last sync time indicator, sign-out button
* **Main content area** — Full width for dashboards and data tables

The `AdminGuard` from the existing admin panel wraps the Mission Control layout to enforce authentication. No additional auth layer needed.

### Navigation structure

```
← Back to Admin Home (/admin)

Mission Control
├── Overview          /admin/mission-control
├── Agents            /admin/mission-control/agents
├── Sessions          /admin/mission-control/sessions
├── Jobs              /admin/mission-control/jobs
├── Projects          /admin/mission-control/projects
└── Tasks             /admin/mission-control/tasks
```

### Screen specifications

#### 1) Overview (`/admin/mission-control`)

KPI cards row:
* Tokens today (sum across agents)
* Estimated cost today (USD)
* Active sessions count
* Stale sessions count
* Jobs queued / running / failed

Status section:
* Agent status cards (online / stale / offline per agent)
* Last telemetry sync time
* Last ingest error (if any)
* System health snapshot (CPU / memory / disk gauges)

Charts (Recharts):
* Token burn over last 7 days (line chart, per agent)
* Cost trend over last 7 days (bar chart)

#### 2) Agents (`/admin/mission-control/agents`)

Card per agent showing:
* Name, role, default model
* Status badge and last heartbeat (relative time)
* Tokens today and 7-day rolling total
* Active sessions count
* Last error (if any)

#### 3) Sessions (`/admin/mission-control/sessions`)

Sortable, filterable data table:
* Columns: Agent, Model, Started, Last Activity, Tokens In, Tokens Out, Total, Compactions, Status
* Filters: Agent, Status, Date range
* Sorting: Any column
* Actions: Archive session, Toggle watch flag

#### 4) Jobs (`/admin/mission-control/jobs`)

List view with filters (status, priority, agent) and a "Create Job" form.

Per job:
* Title, description, assigned agent, priority
* Status with lifecycle badges
* Results and failure info
* Expandable attempt history from `mc_job_runs`

Create/edit form:
* Title, description, agent assignment, priority, input payload (JSON)

#### 5) Projects (`/admin/mission-control/projects`)

List view with status filter.

Per project:
* Name, description, status
* Task counts grouped by status (e.g., "3 todo, 2 in progress, 5 done")

Create/edit form:
* Name, description, status

#### 6) Tasks (`/admin/mission-control/tasks`)

List view with filters (project, status, priority, assigned agent, due date).

Per task:
* Title, project, status, priority, assigned agent, due date
* Expandable detail with description, comments, and links

Create/edit form:
* Title, description, project, status, priority, agent, due date
* Add comments
* Add links (label + URL)



## 7. API Layer

### Why an API layer?

To enforce validation, idempotency, security (service role server-side only), and consistent writes. All writes go through Next.js API routes. The UI reads directly from Supabase via the anon client where appropriate, but all mutations use API routes.

### Endpoint inventory

#### Telemetry (exporter-secret auth)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/mission-control/telemetry/ingest` | Exporter secret (`X-MC-Secret` header) | Receive telemetry payload from Mac Mini |

#### Agents (admin session auth)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mission-control/agents` | List agents |
| GET | `/api/mission-control/agents/[id]` | Get agent detail |

#### Sessions (admin session auth)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mission-control/sessions` | List sessions (with filters) |
| PATCH | `/api/mission-control/sessions/[id]` | Archive session or toggle watch |

#### Jobs (admin session auth + API token for CLI)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mission-control/jobs` | List jobs (with filters) |
| GET | `/api/mission-control/jobs/[id]` | Get job detail with runs |
| POST | `/api/mission-control/jobs` | Create job |
| PATCH | `/api/mission-control/jobs/[id]` | Update job status |

#### Projects (admin session auth)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mission-control/projects` | List projects |
| POST | `/api/mission-control/projects` | Create project |
| GET | `/api/mission-control/projects/[id]` | Get project detail |
| PATCH | `/api/mission-control/projects/[id]` | Update project |
| DELETE | `/api/mission-control/projects/[id]` | Delete project |

#### Tasks (admin session auth)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mission-control/tasks` | List tasks (with filters) |
| POST | `/api/mission-control/tasks` | Create task |
| GET | `/api/mission-control/tasks/[id]` | Get task with comments and links |
| PATCH | `/api/mission-control/tasks/[id]` | Update task |
| DELETE | `/api/mission-control/tasks/[id]` | Delete task |
| POST | `/api/mission-control/tasks/[id]/comments` | Add comment |
| POST | `/api/mission-control/tasks/[id]/links` | Add link |

#### Settings (admin session auth)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mission-control/settings` | Get all settings |
| PATCH | `/api/mission-control/settings` | Update settings |
| GET | `/api/mission-control/model-pricing` | Get pricing table |
| PUT | `/api/mission-control/model-pricing` | Update pricing table |

### Telemetry ingest logic

When a telemetry payload arrives at `/api/mission-control/telemetry/ingest`:

1. Validate `X-MC-Secret` header against `MC_TELEMETRY_SECRET` env var
2. Validate payload schema with Zod
3. For each agent in payload:
   a. Upsert into `mc_agents` by name
   b. For each session: upsert into `mc_sessions` by `(agent_id, openclaw_session_id)`
   c. Recalculate `mc_daily_costs` for today by `(date, agent_id, model)` — always recompute from token totals, never increment
4. Insert `mc_system_health` snapshot (reject if `recorded_at` within 30s of latest)
5. Log result to `mc_ingest_log`
6. Return success

All wrapped in a transaction where possible.

### Validation

All write endpoints validate payload shape with Zod and reject unexpected fields. Zod schemas live in `website/src/lib/mission-control/schemas.ts`.

### Auth patterns

* **Telemetry ingest:** `X-MC-Secret` header checked against `MC_TELEMETRY_SECRET` env var. Not accessible from browser.
* **Admin UI routes:** Supabase session auth via `AdminGuard` (existing pattern). API routes verify session server-side.
* **CLI / agent access (future):** API token in `Authorization: Bearer <token>` header. Token stored in `mc_settings`.



## 8. Idempotency and Data Correctness

### Telemetry ingestion

* Duplicate exporter sends do not inflate totals
* Sessions upsert by `(agent_id, openclaw_session_id)` — token counts are **replaced**, not accumulated
* `mc_daily_costs` upsert by `(date, agent_id, model)` — cost is **recalculated** from current session token totals
* `mc_system_health` insert with `recorded_at`, dedupe window of 30 seconds

### Job updates

* Job status transitions are enforced: `queued → running → completed|failed`, `* → cancelled`
* Invalid transitions return 409 Conflict
* Duplicate status update (same status) is a no-op, does not create extra `mc_job_runs`
* Each job can carry an `input_hash` — duplicate job submission with same hash returns existing job instead of creating new one



## 9. Cost Estimation

Estimated cost is computed from token counts and the `mc_model_pricing` table.

Formula: `(input_tokens / 1,000,000 × input_cost_per_1m) + (output_tokens / 1,000,000 × output_cost_per_1m)`

Requirements:

* Multiple models supported via `mc_model_pricing` rows
* Each agent has a `default_model` but sessions can use different models
* Pricing is editable from the Mission Control UI (model pricing settings screen)
* If a model has no pricing entry, cost shows as "N/A" in the UI

### Seed pricing data

| model | input_cost_per_1m | output_cost_per_1m |
|---|---|---|
| gpt-codex-5.1 | 1.25 | 10.00 |
| claude-sonnet-4 | 3.00 | 15.00 |
| claude-haiku-3.5 | 0.80 | 4.00 |
| claude-opus-4 | 15.00 | 75.00 |
| gpt-4o | 2.50 | 10.00 |
| gpt-4o-mini | 0.15 | 0.60 |



## 10. Mock and Seed Data

A comprehensive mock dataset is used for:

* **Stub mode development** — When `NEXT_PUBLIC_USE_SUPABASE_STUB=true`, the UI renders using mock data so developers can work without a Supabase connection. This follows the existing pattern used by blog, questionnaire, and landing page admin pages.
* **Automated tests** — Tests import mock data directly.
* **Supabase seed script** — A SQL seed file can populate a dev database for integration testing.

### Mock data location

`website/src/data/mission-control/` (following the existing pattern in `website/src/data/`)

### Mock data contents

**Agents (2):**
* Rachel AI — role: "Lead Operations Agent", model: gpt-codex-5.1, status: online
* Vanessa AI — role: "Research & Content Agent", model: gpt-codex-5.1, status: stale

**Sessions (6):**
* 3 active sessions for Rachel AI (primary on gpt-codex-5.1, others on gpt-4o and claude-haiku-3.5 for variety)
* 2 active sessions for Vanessa AI (primary on gpt-codex-5.1, one on gpt-4o-mini)
* 1 archived session for Rachel AI (gpt-codex-5.1)

**Daily costs (14 rows):**
* 7 days of cost data for each agent, realistic token counts trending upward

**System health (3 snapshots):**
* Healthy snapshot (CPU 28%, Memory 52%, Disk 61%)
* Moderate load snapshot (CPU 67%, Memory 78%, Disk 61%)
* Recent snapshot matching "now"

**Jobs (5):**
* 1 queued, 1 running, 2 completed, 1 failed
* The failed job has 2 job_runs (first failed, retry also failed)
* The completed jobs have 1 job_run each

**Projects (3):**
* "Website V2 Launch" — active, 8 tasks
* "SEO Content Pipeline" — active, 5 tasks
* "Client Onboarding Automation" — paused, 3 tasks

**Tasks (16):**
* Distributed across the 3 projects with varying statuses, priorities, and agent assignments
* Some with due dates, some without
* Several with 1-3 comments each
* Several with 1-2 links each

**Model pricing (6 rows):**
* Matches the seed pricing table in Section 9 (including gpt-codex-5.1)

**Settings:**
* `agent_stale_threshold_minutes: 3`
* `system_stale_threshold_minutes: 3`
* `session_stale_threshold_minutes: 60`
* `business_hours_start: 8`
* `business_hours_end: 18`
* `business_hours_timezone: "America/Toronto"`

**Ingest log (3 rows):**
* 2 success entries, 1 error entry



## 11. Testing Requirements

### Required automated tests

**Telemetry:**
* Creates agent if missing
* Upserts sessions deterministically
* Idempotency: repeated payload does not inflate totals
* Rejects invalid payloads (missing fields, wrong types)
* Rejects requests without valid exporter secret
* Logs ingest results to `mc_ingest_log`

**Cost calculation:**
* Computes cost correctly for known models
* Returns null/N/A for unknown models
* Daily cost rollup recalculates, not increments

**Jobs:**
* Valid transitions only (queued → running → completed|failed)
* Invalid transitions return 409
* `mc_job_runs` attempt increments on retry
* Failure states store error message and timestamp
* Duplicate input_hash returns existing job

**Projects / Tasks:**
* CRUD operations work
* Comments append reliably
* Links attach reliably
* Deleting a project cascades or blocks based on task count

**Access control:**
* Unauthed requests to admin API routes return 401
* Telemetry ingest without valid secret returns 401
* Authenticated admin requests succeed

### Seed data tests

Mock data renders correctly on every Mission Control screen in both empty state and seeded state.



## 12. Security and Permissions

* **Supabase Auth** required for all admin-facing routes (enforced by `AdminGuard`)
* Only the admin user can access Mission Control routes
* **Supabase RLS** enabled on all `mc_*` tables
* Service role key (`SUPABASE_SERVICE_ROLE_KEY`) never exposed to client — used only in API routes
* Telemetry exporter authenticates using `MC_TELEMETRY_SECRET` env var via `X-MC-Secret` header
* Telemetry endpoint should support IP allowlist later, but not required for V1

### Environment variables (new for Mission Control)

| Variable | Where | Purpose |
|---|---|---|
| `MC_TELEMETRY_SECRET` | Vercel + Mac Mini | Shared secret for telemetry ingest auth |



## 13. Observability for Mission Control Itself

Mission Control logs telemetry ingest results to `mc_ingest_log`:

* Every ingest attempt (success or error)
* Payload size
* Error messages for failures

The Overview dashboard displays:

* Last successful ingest time
* Last ingest error (if any)
* Count of ingest errors in the last 24 hours

Server-side console logging for:

* Auth failures on API routes
* Zod validation failures with rejected payload shape



## 14. Build Status

> All items below were completed and deployed in February 2026.

| # | Step | Status |
|---|---|---|
| 1 | Database schema — SQL migration for all `mc_*` tables, RLS policies, indexes, seed data | COMPLETED |
| 2 | Types and validation — TypeScript types, Zod schemas | COMPLETED |
| 3 | Mock data — Full mock dataset | COMPLETED |
| 4 | Services layer — Data access functions for all entities | COMPLETED |
| 5 | API routes — All endpoints listed in Section 7, including telemetry ingest | COMPLETED |
| 6 | Dashboard layout — Sidebar, back link, header | COMPLETED |
| 7 | Overview page — KPI cards, status indicators, charts | COMPLETED |
| 8 | Agents page — Agent cards with status and metrics | COMPLETED |
| 9 | Sessions page — Data table with filters and actions | COMPLETED |
| 10 | Jobs page — List, create, status management, run history | COMPLETED |
| 11 | Projects page — List, create, edit with task counts | COMPLETED |
| 12 | Tasks page — List, create, edit with comments and links | COMPLETED |
| 13 | Settings — Model pricing editor, threshold configuration | COMPLETED |
| 14 | Tests — Unit tests for services and ingest logic, basic render tests for UI | COMPLETED |

### What's deployed and ready for external services

* The **telemetry ingest endpoint** (`POST /api/mission-control/telemetry/ingest`) is live and accepting payloads authenticated with `X-MC-Secret`.
* All **CRUD API routes** for jobs, projects, tasks, settings, and model pricing are live and ready for CLI or agent consumption.
* The **database schema** is deployed to Supabase with initial agent rows (Rachel AI, Vanessa AI) and model pricing seeded.
* `MC_TELEMETRY_SECRET` is set in both Vercel and `.env.local`.

### Separate builds (not part of this website deliverable)

These are documented in the companion PRD ([open-claw-external-services.prd.md](./open-claw-external-services.prd.md)):

* Telemetry Exporter (runs on Mac Mini)
* Mission Control CLI Tool (runs on Mac Mini / by agents)
* Email Control Plane (runs on Mac Mini)
* Mac Mini Server Hardening (ops/infra)



## 15. File Structure

```
website/src/
├── app/(admin)/admin/mission-control/
│   ├── layout.tsx                        # Dashboard layout with sidebar
│   ├── page.tsx                          # Overview dashboard
│   ├── agents/
│   │   └── page.tsx                      # Agents list
│   ├── sessions/
│   │   └── page.tsx                      # Sessions table
│   ├── jobs/
│   │   ├── page.tsx                      # Jobs list
│   │   └── [id]/page.tsx                 # Job detail (optional)
│   ├── projects/
│   │   ├── page.tsx                      # Projects list
│   │   └── [id]/page.tsx                 # Project detail (optional)
│   └── tasks/
│       ├── page.tsx                      # Tasks list
│       └── [id]/page.tsx                 # Task detail (optional)
├── app/api/mission-control/
│   ├── telemetry/ingest/route.ts
│   ├── agents/route.ts
│   ├── agents/[id]/route.ts
│   ├── sessions/route.ts
│   ├── sessions/[id]/route.ts
│   ├── jobs/route.ts
│   ├── jobs/[id]/route.ts
│   ├── projects/route.ts
│   ├── projects/[id]/route.ts
│   ├── tasks/route.ts
│   ├── tasks/[id]/route.ts
│   ├── tasks/[id]/comments/route.ts
│   ├── tasks/[id]/links/route.ts
│   ├── settings/route.ts
│   └── model-pricing/route.ts
├── components/mission-control/
│   ├── MCLayout.tsx                      # Sidebar + header wrapper
│   ├── MCSidebar.tsx                     # Navigation sidebar
│   ├── KpiCard.tsx                       # Metric card component
│   ├── StatusBadge.tsx                   # Status indicator badge
│   ├── AgentCard.tsx                     # Agent summary card
│   ├── SessionsTable.tsx                 # Sortable/filterable table
│   ├── JobsList.tsx                      # Jobs list with status
│   ├── JobRunHistory.tsx                 # Attempt history accordion
│   ├── ProjectCard.tsx                   # Project with task counts
│   ├── TaskList.tsx                      # Filterable task list
│   ├── TaskDetail.tsx                    # Task with comments + links
│   ├── SystemHealthGauges.tsx            # CPU/mem/disk gauges
│   ├── TokenBurnChart.tsx                # 7-day token chart
│   ├── CostTrendChart.tsx                # 7-day cost chart
│   └── IngestStatus.tsx                  # Last sync + error indicator
├── lib/mission-control/
│   ├── schemas.ts                        # Zod validation schemas
│   ├── constants.ts                      # Status enums, defaults
│   ├── costs.ts                          # Cost calculation logic
│   └── services/
│       ├── agentsService.ts
│       ├── sessionsService.ts
│       ├── jobsService.ts
│       ├── projectsService.ts
│       ├── tasksService.ts
│       ├── telemetryService.ts
│       ├── costsService.ts
│       └── settingsService.ts
├── types/mission-control.ts              # TypeScript type definitions
└── data/mission-control/
    ├── mockAgents.ts
    ├── mockSessions.ts
    ├── mockDailyCosts.ts
    ├── mockSystemHealth.ts
    ├── mockJobs.ts
    ├── mockProjects.ts
    ├── mockTasks.ts
    ├── mockSettings.ts
    └── mockIngestLog.ts
```



## 16. Success Criteria

Mission Control is successful when:

* You can see token burn today by agent and by model
* You can identify top sessions by burn and age
* You can see "Mac Mini stopped reporting" within 5 minutes
* You can manage projects and tasks without Notion
* You can create and track jobs with outputs and retries
* Failures are visible and diagnosable without going to the Mac Mini
* The telemetry ingest endpoint is live and ready for the Mac Mini exporter to push to
* Mock data renders correctly on all screens for local development

---

# PRD — OpenClaw External Services

> **Prerequisite:** The Mission Control website dashboard is built and deployed. See [open-claw-mission-control.prd.md](./open-claw-mission-control.prd.md) for the complete dashboard PRD.
>
> **What's already live:**
> * Telemetry ingest endpoint: `POST /api/mission-control/telemetry/ingest` (auth: `X-MC-Secret` header)
> * All CRUD API routes for agents, sessions, jobs, projects, tasks, settings, and model pricing
> * Standalone job-runs API: `GET /api/mission-control/job-runs`, `POST`, `PATCH /job-runs/[id]`
> * Task comments/links APIs: `GET` + `POST` on `/tasks/[id]/comments` and `/tasks/[id]/links`
> * Mission commentary API: `GET` + `POST` on `/api/mission-control/commentary`
> * All CLI-facing API routes secured with `X-MC-Secret` header validation
> * Database schema deployed with RLS policies, indexes, and seed data (including `mc_commentary` table)
> * Initial agents seeded: Rachel AI and Vanessa AI (default model: `gpt-codex-5.1`)
> * Model pricing seeded: gpt-codex-5.1, claude-sonnet-4, claude-haiku-3.5, claude-opus-4, gpt-4o, gpt-4o-mini

This document covers the services that run on the Mac Mini and push data to Mission Control via its API. All communication is **outbound from the Mac Mini** — Mission Control never connects inbound to the Mac Mini.



## Architecture Overview

```
┌─────────────────────────────────────────┐
│              Mac Mini                    │
│                                         │
│  ┌───────────┐  ┌────────────────────┐  │
│  │  OpenClaw  │  │ Telemetry Exporter │  │
│  └───────────┘  └────────┬───────────┘  │
│                          │              │
│  ┌───────────┐           │              │
│  │ MC CLI    │───────────┤              │
│  └───────────┘           │              │
│                          │              │
│   All traffic is         │              │
│   OUTBOUND HTTPS ────────┤              │
│                          │              │
└──────────────────────────┼──────────────┘
                           │
                           ▼
┌──────────────────────────────────────────┐
│        Website (Vercel / Next.js)        │
│  ┌────────────────────────────────────┐  │
│  │  POST /api/mission-control/        │  │
│  │       telemetry/ingest             │  │
│  │  GET/POST/PATCH /api/mission-      │  │
│  │       control/{resources}          │  │
│  └──────────────┬─────────────────────┘  │
│                 │                         │
│  ┌──────────────▼─────────────────────┐  │
│  │     Mission Control Dashboard      │  │
│  │  /admin/mission-control/*          │  │
│  └────────────────────────────────────┘  │
└──────────────────────┬───────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────┐
│           Supabase (ca-central-1)        │
│                                          │
│  Mission Control tables (mc_*):          │
│    mc_agents, mc_sessions,               │
│    mc_daily_costs, mc_system_health,     │
│    mc_connectors, mc_jobs, mc_job_runs,  │
│    mc_projects, mc_tasks,                │
│    mc_task_comments, mc_task_links,      │
│    mc_model_pricing, mc_settings,        │
│    mc_ingest_log, mc_commentary          │
└──────────────────────────────────────────┘
```

**Key principle:** The Mac Mini never needs to be reachable from the internet. It only makes outbound HTTPS calls to the Vercel-hosted API. Mission Control reads everything from Supabase.



---



# 1. Telemetry Exporter (Mac Mini)

> **Status:** NOT STARTED — ready to build now. The API endpoint it pushes to is live.

## 1.1 Purpose

The Telemetry Exporter runs locally on the Mac Mini and pushes operational metrics to the Mission Control ingest API on a schedule.

It does NOT:

* Store transcripts
* Store client data
* Store document contents
* Expose OpenClaw publicly

It only pushes metrics and health signals.

## 1.2 Responsibilities

Every polling cycle:

1. Read OpenClaw session data (however OpenClaw stores it locally)
2. Extract per-session metrics (openclaw_session_id, model, tokens, compactions, errors)
3. Capture system health (CPU %, Memory %, Disk %, Uptime)
4. POST telemetry payload to the Mission Control ingest endpoint with `X-MC-Secret` header

## 1.3 Polling Schedule

* Business hours: every 60 seconds
* After hours: every 300 seconds
* Schedule configurable via env

## 1.4 Payload Structure

The ingest endpoint expects this exact shape (validated by Zod on the server):

```json
{
  "timestamp": "2026-02-27T14:30:00Z",
  "agents": [
    {
      "name": "Rachel AI",
      "model": "gpt-codex-5.1",
      "last_heartbeat_at": "2026-02-27T14:29:55Z",
      "sessions": [
        {
          "openclaw_session_id": "abc123",
          "model": "gpt-codex-5.1",
          "started_at": "2026-02-27T09:15:00Z",
          "last_activity_at": "2026-02-27T14:29:50Z",
          "input_tokens": 12000,
          "output_tokens": 4000,
          "total_tokens": 16000,
          "compaction_count": 2,
          "last_error": null
        }
      ]
    }
  ],
  "system_health": {
    "cpu_percent": 32.5,
    "memory_percent": 54.1,
    "disk_percent": 62.2,
    "uptime_seconds": 921233
  }
}
```

### Field notes

* `timestamp` — ISO 8601 with timezone. The exporter's wall-clock time when the payload was assembled.
* `agents[].name` — Must match a known agent name. The server upserts by name, so new agents are created automatically.
* `agents[].model` — The agent's current default model. Used for agent-level display.
* `agents[].sessions[].model` — The model used for that specific session (may differ from the agent default).
* `agents[].sessions[].openclaw_session_id` — The OpenClaw-internal session ID. Used as the upsert key together with agent_id. Must be stable across polling cycles for the same session.
* Token counts (`input_tokens`, `output_tokens`, `total_tokens`) — **Absolute totals**, not deltas. The server replaces stored values, it does not increment.
* `system_health` — Optional but recommended. If omitted, the dashboard will show "no data" for system gauges.

## 1.5 Authentication

Uses the same `X-MC-Secret` shared secret pattern already in use by the ingest endpoint:

```
POST https://mbrowne.ca/api/mission-control/telemetry/ingest
Content-Type: application/json
X-MC-Secret: <value of MC_TELEMETRY_SECRET env var>
```

The `MC_TELEMETRY_SECRET` value must match between the Mac Mini env and the Vercel deployment env.

## 1.6 Idempotency Requirements

* Sessions upserted by `(openclaw_session_id, agent)` — repeated sends are safe
* Daily cost recalculated from token totals, not incremented — repeated sends are safe
* System health deduped by `recorded_at` (30-second window) — rapid sends don't create duplicate rows
* Repeated identical payload must not inflate totals

## 1.7 Implementation

* Language: Node.js or Python
* Runs as a background process on the Mac Mini
* Auto-restart on crash (launchd, pm2, or similar)
* Retry logic on network failure (exponential backoff, max 3 retries)

### Environment variables

| Variable | Purpose |
|---|---|
| `MC_TELEMETRY_SECRET` | Shared secret for `X-MC-Secret` header |
| `MC_INGEST_URL` | Full URL to the ingest endpoint (e.g., `https://mbrowne.ca/api/mission-control/telemetry/ingest`) |
| `POLLING_INTERVAL_BUSINESS` | Seconds between polls during business hours (default: 60) |
| `POLLING_INTERVAL_AFTER` | Seconds between polls after hours (default: 300) |
| `BUSINESS_HOURS_START` | Hour (24h) when business hours start (default: 8) |
| `BUSINESS_HOURS_END` | Hour (24h) when business hours end (default: 18) |
| `BUSINESS_HOURS_TZ` | Timezone for business hours (default: America/Toronto) |

## 1.8 Testing

* Duplicate payload ingestion does not inflate totals
* Partial payload failure (one agent fails, others succeed)
* Network failure retry logic (exponential backoff)
* Invalid schema rejection (server returns 400)
* Missing or wrong secret (server returns 401)

## 1.9 Quick test with curl

You can test the live endpoint right now without building the exporter:

```bash
curl -X POST https://mbrowne.ca/api/mission-control/telemetry/ingest \
  -H "Content-Type: application/json" \
  -H "X-MC-Secret: <your-secret>" \
  -d '{
    "timestamp": "2026-02-27T14:30:00Z",
    "agents": [{
      "name": "Rachel AI",
      "model": "gpt-codex-5.1",
      "last_heartbeat_at": "2026-02-27T14:29:55Z",
      "sessions": [{
        "openclaw_session_id": "test-001",
        "model": "gpt-codex-5.1",
        "started_at": "2026-02-27T09:00:00Z",
        "last_activity_at": "2026-02-27T14:29:00Z",
        "input_tokens": 5000,
        "output_tokens": 2000,
        "total_tokens": 7000,
        "compaction_count": 1,
        "last_error": null
      }]
    }],
    "system_health": {
      "cpu_percent": 30,
      "memory_percent": 55,
      "disk_percent": 60,
      "uptime_seconds": 86400
    }
  }'
```



---



# 2. Mission Control CLI Tool (`missionctl`)

> **Status:** IN PROGRESS — building now. All API routes are live and ready to consume (including Phase 2 task execution endpoints).
>
> **Pattern reference:** Follows the same CLI conventions as [`docreview`](https://github.com/mikebrowne/document-data-entry) — Python + Typer, structured JSON output, `doctor` command, environment variable fallbacks, meaningful exit codes.
>
> **Design decision:** The CLI is built for the Phase 2 task execution model from day one. `mc_jobs` and `mc_job_runs` are deprecated — no `job *` or `job-run *` commands are implemented. Tasks are the single executable unit.

## 2.1 Purpose

CLI tool allows agents and the dispatcher on the Mac Mini to interact with Mission Control without relying on chat connectors. All communication is outbound HTTPS to the Vercel-hosted API.

The CLI is task-execution-first: its primary purpose is to support the dispatcher's claim-execute-update loop. Secondary commands provide operational and planning CRUD for tasks, projects, commentary, and settings.

## 2.2 Global CLI Contract

* **Base URL env:** `MC_API_URL` (recommended: `https://www.mbrowne.ca/api/mission-control`)
* **Auth env/header:** `MC_TELEMETRY_SECRET` → sent as `X-MC-Secret` on every request
* **Output:** `--format text|json` (default `text`; dispatcher/agents should always use `json`)
* **Secret safety:** `X-MC-Secret` header must never appear in stdout/stderr on any code path — strip from error representations before printing

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success, including expected flow control (no eligible tasks, at concurrency limit) |
| 1 | API error (auth failure, validation rejection, server error) |
| 2 | Local error (missing env vars, missing arguments, invalid local validation) |

Exit code 0 covers all non-error outcomes. The dispatcher parses the JSON response body to distinguish between "task claimed," "no work available," and "at concurrency limit" — it does not branch on exit codes for those cases.

### Retry logic (Tier 1 commands only)

* Network failures: exponential backoff, max 3 retries
* 5xx responses: retry once after 2 seconds
* 4xx responses: no retry, surface the error immediately
* 409 (concurrency limit): no retry, exit 0, surface the response body

## 2.3 Commands — Tier 1 (Dispatcher Hot Path)

These commands are called every 60 seconds by the dispatcher. They require the most robust retry/error handling.

### `doctor`

Reports environment, dependency, and connectivity readiness.

```
$ missionctl doctor
missionctl_version=0.1.0
python_version=3.12.1 ok=True
pydantic=installed
typer=installed
httpx=installed
MC_API_URL=https://www.mbrowne.ca/api/mission-control
MC_TELEMETRY_SECRET=present
api_reachable=True
auth_ok=True
```

```
$ missionctl doctor --format json
{
  "missionctl_version": "0.1.0",
  "python_version": "3.12.1",
  "python_ok": true,
  "pydantic_installed": true,
  "typer_installed": true,
  "httpx_installed": true,
  "mc_api_url": "https://www.mbrowne.ca/api/mission-control",
  "mc_telemetry_secret_present": true,
  "api_reachable": true,
  "auth_ok": true
}
```

Checks performed:
* CLI version
* Python >= 3.11
* Required packages installed (pydantic, typer, httpx)
* `MC_API_URL` env var is set
* `MC_TELEMETRY_SECRET` env var is set
* API is reachable (GET `/api/mission-control/agents`)
* Auth is valid (secret accepted by the API)

Must fail with exit code 2 if `MC_API_URL` or `MC_TELEMETRY_SECRET` is missing.

### `agent concurrency`

```
missionctl agent concurrency --id <agent_id>
```

* **Endpoint:** `GET /agents/{id}/concurrency`
* **Response:**

```json
{ "ok": true, "data": { "max": 1, "running": 0 } }
```

### `task claim`

```
missionctl task claim --agent-id <id> [--queue <ops|dev|marketing|admin>] [--lease-seconds <int>]
```

* **Endpoint:** `POST /tasks/claim`
* **Request body:**

```json
{
  "agent_id": "uuid",
  "queue": "ops",
  "lease_duration_seconds": 600
}
```

* **Response — task claimed (200):**

```json
{
  "ok": true,
  "data": {
    "task": { "id": "...", "status": "in_progress", "attempt_count": 1, "..." },
    "task_run": { "id": "<run-uuid>", "task_id": "...", "agent_id": "...", "attempt": 1, "started_at": "...", "..." }
  }
}
```

The claim route atomically creates both the status transition and the `mc_task_runs` row. The `task_run.id` is returned so the dispatcher can pass it directly to `task-run update` after execution — no separate lookup needed.

* **Response — no eligible tasks (200):**

```json
{ "ok": true, "data": null }
```

* **Response — at concurrency limit (409):**

```json
{ "ok": false, "reason": "at_concurrency_limit", "data": null, "concurrency": { "max": 1, "running": 1 } }
```

All three outcomes exit 0. The dispatcher distinguishes them by parsing the JSON body.

**`--format text` output (when claimed):**

```
Claimed task <task_id> (attempt 1)
Run ID: <run_id>
Title: <task title>
Queue: ops
Priority: high
```

### `task update`

```
missionctl task update --id <task_id> --status <status> [status-specific flags]
```

* **Endpoint:** `PATCH /tasks/{id}`
* **Statuses:** `todo | queued | in_progress | in_review | blocked | failed | done | cancelled`

**Flags:**

| Flag | Required when | Notes |
|---|---|---|
| `--status` | Always | Target status |
| `--blocked-reason` | `status = blocked` | Enum: `needs_human_input`, `missing_access`, `external_dependency`, `ambiguous_requirements`, `tool_error`, `compliance_risk`, `rate_limited`, `infra_unavailable` |
| `--blocked-detail` | Recommended when blocked | Free-text explanation / questions for human |
| `--next-check-at` | Recommended when blocked | ISO 8601 datetime |
| `--error-message` | Recommended when failed | Error text |
| `--escalation-level` | Optional | Integer |
| `--output-ref` | Optional | Reference to output artifact |

**Local validation (exit 2, no HTTP call):**
* If `--status blocked` and `--blocked-reason` is missing → exit 2 with error message.

**Server validation (exit 1):**
* Invalid state transitions are rejected by the API with 400 and an error message.
* `blocked_reason` required when `status = blocked` (also enforced server-side).

### `task release`

```
missionctl task release --id <task_id> --agent-id <id> [--reason <text>]
```

* **Endpoint:** `POST /tasks/{id}/release`
* **Request body:**

```json
{ "agent_id": "uuid", "reason": "optional explanation" }
```

Sets task status back to `queued`, clears `claimed_by` and `lease_expires_at`, updates the associated task run with `outcome = failed`.

### `task expire-leases`

```
missionctl task expire-leases
```

* **Endpoint:** `POST /tasks/expire-leases`
* **Response:**

```json
{ "ok": true, "expired_count": 3, "data": [ "...expired task rows..." ] }
```

Finds all tasks where `status = 'in_progress' AND lease_expires_at < now()`, marks them as `failed`, clears lease fields, increments `escalation_level`, and updates associated task runs.

### `task-run update`

```
missionctl task-run update --id <run_id> [--outcome <success|blocked|failed>] [--completed-at <ISO-8601>] [--duration-ms <int>] [--error-message <text>] [--logs-url <url>] [--input-tokens <int>] [--output-tokens <int>] [--total-tokens <int>]
```

* **Endpoint:** `PATCH /task-runs/{id}`
* **Request body (typical completion):**

```json
{
  "outcome": "success",
  "completed_at": "2026-02-27T10:15:00Z",
  "duration_ms": 12345,
  "error_message": null,
  "logs_url": null,
  "token_usage": { "input_tokens": 5000, "output_tokens": 2000, "total_tokens": 7000 }
}
```

Token usage is passed as three separate flags (`--input-tokens`, `--output-tokens`, `--total-tokens`). The CLI assembles the `token_usage` JSON object internally. If none are provided, `token_usage` is sent as `null`.

`--completed-at` defaults to the current UTC timestamp if not provided.

### `task-run create` (edge case)

```
missionctl task-run create --task-id <uuid> --agent-id <uuid> --attempt <int> [--started-at <ISO-8601>]
```

* **Endpoint:** `POST /task-runs`
* **Request body:**

```json
{
  "task_id": "uuid",
  "agent_id": "uuid",
  "attempt": 1,
  "started_at": "2026-02-27T09:00:00Z"
}
```

`--started-at` defaults to the current UTC timestamp if not provided.

This command is only needed for edge cases outside the normal claim flow. `POST /tasks/claim` auto-creates the task run — this is the primary path.

### Dispatcher hot path

The normal dispatcher loop uses 4-5 CLI calls per cycle:

```
task expire-leases → agent concurrency → task claim → [execute work] → task update + task-run update --id <run_id>
```

The `run_id` comes back from the `task claim` response (`data.task_run.id`) and flows directly into the `task-run update` call. No discovery step is needed.

With `task release` as the escape hatch for releasing a claimed task back to the queue.

## 2.4 Commands — Tier 2 (Operational / Planning)

These commands are called by agents during task execution or by humans for operational work. They have simpler error handling (no retries on network failure).

### Tasks

```
missionctl task list [--project-id <uuid>] [--status <status>] [--priority <priority>] [--queue <queue>] [--task-type <type>] [--claimed-by <agent_id>]
missionctl task get --id <uuid>
missionctl task create --title <text> [--project-id <uuid>] [--description <text>] [--status <status>] [--priority <priority>] [--assigned-agent-id <uuid>] [--due-date <date>] [--queue <queue>] [--task-type <type>] [--auto-dispatch] [--max-attempts <int>]
missionctl task comments --id <uuid>
missionctl task comment --id <uuid> --author <text> --body <text>
missionctl task links --id <uuid>
missionctl task link --id <uuid> --label <text> --url <url>
```

* `task create`: `--title` is required. If `--auto-dispatch` is set, the server creates the task with `status = queued` regardless of the `--status` flag.
* `task list` filters: `--status`, `--priority`, `--queue`, `--task-type`, `--claimed-by` all map to query params.

### Task Runs

```
missionctl task-run list --task-id <uuid>
missionctl task-run get --id <uuid>
```

### Projects

```
missionctl project list [--status <active|paused|completed|archived>]
missionctl project get --id <uuid>
missionctl project create --name <text> [--description <text>]
missionctl project update --id <uuid> [--name <text>] [--description <text>] [--status <status>]
```

### Commentary

```
missionctl commentary list
missionctl commentary add --author <text> --body <text>
```

### Settings

```
missionctl settings get
```

### API endpoint mapping (all commands)

All endpoints are live and secured with `X-MC-Secret`:

| Command | Method | Endpoint |
|---|---|---|
| `doctor` | GET | `/agents` (connectivity check) |
| `agent concurrency` | GET | `/agents/{id}/concurrency` |
| `task claim` | POST | `/tasks/claim` |
| `task update` | PATCH | `/tasks/{id}` |
| `task release` | POST | `/tasks/{id}/release` |
| `task expire-leases` | POST | `/tasks/expire-leases` |
| `task-run create` | POST | `/task-runs` |
| `task-run update` | PATCH | `/task-runs/{id}` |
| `task-run list` | GET | `/task-runs?task_id=...` |
| `task-run get` | GET | `/task-runs/{id}` |
| `task list` | GET | `/tasks` |
| `task get` | GET | `/tasks/{id}` |
| `task create` | POST | `/tasks` |
| `task comments` | GET | `/tasks/{id}/comments` |
| `task comment` | POST | `/tasks/{id}/comments` |
| `task links` | GET | `/tasks/{id}/links` |
| `task link` | POST | `/tasks/{id}/links` |
| `project list` | GET | `/projects` |
| `project get` | GET | `/projects/{id}` |
| `project create` | POST | `/projects` |
| `project update` | PATCH | `/projects/{id}` |
| `commentary list` | GET | `/commentary` |
| `commentary add` | POST | `/commentary` |
| `settings get` | GET | `/settings` |

All endpoint paths are relative to `MC_API_URL` (e.g., `https://www.mbrowne.ca/api/mission-control`).

> **Note on domain redirect:** `mbrowne.ca` 307-redirects to `www.mbrowne.ca`. Use `https://www.mbrowne.ca/api/mission-control` as `MC_API_URL` to avoid redirect issues. POST bodies can be dropped during 307 redirects by some HTTP clients.

> **Note on Zod strict validation:** The API uses `.strict()` Zod schemas. Unknown fields in request bodies are rejected with 400. The CLI must only send recognized fields.

## 2.5 Implementation

* **Language:** Python (same as `docreview`)
* **CLI framework:** Typer (same as `docreview`)
* **HTTP client:** httpx (follows redirects by default, async-capable)
* **Validation:** Pydantic for response parsing
* **Build backend:** hatchling (same as `docreview`)
* **Package structure:** `src/` layout with command sub-modules

```
src/missionctl/
├── __init__.py
├── cli.py              # Typer app, registers sub-apps
├── client.py           # HTTP client (base URL, auth, retries, error handling)
├── models.py           # Pydantic models for API responses
├── formatting.py       # text vs json output formatting
├── commands/
│   ├── __init__.py
│   ├── doctor.py
│   ├── agent.py        # agent concurrency
│   ├── task.py         # claim, update, release, expire-leases, list, get, create, comment, link
│   ├── task_run.py     # create, update, list, get
│   ├── project.py      # list, get, create, update
│   ├── commentary.py   # list, add
│   └── settings.py     # get
```

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "missionctl"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.6.0",
  "typer>=0.12.0",
  "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "respx>=0.22.0",
]

[project.scripts]
missionctl = "missionctl.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/missionctl"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

## 2.6 Authentication

Uses the same `X-MC-Secret` header pattern as the Telemetry Exporter. The CLI sends `X-MC-Secret` with every request, and the API routes validate it against the `MC_TELEMETRY_SECRET` env var.

No new auth mechanism is needed — the same shared secret that already works for telemetry ingest works for CLI access. All CLI-facing API routes validate `X-MC-Secret` on every request.

### Environment variables (on the Mac Mini)

| Variable | Purpose | Fallback |
|---|---|---|
| `MC_API_URL` | Base URL of the Mission Control API | None — required |
| `MC_TELEMETRY_SECRET` | Shared secret for `X-MC-Secret` header | None — required |

Recommended `MC_API_URL` value: `https://www.mbrowne.ca/api/mission-control`

## 2.7 Testing

* `doctor` reports all checks correctly (present/missing env vars, reachable/unreachable API, CLI version)
* Each command returns valid JSON in `--format json` mode
* Auth failure (wrong secret) returns exit code 1 with clear error
* Missing required args return exit code 2
* `task update --status blocked` without `--blocked-reason` returns exit code 2 without making HTTP call
* `task claim` returns exit 0 for all three outcomes (claimed, no work, at capacity)
* Network failure triggers retry logic (Tier 1 commands)
* No secrets appear in stdout/stderr on any code path
* HTTP client mocking via `respx` for unit tests

## 2.8 Agent Integration

Agents call the CLI instead of writing directly to Supabase. This creates a clean abstraction layer and ensures all writes go through validated API routes.

## 2.9 MVP Build Order

Build Tier 1 first (the dispatcher hot path), then add Tier 2 convenience commands:

| # | Command | Tier | Notes |
|---|---|---|---|
| 1 | `doctor` | 1 | First working vertical slice — validates env, deps, connectivity |
| 2 | `agent concurrency` | 1 | |
| 3 | `task claim` | 1 | Parse `data.task` + `data.task_run` from response |
| 4 | `task update` | 1 | Local validation for blocked status |
| 5 | `task release` | 1 | |
| 6 | `task-run update` | 1 | Three separate token flags → assembled object |
| 7 | `task expire-leases` | 1 | |
| 8 | `task-run create` | 1 | Edge case only |
| 9 | `task list / get / create` | 2 | |
| 10 | `task comment / comments / link / links` | 2 | |
| 11 | `task-run list / get` | 2 | |
| 12 | `project list / get / create / update` | 2 | |
| 13 | `commentary list / add` | 2 | |
| 14 | `settings get` | 2 | |



---



# 3. Agent Integration and Task Execution

> **Status:** Design complete. Implementation depends on CLI Tool (Section 2) and Phase 2 dashboard/backend deployment.
>
> **Note:** The Phase 2 PRDs (Sections 5–6 of this document) define the full task execution engine. This section provides the high-level agent model. The job lifecycle below is **legacy** — Phase 2 replaces `mc_jobs` / `mc_job_runs` with `mc_tasks` / `mc_task_runs` as the primary execution unit.

## 3.1 Philosophy

* Agents are **persistent identities** (rows in `mc_agents`)
* Tasks are the **primary executable unit** (rows in `mc_tasks` + `mc_task_runs`)
* Sessions are **short-lived contexts** (rows in `mc_sessions`)

Never use long-lived sessions for operational work.

## 3.2 Task Lifecycle (Phase 2)

```
todo → queued                               (human promotes or auto_dispatch)
queued → in_progress                        (dispatcher claims via RPC)
in_progress → done | in_review | blocked | failed | cancelled
in_review → done | queued | cancelled
blocked → queued | cancelled
failed → queued | cancelled
```

Retry creates a new `mc_task_runs` entry with incremented `attempt`. See the Phase 2 PRD (Section 5) for full state transition rules.

## 3.2.1 Legacy Job Lifecycle (deprecated)

The original V1 job lifecycle is preserved for reference. `mc_jobs` and `mc_job_runs` remain in the database but are no longer actively used for new automation.

```
queued → running → completed
queued → running → failed
any state → cancelled
```

## 3.3 Agent Rules

When an agent receives a task:

1. Create a new OpenClaw session
2. Perform the task
3. Write the result to Mission Control via `missionctl` CLI (`task update` + `task-run update`)
4. End the session

Never keep operational context in memory between tasks.

## 3.4 Current agents

| Name | Role | Default Model | Max Concurrency |
|---|---|---|---|
| Rachel AI | Lead Operations Agent | gpt-codex-5.1 | 1 |
| Vanessa AI | Research and Content Agent | gpt-codex-5.1 | 1 |



---



# 4. Build Priority

| # | Service | Depends On | Status |
|---|---|---|---|
| 1 | Telemetry Exporter | Nothing — API endpoint is live | Ready to build |
| 2 | CLI Tool (`missionctl`) | API routes (already live, all secured with `X-MC-Secret`) | **In progress** |
| 3 | Agent Integration / Dispatcher | CLI Tool + Phase 2 dashboard deployment | Future phase |

### What to build now

**Telemetry Exporter** is needed to start getting real data into the dashboard. **CLI Tool** (`missionctl`) is actively being built — see Section 2 for the locked command contract.

### What you need before building

| Item | Value | Status |
|---|---|---|
| `MC_TELEMETRY_SECRET` | Already set in `.env.local` and Vercel | Done |
| Production domain | `mbrowne.ca` | Done |
| `MC_INGEST_URL` | `https://mbrowne.ca/api/mission-control/telemetry/ingest` | Done |

### Future items (not needed now)

These are separate projects that will get their own PRDs when the time comes:

* **Email Control Plane** — email-based job dispatch (separate service, separate PRD)
* **Mac Mini ops setup** — disabling sleep, process management, log rotation (local ops checklist, not a software PRD)

---

# PRD — Mission Control Phase 2: Task Execution Engine (Dashboard & Backend)

> **Status:** NOT STARTED
>
> **Prerequisite:** Mission Control V1 is deployed. See [open-claw-mission-control.prd.md](./open-claw-mission-control.prd.md) for the V1 dashboard PRD.
>
> **Companion PRD:** See [open-claw-phase-2-agent.prd.md](./open-claw-phase-2-agent.prd.md) for the Dispatcher and Agent Workflow spec (Mac Mini side).
>
> **Scope:** This document covers the **website dashboard and backend** — schema migration, API routes, Supabase RPC functions, TypeScript types, services, and UI. It does NOT cover the dispatcher, OpenClaw, or agent execution logic.



## 1. Purpose

Phase 2 evolves Mission Control from an observability dashboard into a **deterministic task execution engine**.

V1 answered: "What are the agents doing?"
Phase 2 answers: "What should the agents do, and did they do it correctly?"

After Phase 2, Mission Control:

* Is the single source of truth for all projects and tasks
* Supports lease-based task claiming with atomic concurrency enforcement
* Provides full audit trail via task runs
* Surfaces blocked, failed, and escalated tasks to humans
* Replaces Notion as the operational backbone
* Requires no LLM for scheduling or orchestration logic



## 2. Key Decisions (Agreed)

These decisions were locked in during Phase 2 planning and must not be revisited during implementation:

1. **Tasks subsume Jobs.** `mc_jobs` and `mc_job_runs` are deprecated. Tasks are the single execution unit. A new `mc_task_runs` table replaces `mc_job_runs`.
2. **Status enum extended, not renamed.** V1 values are kept. New values added: `queued`, `blocked`, `failed`.
3. **Priority unchanged.** Keep `low | normal | high | urgent`. No P0–P3.
4. **`todo` is NOT dispatchable.** `todo` = planned/backlog. `queued` = ready for dispatcher. This separation is critical.
5. **Lease-based execution via Supabase RPC.** Atomic claiming with `FOR UPDATE SKIP LOCKED`.
6. **Lease expiry handled by dispatcher**, not pg_cron.
7. **Concurrency stored per-agent** in `mc_agents.max_concurrency`.
8. **Auth: Supabase Auth** for dashboard, **`X-MC-Secret`** for all API routes called by the dispatcher/CLI.
9. **Skill.md is NOT part of Mission Control.** MC only knows tasks, agents, and outcomes.



## 3. Architecture (Phase 2 Additions)

Phase 2 adds to the existing V1 architecture:

```
┌─────────────────────────────────────────┐
│              Mac Mini                    │
│                                         │
│  ┌───────────┐  ┌────────────────────┐  │
│  │  OpenClaw  │  │ Telemetry Exporter │  │
│  └───────────┘  └────────┬───────────┘  │
│                          │              │
│  ┌───────────┐           │              │
│  │ Dispatcher │───────────┤              │
│  └───────────┘           │              │
│       │                  │              │
│  ┌────┴──────┐           │              │
│  │ missionctl│───────────┤              │
│  └───────────┘           │              │
│                          │              │
│   All traffic is         │              │
│   OUTBOUND HTTPS ────────┤              │
└──────────────────────────┼──────────────┘
                           │
                           ▼
┌──────────────────────────────────────────┐
│        Website (Vercel / Next.js)        │
│  ┌────────────────────────────────────┐  │
│  │  API Routes:                       │  │
│  │    POST /tasks/claim  ← NEW        │  │
│  │    POST /tasks/[id]/release ← NEW  │  │
│  │    POST /tasks/expire-leases ← NEW │  │
│  │    POST /task-runs ← NEW           │  │
│  │    PATCH /task-runs/[id] ← NEW     │  │
│  │    (all existing V1 routes remain) │  │
│  └──────────────┬─────────────────────┘  │
│                 │                         │
│  ┌──────────────▼─────────────────────┐  │
│  │  Supabase RPC:                     │  │
│  │    claim_task() ← NEW              │  │
│  └──────────────┬─────────────────────┘  │
│                 │                         │
│  ┌──────────────▼─────────────────────┐  │
│  │     Mission Control Dashboard      │  │
│  │  /admin/mission-control/*          │  │
│  │    + Blocked Inbox ← NEW           │  │
│  │    + Failed Inbox ← NEW            │  │
│  │    + Concurrency Panel ← NEW       │  │
│  │    + Task Board (8 statuses) ← NEW │  │
│  └────────────────────────────────────┘  │
└──────────────────────┬───────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────┐
│           Supabase (ca-central-1)        │
│                                          │
│  Modified tables:                        │
│    mc_tasks (12 new columns)             │
│    mc_agents (+max_concurrency)          │
│                                          │
│  New tables:                             │
│    mc_task_runs                          │
│                                          │
│  New functions:                          │
│    claim_task()                          │
│                                          │
│  Deprecated (kept, not dropped):         │
│    mc_jobs, mc_job_runs                  │
└──────────────────────────────────────────┘
```



---



## 4. Data Model Changes

### 4.1 `mc_tasks` — Extended Columns

These columns are **added** to the existing `mc_tasks` table. All existing columns remain unchanged.

| Column | Type | Default | Nullable | Notes |
|---|---|---|---|---|
| `queue` | text | null | yes | `ops`, `dev`, `marketing`, `admin` |
| `task_type` | text | null | yes | `operational`, `content`, `ingestion`, `maintenance`, `review`, `dev` |
| `auto_dispatch` | boolean | false | no | If true, task is created with status `queued` instead of `todo` |
| `claimed_by` | uuid (FK → mc_agents) | null | yes | Agent that holds the lease |
| `lease_expires_at` | timestamptz | null | yes | When the current lease expires |
| `attempt_count` | integer | 0 | no | Incremented each time a task is claimed |
| `max_attempts` | integer | 3 | no | Auto-fail threshold |
| `blocked_reason` | text | null | yes | Structured reason (see enum below) |
| `blocked_detail` | text | null | yes | Free-text explanation, questions for human |
| `next_check_at` | timestamptz | null | yes | When to re-evaluate a blocked task |
| `escalation_level` | integer | 0 | no | Incremented on repeated failures/blocks |

### 4.2 `mc_tasks` — Updated Status Enum

V1 statuses (5): `todo | in_progress | in_review | done | cancelled`

Phase 2 statuses (8): `todo | queued | in_progress | in_review | blocked | failed | done | cancelled`

| Status | Layer | Meaning |
|---|---|---|
| `todo` | Planning | Exists but not ready for execution. Human backlog. |
| `queued` | Execution | Ready for dispatcher to claim. |
| `in_progress` | Runtime | Claimed by an agent, lease active. |
| `in_review` | Runtime | Agent finished, waiting for human approval. |
| `blocked` | Runtime | Agent cannot proceed. Requires human input or external resolution. |
| `failed` | Runtime | Attempted and failed. May auto-retry if under `max_attempts`. |
| `done` | Completion | Successfully completed. |
| `cancelled` | Completion | Abandoned intentionally by a human. |

### 4.3 Valid State Transitions

```
todo → queued                               (human promotes or auto_dispatch)
queued → in_progress                        (dispatcher claims via RPC)
queued → cancelled                          (human cancels)
in_progress → done                          (agent completes)
in_progress → in_review                     (agent finishes, needs human approval)
in_progress → blocked                       (agent cannot proceed)
in_progress → failed                        (agent fails or lease expires)
in_progress → cancelled                     (human cancels mid-execution)
in_review → done                            (human approves)
in_review → queued                          (human requests rework)
in_review → cancelled                       (human cancels)
blocked → queued                            (blocker resolved, re-queue)
blocked → cancelled                         (human cancels)
failed → queued                             (retry, if attempt_count < max_attempts)
failed → cancelled                          (human gives up)
```

### 4.4 Blocked Reason Enum

| Value | Meaning |
|---|---|
| `needs_human_input` | Agent needs a decision or clarification from a human |
| `missing_access` | Agent lacks credentials or permissions for a resource |
| `external_dependency` | Waiting on a third-party service or response |
| `ambiguous_requirements` | Task description is unclear, agent cannot proceed safely |
| `tool_error` | A tool or skill failed unexpectedly |
| `compliance_risk` | Agent detected a compliance concern and stopped |
| `rate_limited` | Model or API rate limit hit |
| `infra_unavailable` | Infrastructure (Mac Mini, network, etc.) is down |

When `status = blocked`, `blocked_reason` and `blocked_detail` are **required**. `next_check_at` is **recommended**.

### 4.5 `mc_agents` — New Column

| Column | Type | Default | Notes |
|---|---|---|---|
| `max_concurrency` | integer | 1 | Max tasks this agent can run simultaneously |

### 4.6 New Table: `mc_task_runs`

Tracks each execution attempt for a task. Replaces the concept of `mc_job_runs`.

| Column | Type | Default | Nullable | Notes |
|---|---|---|---|---|
| `id` | uuid PK | gen_random_uuid() | no | |
| `task_id` | uuid FK → mc_tasks | — | no | CASCADE on delete |
| `agent_id` | uuid FK → mc_agents | — | no | SET NULL on delete |
| `attempt` | integer | — | no | Matches `task.attempt_count` at time of claim |
| `started_at` | timestamptz | — | no | When claim occurred |
| `completed_at` | timestamptz | null | yes | When execution finished |
| `duration_ms` | integer | null | yes | Computed: `completed_at - started_at` |
| `outcome` | text | — | no | `success`, `blocked`, `failed` |
| `error_message` | text | null | yes | |
| `logs_url` | text | null | yes | Link to execution logs |
| `token_usage` | jsonb | null | yes | `{ input_tokens, output_tokens, total_tokens }` |
| `created_at` | timestamptz | now() | no | |

Indexes: `task_id`, `agent_id`, `outcome`

Unique constraint: `(task_id, attempt)`

### 4.7 New Indexes on `mc_tasks`

| Index | Column(s) | Notes |
|---|---|---|
| `idx_mc_tasks_queue` | `queue` | Filter by queue |
| `idx_mc_tasks_lease_expires` | `lease_expires_at` | Find expired leases |
| `idx_mc_tasks_claimed_by` | `claimed_by` | Count running tasks per agent |
| `idx_mc_tasks_task_type` | `task_type` | Filter by type |

### 4.8 Deprecated Tables

`mc_jobs` and `mc_job_runs` remain in the database but are no longer actively used. The dashboard will stop displaying them. Existing API routes for jobs remain functional but are considered deprecated. A future cleanup migration can drop them.



---



## 5. Supabase RPC: `claim_task`

The most critical new function. Must be **atomic** to prevent double-claiming.

### Specification

```sql
CREATE OR REPLACE FUNCTION claim_task(
    p_agent_id uuid,
    p_queue text DEFAULT NULL,
    p_lease_duration interval DEFAULT interval '10 minutes'
)
RETURNS SETOF mc_tasks
LANGUAGE sql
AS $$
    UPDATE mc_tasks
    SET
        status = 'in_progress',
        claimed_by = p_agent_id,
        lease_expires_at = now() + p_lease_duration,
        attempt_count = attempt_count + 1
    WHERE id = (
        SELECT id
        FROM mc_tasks
        WHERE status = 'queued'
          AND (assigned_agent_id IS NULL OR assigned_agent_id = p_agent_id)
          AND (p_queue IS NULL OR queue = p_queue)
        ORDER BY
            CASE priority
                WHEN 'urgent' THEN 0
                WHEN 'high' THEN 1
                WHEN 'normal' THEN 2
                WHEN 'low' THEN 3
            END,
            created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *;
$$;
```

### Behavior

* Returns the claimed task row, or empty set if no eligible task exists.
* `FOR UPDATE SKIP LOCKED` prevents two concurrent claims from selecting the same task.
* Priority ordering: urgent > high > normal > low, then FIFO within same priority.
* If `p_queue` is provided, only tasks in that queue are considered.
* If `assigned_agent_id` is set on a task, only that agent can claim it.

### Concurrency Guard

The API route that calls this RPC must **first** check the agent's current running count against `mc_agents.max_concurrency`. The RPC itself does not enforce concurrency — that's the caller's responsibility (the claim API route).



---



## 6. API Routes (Phase 2 Additions)

All new routes use `X-MC-Secret` authentication via the shared `validateMcSecret()` helper.

### 6.1 Claim Task

```
POST /api/mission-control/tasks/claim
```

Body:
```json
{
    "agent_id": "uuid",
    "queue": "ops",
    "lease_duration_seconds": 600
}
```

Logic:
1. Validate `X-MC-Secret`
2. Check `agent.max_concurrency` vs. current running count (`SELECT count(*) FROM mc_tasks WHERE claimed_by = agent_id AND status = 'in_progress'`)
3. If at capacity, return `{ ok: false, reason: "at_concurrency_limit" }`
4. Call `claim_task` RPC
5. If a task was claimed, create an `mc_task_runs` row with `started_at = now()` and `outcome = 'running'`... wait, the outcome enum is success/blocked/failed, not running. Let me reconsider — the task run is created at claim time with `started_at`, and `outcome` + `completed_at` are filled in when the task finishes. So at creation time, `outcome` should be null or we need a running state.

Actually, let me revise: `outcome` should be nullable, set to null at creation, and filled in at completion. Or we add `running` to the outcome enum. The cleaner approach is to leave `outcome` null until completion.

Response (success):
```json
{
    "ok": true,
    "data": { /* task row */ }
}
```

Response (no work):
```json
{
    "ok": true,
    "data": null
}
```

### 6.2 Release Task

```
POST /api/mission-control/tasks/{id}/release
```

Body:
```json
{
    "agent_id": "uuid",
    "reason": "optional explanation"
}
```

Logic:
1. Validate `X-MC-Secret`
2. Verify `claimed_by = agent_id`
3. Set `status = queued`, clear `claimed_by` and `lease_expires_at`
4. Update the associated `mc_task_runs` row with `outcome = failed`, `error_message = reason`

### 6.3 Expire Stale Leases

```
POST /api/mission-control/tasks/expire-leases
```

Body: (none required)

Logic:
1. Validate `X-MC-Secret`
2. Find all tasks where `status = 'in_progress' AND lease_expires_at < now()`
3. For each: set `status = 'failed'`, clear `claimed_by` and `lease_expires_at`, increment `escalation_level`
4. If `attempt_count >= max_attempts`, keep as `failed`. Otherwise dispatcher may re-queue.
5. Update associated task runs with `outcome = failed`, `error_message = 'Lease expired'`
6. Return count of expired tasks

Response:
```json
{
    "ok": true,
    "expired_count": 3,
    "data": [ /* expired task rows */ ]
}
```

### 6.4 Check Agent Concurrency

```
GET /api/mission-control/agents/{id}/concurrency
```

Logic:
1. Validate `X-MC-Secret`
2. Return `{ max: agent.max_concurrency, running: count(tasks where claimed_by = id AND status = in_progress) }`

### 6.5 Task Runs CRUD

```
POST /api/mission-control/task-runs                 — create run
GET  /api/mission-control/task-runs?task_id=...     — list runs for a task
GET  /api/mission-control/task-runs/{id}            — get single run
PATCH /api/mission-control/task-runs/{id}           — update outcome/duration/error
```

### 6.6 Existing Routes — Updates

| Route | Change |
|---|---|
| `PATCH /api/mission-control/tasks/[id]` | Accept new fields: `blocked_reason`, `blocked_detail`, `next_check_at`, `escalation_level`. Validate that `blocked_reason` is required when setting `status = blocked`. |
| `POST /api/mission-control/tasks` | Accept new fields: `queue`, `task_type`, `auto_dispatch`, `max_attempts`. If `auto_dispatch = true`, set status to `queued` instead of `todo`. |
| `GET /api/mission-control/tasks` | Accept new query params: `queue`, `task_type`, `claimed_by`. |



---



## 7. TypeScript Changes

### 7.1 Updated Types

```typescript
export type McTaskStatus =
    | "todo" | "queued" | "in_progress" | "in_review"
    | "blocked" | "failed" | "done" | "cancelled";

export type McTaskQueue = "ops" | "dev" | "marketing" | "admin";

export type McTaskType =
    | "operational" | "content" | "ingestion"
    | "maintenance" | "review" | "dev";

export type McBlockedReason =
    | "needs_human_input" | "missing_access" | "external_dependency"
    | "ambiguous_requirements" | "tool_error" | "compliance_risk"
    | "rate_limited" | "infra_unavailable";

export type McTaskRunOutcome = "success" | "blocked" | "failed";
```

### 7.2 Updated `McTask` Interface

Add to existing interface:
```typescript
queue: McTaskQueue | null;
task_type: McTaskType | null;
auto_dispatch: boolean;
claimed_by: string | null;
lease_expires_at: string | null;
attempt_count: number;
max_attempts: number;
blocked_reason: McBlockedReason | null;
blocked_detail: string | null;
next_check_at: string | null;
escalation_level: number;
```

### 7.3 Updated `McAgent` Interface

Add:
```typescript
max_concurrency: number;
```

### 7.4 New `McTaskRun` Interface

```typescript
export interface McTaskRun {
    id: string;
    task_id: string;
    agent_id: string;
    attempt: number;
    started_at: string;
    completed_at: string | null;
    duration_ms: number | null;
    outcome: McTaskRunOutcome | null;
    error_message: string | null;
    logs_url: string | null;
    token_usage: { input_tokens: number; output_tokens: number; total_tokens: number } | null;
    created_at: string;
}
```

### 7.5 Updated Task State Transitions

```typescript
export const MC_TASK_VALID_TRANSITIONS: Record<McTaskStatus, McTaskStatus[]> = {
    todo: ["queued", "cancelled"],
    queued: ["in_progress", "cancelled"],
    in_progress: ["done", "in_review", "blocked", "failed", "cancelled"],
    in_review: ["done", "queued", "cancelled"],
    blocked: ["queued", "cancelled"],
    failed: ["queued", "cancelled"],
    done: [],
    cancelled: [],
};
```

### 7.6 Zod Schema Updates

New schemas needed:
* `claimTaskSchema` — `{ agent_id: uuid, queue?: string, lease_duration_seconds?: number }`
* `releaseTaskSchema` — `{ agent_id: uuid, reason?: string }`
* `createTaskRunSchema` — task run creation fields
* `updateTaskRunSchema` — outcome, completed_at, duration_ms, error_message, logs_url, token_usage

Updated schemas:
* `createTaskSchema` — add `queue`, `task_type`, `auto_dispatch`, `max_attempts`
* `updateTaskSchema` — add `blocked_reason`, `blocked_detail`, `next_check_at`, `escalation_level`, `queue`, `task_type`



---



## 8. Dashboard UI Changes

### 8.1 Task Board (Updated)

The existing task list/table view must handle 8 statuses. Options:

* **Kanban board** — columns for each status (or grouped: Planning | Execution | Completed)
* **Filtered table** — dropdown filter for status, with status badge colors

Each task card/row should show: title, priority badge, queue badge, assigned agent, attempt count, and lease timer (if `in_progress`).

### 8.2 Blocked Inbox (New Page)

Route: `/admin/mission-control/blocked`

Shows all tasks with `status = blocked`, sorted by `escalation_level` desc, then `created_at` asc.

Each item shows:
* Task title and project
* `blocked_reason` (human-readable label)
* `blocked_detail` (full text)
* `next_check_at` (countdown or "overdue" badge)
* `escalation_level`
* Action buttons: Unblock (→ `queued`), Cancel, Edit detail

### 8.3 Failed Inbox (New Page)

Route: `/admin/mission-control/failed`

Shows all tasks with `status = failed`, sorted by `updated_at` desc.

Each item shows:
* Task title and project
* `error_message` from latest task run
* `attempt_count` / `max_attempts`
* Action buttons: Retry (→ `queued`), Cancel, View runs

### 8.4 Concurrency Panel (New Component)

Displayed on the main Mission Control dashboard page.

Per agent:
* Agent name and status
* Running: X / max_concurrency
* Current task title (if running)
* Lease time remaining

System total:
* Total running across all agents
* Total queued count

### 8.5 Task Detail Page (Updated)

Add sections for:
* **Lease info** — `claimed_by`, `lease_expires_at` (with countdown), `attempt_count`
* **Blocked info** — `blocked_reason`, `blocked_detail`, `next_check_at` (shown when status = blocked)
* **Task runs** — table of all execution attempts with outcome, duration, error
* **Queue & type** — displayed as badges



---



## 9. Migration Plan

### 9.1 SQL Migration (003_phase2_task_execution.sql)

The migration must:

1. Add new columns to `mc_tasks` (all nullable or with defaults, so existing rows are unaffected)
2. Extend the status check constraint to include `queued`, `blocked`, `failed`
3. Add `max_concurrency` to `mc_agents`
4. Create `mc_task_runs` table
5. Create `claim_task` RPC function
6. Add new indexes
7. Update RLS policies for new table

### 9.2 Existing Data

* Existing tasks keep their current status. No data migration needed.
* New columns default to null/0/false, so existing rows remain valid.
* `mc_jobs` and `mc_job_runs` are untouched.

### 9.3 Mock Data Updates

* Update mock tasks to include some with `queued`, `blocked`, and `failed` statuses
* Add mock task runs
* Update `McTask` mock objects to include new fields
* Add `max_concurrency` to mock agents



---



## 10. Observability

Phase 2 adds tracking for:

| Metric | Source |
|---|---|
| Task durations | `mc_task_runs.duration_ms` |
| Retry counts | `mc_tasks.attempt_count` |
| Failure rates | `mc_task_runs` where `outcome = failed` |
| Agent load | Count of `in_progress` tasks per agent |
| Lease violations | Tasks that went through expire-leases |
| Blocked reasons distribution | `mc_tasks.blocked_reason` aggregation |
| Queue depth | Count of `queued` tasks per queue |
| Escalation count | Tasks with `escalation_level > 0` |



---



## 11. TDD Requirements

All critical flows require tests before the feature is considered complete:

| Flow | Test Type |
|---|---|
| Claim task (happy path) | Unit + integration |
| Claim task at concurrency limit | Unit |
| Claim task with queue filter | Unit |
| Claim task — no eligible tasks | Unit |
| Lease expiry | Unit + integration |
| Blocked → queued transition | Unit |
| Failed → queued retry (under max_attempts) | Unit |
| Failed → stays failed (at max_attempts) | Unit |
| Status transition validation | Unit |
| auto_dispatch flag | Unit |
| Concurrency check endpoint | Unit |
| Task run creation and completion | Unit |

Testing infrastructure: Jest 30 + React Testing Library (same as V1).



---



## 12. Acceptance Criteria

Phase 2 is production-ready when:

* [ ] An agent cannot claim a task while at concurrency limit
* [ ] Two agents cannot claim the same task (atomic locking verified)
* [ ] Expired leases return tasks to failed/queued correctly
* [ ] Blocked tasks surface in the Blocked Inbox with reason and detail
* [ ] Failed tasks surface in the Failed Inbox with error and attempt count
* [ ] Task runs provide a complete audit trail per task
* [ ] `todo` tasks are never claimed by the dispatcher
* [ ] `auto_dispatch = true` creates tasks directly as `queued`
* [ ] All state transitions are validated (invalid transitions rejected)
* [ ] Concurrency panel shows accurate real-time counts
* [ ] No LLM is involved in scheduling or orchestration logic
* [ ] All TDD flows have passing tests



---



## 13. Build Sequence

| # | Step | Depends On |
|---|---|---|
| 1 | Write SQL migration (schema + RPC + indexes + RLS) | Nothing |
| 2 | Update TypeScript types and Zod schemas | Nothing |
| 3 | Update mock data (tasks, agents, new task runs) | Step 2 |
| 4 | Update task service (new fields, state transitions) | Steps 2–3 |
| 5 | Create task run service | Steps 2–3 |
| 6 | Create claim/release/expire-leases API routes | Steps 4–5 |
| 7 | Create concurrency check API route | Step 4 |
| 8 | Create task-runs API routes | Step 5 |
| 9 | Update existing task API routes (new fields, auto_dispatch) | Step 4 |
| 10 | Write tests for all execution flows | Steps 4–9 |
| 11 | Build Blocked Inbox UI | Step 9 |
| 12 | Build Failed Inbox UI | Step 9 |
| 13 | Build Concurrency Panel component | Step 7 |
| 14 | Update Task Board / Task Detail views | Step 9 |
| 15 | Update main dashboard page with new panels | Steps 11–14 |
| 16 | Run SQL migration in Supabase | Step 1 (manual) |

---

# PRD — Mission Control Phase 2: Agent Workflow & Dispatcher

> **Status:** NOT STARTED
>
> **Prerequisite:** Mission Control Phase 2 dashboard/backend must be deployed first. See [open-claw-phase-2.prd.md](./open-claw-phase-2.prd.md) for the schema, API routes, and RPC specs.
>
> **Scope:** This document covers the **Mac Mini side** — the dispatcher process, agent execution model, session discipline, retry logic, and stuck escalation. It does NOT cover the dashboard UI, schema design, or API route implementation.
>
> **Not in scope for Mission Control:** Skill.md definitions, OpenClaw internals, and agent reasoning logic. Mission Control only knows tasks, agents, and outcomes.



## 1. Purpose

Define how Rachel and Vanessa operate as deterministic workers within Mission Control.

Agents must:

* Pull work from Mission Control, never from memory or chat
* Execute in short-lived sessions (one task = one session)
* Update status correctly via `missionctl` CLI or API
* Handle blocked situations explicitly with structured reasons
* Never rely on chat memory, context carryover, or LLM for scheduling



## 2. Agent Roles

### Rachel AI — Lead Operations Agent

* Pulls queues: `ops`, `dev`, `admin`
* Can create subtasks
* Default model: `gpt-codex-5.1`
* `max_concurrency`: 1

### Vanessa AI — Research and Content Agent

* Pulls queue: `marketing`
* Outputs go to `in_review` (human approval required)
* Default model: `gpt-codex-5.1`
* `max_concurrency`: 1

### System Limits

* Max parallel tasks across all agents: 2
* No agent may exceed its `max_concurrency` value (stored in `mc_agents`)



## 3. Dispatcher

The dispatcher is the most important runtime component. It runs locally on the Mac Mini as a background process.

### 3.1 Responsibilities

* Enforce concurrency limits
* Claim work from Mission Control
* Spawn OpenClaw sessions for claimed tasks
* Write results back to Mission Control
* Handle retries and lease expiry
* Detect stuck tasks

### 3.2 Main Loop (every 60 seconds)

```
1. Call POST /tasks/expire-leases
   → Clears any expired leases from previous cycles

2. For each agent:
   a. Call GET /agents/{id}/concurrency
   b. If running < max_concurrency:
      - Call POST /tasks/claim with agent_id and agent's queue(s)
      - If a task was claimed:
        → Spawn OpenClaw session with task payload
        → On completion: update task status + task run
        → On failure: update task status + task run + error
        → On blocked: update task status with reason + detail
```

### 3.3 Lease Management

* Default lease duration: 10 minutes (configurable per claim)
* Dispatcher calls `expire-leases` at the start of every cycle
* If a task's lease expires before the agent finishes, the task goes to `failed`
* Long-running tasks should periodically renew their lease (future enhancement)

### 3.4 Implementation

* Language: Python (same as `missionctl` CLI and `docreview`)
* Runs as a background process (launchd, pm2, or similar)
* Auto-restart on crash
* All API calls go through the `missionctl` CLI client library or direct HTTP
* Uses `X-MC-Secret` for authentication

### 3.5 Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `MC_API_URL` | Base URL for Mission Control API | `https://www.mbrowne.ca/api/mission-control` |
| `MC_TELEMETRY_SECRET` | Shared secret for `X-MC-Secret` | Required |
| `DISPATCH_INTERVAL` | Seconds between dispatch cycles | 60 |
| `DEFAULT_LEASE_SECONDS` | Default lease duration | 600 |



## 4. Task Execution Flow

When the dispatcher claims a task for an agent:

```
1. Receive task payload from claim response
2. Create a new OpenClaw session (short-lived, atomic)
3. Agent reads task title, description, queue, and any linked context
4. Agent executes work using its skills
5. Agent writes results back:

   If SUCCESS:
     → PATCH /tasks/{id} with status = "done" (or "in_review" for Vanessa)
     → PATCH /task-runs/{id} with outcome = "success", duration_ms, token_usage
     → POST /tasks/{id}/comments with output summary
     → POST /tasks/{id}/links with any artifact URLs

   If BLOCKED:
     → PATCH /tasks/{id} with:
         status = "blocked"
         blocked_reason = "<structured reason>"
         blocked_detail = "<specific questions or explanation>"
         next_check_at = "<when to re-check>"
     → PATCH /task-runs/{id} with outcome = "blocked"

   If FAILED:
     → PATCH /tasks/{id} with status = "failed", error_message
     → PATCH /task-runs/{id} with outcome = "failed", error_message, duration_ms

6. End the OpenClaw session
7. Never carry context forward to the next task
```



## 5. Session Discipline

Agents must:

* Treat each task as an atomic unit of work
* Start a fresh OpenClaw session for each task
* Not accumulate context between tasks
* Not keep long-running chat sessions open
* Only call the LLM when the task requires reasoning

Scheduling logic (dispatcher loop, concurrency checks, lease management) must **never** use an LLM. These are deterministic operations.



## 6. Retry Policy

### Automatic Retry

If a task fails and `attempt_count < max_attempts`:
* Dispatcher may re-queue the task (set status → `queued`)
* Next dispatch cycle will claim it again
* A new `mc_task_runs` row is created for the retry

If `attempt_count >= max_attempts`:
* Task stays as `failed`
* `escalation_level` is incremented
* Human must intervene (visible in Failed Inbox on dashboard)

### Blocked Tasks

Blocked tasks are NOT auto-retried.

* They wait until `next_check_at`
* They require a condition change (human unblocks, external dependency resolves)
* The dispatcher's stuck detection loop may escalate them if they remain blocked past threshold



## 7. Stuck Escalation

### Detection Rules

The stuck detection loop runs hourly (or as configured):

| Condition | Action |
|---|---|
| `in_progress` past `lease_expires_at` | Mark failed, increment escalation |
| `blocked` past `next_check_at` | Increment `escalation_level` |
| `attempt_count >= max_attempts` | Increment `escalation_level` |
| `escalation_level >= 2` | Surface prominently in dashboard |

### Escalation Behavior

* Increment `escalation_level` on the task
* Post a commentary entry summarizing the stuck task
* Dashboard shows escalated tasks prominently in Blocked/Failed inboxes

### Optional (Future)

* LLM-generated summary of stuck task clusters (non-critical, cosmetic)
* Email/Slack notification for high-escalation tasks



## 8. Cadence Summary

| Loop | Interval | Uses LLM? | Purpose |
|---|---|---|---|
| Task uptake | 60 seconds | Only if task claimed | Claim and execute work |
| Lease expiry check | 60 seconds (start of each cycle) | Never | Clear expired leases |
| Heartbeat | 5 minutes | Never | System health telemetry |
| Stuck detection | Hourly | Optional summary only | Find zombie/stuck tasks |
| Daily summary | Once daily | Optional | Operational report |

No LLM usage during cadence checks or scheduling logic.



## 9. API Endpoints Used by Dispatcher

All calls use `X-MC-Secret` header.

| Purpose | Method | Endpoint |
|---|---|---|
| Expire stale leases | POST | `/api/mission-control/tasks/expire-leases` |
| Check concurrency | GET | `/api/mission-control/agents/{id}/concurrency` |
| Claim task | POST | `/api/mission-control/tasks/claim` |
| Update task status | PATCH | `/api/mission-control/tasks/{id}` |
| Release task | POST | `/api/mission-control/tasks/{id}/release` |
| Create task run | POST | `/api/mission-control/task-runs` |
| Update task run | PATCH | `/api/mission-control/task-runs/{id}` |
| Add task comment | POST | `/api/mission-control/tasks/{id}/comments` |
| Add task link | POST | `/api/mission-control/tasks/{id}/links` |
| Add commentary | POST | `/api/mission-control/commentary` |

> **Note on domain redirect:** `mbrowne.ca` 307-redirects to `www.mbrowne.ca`. Use `https://www.mbrowne.ca/api/mission-control` as `MC_API_URL`, or ensure the HTTP client follows redirects (httpx does by default).



## 10. Success Criteria

The agent system is stable when:

* [ ] No duplicate task executions occur (lease + concurrency guard verified)
* [ ] No zombie `in_progress` tasks exist (lease expiry clears them)
* [ ] Blocked tasks include structured reason and detail
* [ ] `attempt_count` never exceeds `max_attempts` without human intervention
* [ ] Concurrency limits are respected per-agent and system-wide
* [ ] No LLM tokens are spent on scheduling or dispatch logic
* [ ] Each task execution has a complete task run audit trail
* [ ] Agents do not carry context between tasks
* [ ] Dispatcher auto-restarts on crash with no data loss



## 11. Build Sequence

| # | Step | Depends On |
|---|---|---|
| 1 | Phase 2 dashboard/backend deployed | [open-claw-phase-2.prd.md](./open-claw-phase-2.prd.md) |
| 2 | `missionctl` CLI built | [open-claw-external-services.prd.md](./open-claw-external-services.prd.md) Section 2 |
| 3 | Dispatcher main loop (claim, execute, update) | Steps 1–2 |
| 4 | Lease expiry integration in dispatch loop | Step 3 |
| 5 | Retry logic (auto re-queue under max_attempts) | Step 3 |
| 6 | Stuck detection loop (hourly) | Step 3 |
| 7 | Integration testing (full claim → execute → complete cycle) | Steps 3–6 |
