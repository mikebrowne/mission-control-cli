# PRD — OpenClaw Executor: Automated Task Dispatch & Execution

> **Status:** IN PROGRESS
>
> **Prerequisites:**
> - Mission Control Phase 2 deployed ([open-claw-phase-2.prd.md](./open-claw-phase-2.prd.md))
> - OpenClaw Gateway running on Mac Mini
> - Agents (Rachel, Vanessa) configured in OpenClaw
>
> **Scope:** End-to-end automated task execution — from a task entering `queued` status to a completed result written back to Mission Control with zero human intervention.
>
> **Related PRDs:**
> - [open-claw-phase-2.prd.md](./open-claw-phase-2.prd.md) — Schema, API routes, dashboard
> - [open-claw-phase-2-agent.prd.md](./open-claw-phase-2-agent.prd.md) — Agent workflow & dispatcher design
> - [open-claw-external-services.prd.md](./open-claw-external-services.prd.md) — CLI, telemetry, integration



---



## 1. High Level

### 1.1 Problem

Tasks enter `queued` status in Mission Control but never execute automatically. The previous design had three issues:

1. **Concurrency deadlock.** `getAgentConcurrency` counted all `in_progress` tasks regardless of lease expiry. A single stale task permanently blocked dispatch for that agent.
2. **No attempt overflow guard.** The `claim_task` RPC could push `attempt_count` past `max_attempts`, creating invalid states.
3. **No execution bridge.** No process existed to take a claimed task, run it through OpenClaw, and write results back to Mission Control.

Issues 1 and 2 are fixed (lease-aware concurrency, attempt guard). This PRD addresses issue 3: building the execution bridge.

### 1.2 Execution Model: Run-Once via `openclaw agent`

OpenClaw's `openclaw agent` CLI command runs a **complete agent loop** — intake, context assembly, model inference, tool execution, streaming reply, and persistence — in a single synchronous call. This maps directly to the Phase 2 Agent PRD's "Option A: Run-once model."

```
Dispatcher claims task
    → spawns: openclaw agent --agent rachel --session-id "mc-task-<id>" --message "<prompt>" --json
    → agent runs to completion (including all tool calls)
    → dispatcher captures reply
    → writes results back to Mission Control
```

Each task gets an **isolated session** via `--session-id`. No context bleed between tasks. No long-running sessions to manage. No separate executor or closer process.

This is chosen over `sessions_spawn` (OpenClaw's sub-agent tool) because:

- `sessions_spawn` is an agent tool for agent-to-agent orchestration — it requires an existing agent session to call it from
- `openclaw agent` is a CLI command designed for automation — it can be called directly from a Python subprocess
- Run-once is synchronous: the dispatcher gets the result immediately without polling
- It eliminates the need for a separate executor process, closer process, session history polling, or `MISSION_OUTPUT::` completion markers

### 1.3 Architecture

```
Dispatcher (Python, Mac Mini)
    │
    ├── HTTP ──→ Mission Control API (Vercel)
    │               └── Supabase
    │
    └── subprocess ──→ openclaw agent (local Gateway)
                          └── AI model (API provider)
```

The dispatcher is the **single orchestration process**. It handles claiming, execution, result writing, retries, and error recovery. No other runtime components are needed.

### 1.4 Agent Roles

| Agent | Queues | Completion Status | Max Concurrency |
|---|---|---|---|
| Rachel AI | `ops`, `dev`, `admin` | `done` | 1 |
| Vanessa AI | `marketing` | `in_review` (human approval required) | 1 |

Max parallel tasks across all agents: 2 (one per agent).

### 1.5 Dispatch Cycle (every 60 seconds)

```
1. POST /tasks/expire-leases
   → Clear any stale in_progress tasks from previous cycles

2. For each agent (rachel, vanessa):
   a. GET /agents/{id}/concurrency
   b. If running >= max → skip this agent

   c. POST /tasks/claim { agent_id, queue, lease_duration_seconds: 600 }
      → If data is null → no work available, skip
      → Extract task from response.data.task
      → Extract task_run_id from response.data.task_run.id

   d. Spawn subprocess (async, so both agents can run in parallel):
      openclaw agent \
        --agent <name> \
        --session-id "mc-task-<task.id>-attempt-<attempt_count>" \
        --message "<task prompt>" \
        --json \
        --timeout 570

   e. On completion → parse reply, update task + task_run + comment
   f. On failure   → fail/release task, update task_run with error
   g. On blocked   → set blocked status with reason + detail
```

### 1.6 What This PRD Does NOT Cover

- `sessions_spawn` / multi-turn session model (future enhancement for complex workflows)
- `dispatched_pending_start` status (future observability improvement)
- Server-side lease expiry (future; currently dispatcher-triggered)
- Dashboard UI for executor status (can use existing task/concurrency views)
- OpenClaw internals, skill definitions, or agent reasoning logic



---



## 2. Mission Control (Website)

Changes to the website codebase to support the executor.

### 2.1 Schema: New Columns on `mc_tasks`

Add two nullable columns to track which OpenClaw session handled a task:

| Column | Type | Default | Nullable | Purpose |
|---|---|---|---|---|
| `openclaw_session_key` | text | null | yes | Session key used for this task's execution (e.g. `agent:rachel:mc-task-<uuid>-attempt-1`) |
| `openclaw_run_id` | text | null | yes | OpenClaw run ID returned by the agent command |

These are audit/debugging fields. The dispatcher writes them after claiming a task. They let you:
- Inspect the OpenClaw transcript on disk if something goes wrong
- Correlate Mission Control tasks with OpenClaw session state
- See in the dashboard which session handled which task

### 2.2 SQL Migration

Create `docs/migrations/004_executor_session_tracking.sql`:

```sql
-- Executor session tracking: link tasks to OpenClaw sessions

ALTER TABLE public.mc_tasks
  ADD COLUMN IF NOT EXISTS openclaw_session_key text,
  ADD COLUMN IF NOT EXISTS openclaw_run_id text;

CREATE INDEX IF NOT EXISTS idx_mc_tasks_openclaw_session
  ON public.mc_tasks(openclaw_session_key)
  WHERE openclaw_session_key IS NOT NULL;
```

### 2.3 TypeScript Type Update

In `website/src/types/mission-control.ts`, add to the `McTask` interface:

```typescript
export interface McTask {
    // ... existing fields ...
    openclaw_session_key: string | null;
    openclaw_run_id: string | null;
}
```

### 2.4 Service Layer Update

In `website/src/lib/mission-control/services/tasksService.ts`:

- `updateTask()` already accepts `Partial<CreateTaskInput>`. Extend `CreateTaskInput` (or the update input type) to include `openclaw_session_key` and `openclaw_run_id`.
- No changes needed to `claimTask()`, `releaseTask()`, or `expireLeases()`.

### 2.5 API Route Update

`PATCH /api/mission-control/tasks/[id]` already accepts arbitrary task fields. The new columns will flow through automatically once the type and service are updated.

No new API endpoints are needed.

### 2.6 Mock Data Update

Add `openclaw_session_key: null` and `openclaw_run_id: null` to all mock task objects in `website/src/data/mission-control/`.

### 2.7 Zod Schema Update

In `website/src/lib/mission-control/schemas.ts`, add the new fields to the task update schema:

```typescript
openclaw_session_key: z.string().nullable().optional(),
openclaw_run_id: z.string().nullable().optional(),
```

### 2.8 Previously Completed Fixes (Phase 0)

These changes are already applied and should be deployed:

**Lease-aware concurrency** (`agentsService.ts`):
```typescript
const { count, error } = await supabase
    .from("mc_tasks")
    .select("*", { count: "exact", head: true })
    .eq("claimed_by", id)
    .eq("status", "in_progress")
    .gt("lease_expires_at", now);  // ← NEW: only count valid leases
```

**Attempt guard in `claim_task` RPC** (`003_phase2_task_execution.sql`):
```sql
WHERE t.status = 'queued'
  AND t.attempt_count < t.max_attempts  -- ← NEW: prevent retry overflow
  AND (t.assigned_agent_id IS NULL OR t.assigned_agent_id = p_agent_id)
  AND (p_queue IS NULL OR t.queue = p_queue)
```

**Claim response includes task_run** (`tasks/claim/route.ts`):
```typescript
return NextResponse.json({ ok: true, data: { task, task_run: taskRun } });
```



---



## 3. Supabase

Database changes that must be applied directly in the Supabase SQL Editor.

### 3.1 Run the New Migration

Execute the contents of `004_executor_session_tracking.sql` (Section 2.2 above) in the Supabase SQL Editor.

### 3.2 Re-run the `claim_task` RPC

The attempt guard was added to the migration file but must also be applied to the live database. Paste and execute the full function:

```sql
CREATE OR REPLACE FUNCTION public.claim_task(
    p_agent_id uuid,
    p_queue text DEFAULT NULL,
    p_lease_duration interval DEFAULT interval '10 minutes'
)
RETURNS SETOF public.mc_tasks
LANGUAGE sql
AS $$
    UPDATE public.mc_tasks
    SET
        status = 'in_progress',
        claimed_by = p_agent_id,
        lease_expires_at = now() + p_lease_duration,
        attempt_count = attempt_count + 1
    WHERE id = (
        SELECT t.id
        FROM public.mc_tasks t
        WHERE t.status = 'queued'
          AND t.attempt_count < t.max_attempts
          AND (t.assigned_agent_id IS NULL OR t.assigned_agent_id = p_agent_id)
          AND (p_queue IS NULL OR t.queue = p_queue)
        ORDER BY
            CASE t.priority
                WHEN 'urgent' THEN 0
                WHEN 'high' THEN 1
                WHEN 'normal' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            t.created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *;
$$;
```

Both operations are idempotent and safe to run at any time.



---



## 4. CLI (`missionctl`)

The dispatcher can call Mission Control APIs directly via HTTP, but wrapping calls in the CLI provides consistent logging, retry logic, and a testable interface. The CLI needs commands for every step of the dispatch cycle.

### 4.1 Required Commands

| Command | API Call | Purpose |
|---|---|---|
| `missionctl tasks expire-leases` | `POST /tasks/expire-leases` | Clear stale leases at start of each cycle |
| `missionctl agents concurrency <agent_id>` | `GET /agents/{id}/concurrency` | Check if agent has a free slot |
| `missionctl tasks claim --agent-id <uuid> --queue <queue> [--lease-seconds 600]` | `POST /tasks/claim` | Claim next eligible task |
| `missionctl tasks update <task_id> --status <status> [--blocked-reason ...] [--openclaw-session-key ...]` | `PATCH /tasks/{id}` | Update task status and fields |
| `missionctl tasks release <task_id> --agent-id <uuid> [--reason "..."]` | `POST /tasks/{id}/release` | Release a task back to queued |
| `missionctl tasks comment <task_id> --author "Rachel AI" --body "..."` | `POST /tasks/{id}/comments` | Add output summary as a comment |
| `missionctl task-runs update <run_id> --outcome <outcome> [--duration-ms ...] [--error-message ...]` | `PATCH /task-runs/{id}` | Record execution result |

### 4.2 Claim Response Parsing

The `POST /tasks/claim` response shape changed. The CLI must handle:

```json
{
  "ok": true,
  "data": {
    "task": { "id": "...", "title": "...", "status": "in_progress", ... },
    "task_run": { "id": "...", "task_id": "...", "attempt": 1, "started_at": "...", ... }
  }
}
```

When no task is available: `{ "ok": true, "data": null }`.

The `tasks claim` command output (with `--format json`) should include both the task and task_run so the dispatcher can extract `task_run.id` without a separate lookup.

### 4.3 Concurrency Response

```json
{ "ok": true, "data": { "max": 1, "running": 0 } }
```

Now lease-aware: `running` only counts tasks where `lease_expires_at > now()`. Expired leases read as `running: 0` even before `expire-leases` runs.

### 4.4 Output Format

All commands must support `--format json` for machine-readable output. The dispatcher should always use JSON mode. Human-readable table output is the default for interactive use.

### 4.5 Error Handling

| Scenario | Exit Code | Dispatcher Action |
|---|---|---|
| API returned success | 0 | Process response |
| Auth failure (401) | 1 | Log and halt cycle |
| Validation error (400) | 1 | Log task ID and error |
| Concurrency limit (409) | 0 | Skip agent (expected) |
| Server error (500) | 1 | Log and retry next cycle |
| Network unreachable | 2 | Log and retry next cycle |

The 409 (concurrency limit) from the claim endpoint should be treated as a normal "no work" response, not an error.



---



## 5. Agent (Dispatcher + OpenClaw)

The dispatcher is the runtime component that ties everything together. It runs on the Mac Mini as a background process.

### 5.1 Dispatcher Structure

```
dispatcher/
├── dispatcher.py       # Main async loop (entry point)
├── executor.py         # openclaw agent subprocess wrapper
├── mc_client.py        # Mission Control HTTP client
├── prompt.py           # Task prompt template builder
├── config.py           # Environment variables and agent registry
└── requirements.txt    # httpx, asyncio (stdlib)
```

### 5.2 Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `MC_API_URL` | Mission Control API base URL | `https://www.mbrowne.ca/api/mission-control` |
| `MC_TELEMETRY_SECRET` | Shared secret for `X-MC-Secret` header | Required |
| `DISPATCH_INTERVAL` | Seconds between dispatch cycles | `60` |
| `DEFAULT_LEASE_SECONDS` | Lease duration when claiming | `600` |
| `AGENT_TIMEOUT_SECONDS` | OpenClaw agent run timeout | `570` (lease minus 30s buffer) |
| `RACHEL_AGENT_ID` | Rachel's UUID in mc_agents | Required |
| `VANESSA_AGENT_ID` | Vanessa's UUID in mc_agents | Required |

### 5.3 Agent Registry

```python
AGENTS = [
    {
        "id": os.environ["RACHEL_AGENT_ID"],
        "name": "rachel",
        "queues": ["ops", "dev", "admin"],
        "completion_status": "done",
        "author_name": "Rachel AI",
    },
    {
        "id": os.environ["VANESSA_AGENT_ID"],
        "name": "vanessa",
        "queues": ["marketing"],
        "completion_status": "in_review",
        "author_name": "Vanessa AI",
    },
]
```

### 5.4 Mission Control HTTP Client

Thin wrapper around `httpx` with retry logic and `X-MC-Secret` auth:

```python
class MCClient:
    def __init__(self, base_url: str, secret: str):
        self.client = httpx.Client(
            base_url=base_url,
            headers={"X-MC-Secret": secret, "Content-Type": "application/json"},
            timeout=30.0,
        )

    def expire_leases(self) -> list[dict]:
        r = self.client.post("/tasks/expire-leases")
        return r.json().get("data", [])

    def get_concurrency(self, agent_id: str) -> dict:
        r = self.client.get(f"/agents/{agent_id}/concurrency")
        return r.json()["data"]  # { "max": int, "running": int }

    def claim_task(self, agent_id: str, queue: str, lease_seconds: int = 600) -> dict | None:
        r = self.client.post("/tasks/claim", json={
            "agent_id": agent_id,
            "queue": queue,
            "lease_duration_seconds": lease_seconds,
        })
        body = r.json()
        if r.status_code == 409:  # at concurrency limit
            return None
        return body.get("data")  # { "task": {...}, "task_run": {...} } or None

    def update_task(self, task_id: str, **fields) -> dict:
        r = self.client.patch(f"/tasks/{task_id}", json=fields)
        return r.json()

    def update_task_run(self, run_id: str, **fields) -> dict:
        r = self.client.patch(f"/task-runs/{run_id}", json=fields)
        return r.json()

    def release_task(self, task_id: str, agent_id: str, reason: str = "") -> dict:
        r = self.client.post(f"/tasks/{task_id}/release", json={
            "agent_id": agent_id,
            "reason": reason,
        })
        return r.json()

    def add_comment(self, task_id: str, author: str, body: str) -> dict:
        r = self.client.post(f"/tasks/{task_id}/comments", json={
            "author": author,
            "body": body,
        })
        return r.json()
```

### 5.5 OpenClaw Executor

Wraps the `openclaw agent` CLI as an async subprocess:

```python
@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str

async def execute_task(
    agent_name: str,
    session_id: str,
    prompt: str,
    timeout_seconds: int,
) -> ExecutionResult:
    proc = await asyncio.create_subprocess_exec(
        "openclaw", "agent",
        "--agent", agent_name,
        "--session-id", session_id,
        "--message", prompt,
        "--json",
        "--timeout", str(timeout_seconds),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds + 30,  # buffer beyond agent timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return ExecutionResult(exit_code=-1, stdout="", stderr="Dispatcher timeout exceeded")

    return ExecutionResult(
        exit_code=proc.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
```

Key details:

- `--agent <name>` targets the configured OpenClaw agent
- `--session-id "mc-task-<task_id>-attempt-<N>"` isolates each task in its own session
- `--json` returns structured output
- `--timeout` tells OpenClaw to abort if the run exceeds this duration
- `stdin=DEVNULL` prevents the subprocess from hanging on interactive prompts
- Dispatcher timeout (`wait_for`) is set higher than the agent timeout as a safety net

### 5.6 Task Prompt Template

```python
def build_task_prompt(task: dict) -> str:
    parts = [
        "You have been assigned a Mission Control task.\n",
        f"Task ID: {task['id']}",
        f"Title: {task['title']}",
    ]
    if task.get("description"):
        parts.append(f"Description: {task['description']}")
    if task.get("queue"):
        parts.append(f"Queue: {task['queue']}")
    if task.get("priority"):
        parts.append(f"Priority: {task['priority']}")
    if task.get("task_type"):
        parts.append(f"Type: {task['task_type']}")

    parts.append("")
    parts.append("Execute this task completely. When finished, state your results clearly.")
    parts.append("")
    parts.append(
        "If you cannot proceed because you need human input, access, or clarification, "
        "respond with NEEDS_HUMAN on its own line followed by the reason. Example:"
    )
    parts.append("NEEDS_HUMAN: needs_human_input: I need the client's email address to proceed.")
    parts.append("")
    parts.append(
        "If you encounter a tool error or infrastructure problem, describe the error clearly."
    )
    return "\n".join(parts)
```

The prompt is intentionally simple. The agent's IDENTITY.md and OpenClaw's system prompt provide the rest of the context. The task prompt only needs to convey what to do and how to signal problems.

### 5.7 Result Parsing

```python
def parse_agent_reply(stdout: str) -> tuple[str, str | None]:
    """Returns (reply_text, blocked_signal_or_none)."""
    try:
        data = json.loads(stdout)
        reply = data.get("reply", data.get("text", stdout))
    except (json.JSONDecodeError, TypeError):
        reply = stdout.strip()

    for line in reply.splitlines():
        stripped = line.strip()
        if stripped.startswith("NEEDS_HUMAN"):
            return reply, stripped
    return reply, None

BLOCKED_REASON_MAP = {
    "needs_human_input": "needs_human_input",
    "missing_access": "missing_access",
    "external_dependency": "external_dependency",
    "ambiguous_requirements": "ambiguous_requirements",
    "tool_error": "tool_error",
    "compliance_risk": "compliance_risk",
    "rate_limited": "rate_limited",
    "infra_unavailable": "infra_unavailable",
}

def parse_blocked_signal(signal: str) -> tuple[str, str]:
    """Parse 'NEEDS_HUMAN: reason_key: detail text' into (blocked_reason, blocked_detail)."""
    parts = signal.replace("NEEDS_HUMAN:", "").strip().split(":", 1)
    reason_key = parts[0].strip() if parts else "needs_human_input"
    detail = parts[1].strip() if len(parts) > 1 else reason_key
    reason = BLOCKED_REASON_MAP.get(reason_key, "needs_human_input")
    return reason, detail
```

### 5.8 Main Dispatch Loop

```python
async def dispatch_cycle(mc: MCClient, agents: list[dict]):
    # Step 1: Clean up stale leases
    expired = mc.expire_leases()
    if expired:
        log.info(f"Expired {len(expired)} stale lease(s)")

    # Step 2: Claim and execute per agent
    pending = []
    for agent in agents:
        concurrency = mc.get_concurrency(agent["id"])
        log.debug(f"{agent['name']}: running={concurrency['running']}/{concurrency['max']}")

        if concurrency["running"] >= concurrency["max"]:
            continue

        claimed = None
        for queue in agent["queues"]:
            claimed = mc.claim_task(agent["id"], queue)
            if claimed:
                break

        if not claimed:
            continue

        pending.append(run_task(mc, agent, claimed))

    if pending:
        await asyncio.gather(*pending)

async def run_task(mc: MCClient, agent: dict, claim_data: dict):
    task = claim_data["task"]
    task_run_id = claim_data["task_run"]["id"]
    session_id = f"mc-task-{task['id']}-attempt-{task['attempt_count']}"
    session_key = f"agent:{agent['name']}:{session_id}"
    prompt = build_task_prompt(task)
    started = time.time()

    # Record session binding on the task
    mc.update_task(task["id"],
        openclaw_session_key=session_key,
        openclaw_run_id=None,  # set after execution if available
    )

    log.info(f"Executing task {task['id'][:8]}... ({task['title']}) via {agent['name']}")

    # Execute
    try:
        result = await execute_task(
            agent_name=agent["name"],
            session_id=session_id,
            prompt=prompt,
            timeout_seconds=int(os.environ.get("AGENT_TIMEOUT_SECONDS", 570)),
        )
    except Exception as e:
        log.error(f"Failed to start execution for task {task['id'][:8]}: {e}")
        mc.release_task(task["id"], agent["id"], reason=f"Execution failed to start: {e}")
        mc.update_task_run(task_run_id,
            outcome="failed",
            error_message=str(e),
            completed_at=now_iso(),
            duration_ms=int((time.time() - started) * 1000),
        )
        return

    duration_ms = int((time.time() - started) * 1000)
    reply, blocked_signal = parse_agent_reply(result.stdout)
    completed_at = now_iso()

    # Route outcome
    if result.exit_code == 0 and blocked_signal is None:
        # Success
        mc.update_task(task["id"], status=agent["completion_status"])
        mc.update_task_run(task_run_id,
            outcome="success", completed_at=completed_at, duration_ms=duration_ms,
        )
        mc.add_comment(task["id"], author=agent["author_name"], body=reply)
        log.info(f"Task {task['id'][:8]} completed successfully ({duration_ms}ms)")

    elif blocked_signal:
        # Blocked — agent needs human input
        reason, detail = parse_blocked_signal(blocked_signal)
        mc.update_task(task["id"],
            status="blocked", blocked_reason=reason, blocked_detail=detail,
        )
        mc.update_task_run(task_run_id,
            outcome="blocked", completed_at=completed_at, duration_ms=duration_ms,
        )
        mc.add_comment(task["id"], author=agent["author_name"], body=reply)
        log.info(f"Task {task['id'][:8]} blocked: {reason}")

    else:
        # Failed
        error_msg = result.stderr or reply or "Unknown error"
        mc.update_task(task["id"], status="failed")
        mc.update_task_run(task_run_id,
            outcome="failed", error_message=error_msg,
            completed_at=completed_at, duration_ms=duration_ms,
        )
        log.warning(f"Task {task['id'][:8]} failed: {error_msg[:100]}")

        # Auto re-queue if attempts remain
        if task["attempt_count"] < task["max_attempts"]:
            mc.update_task(task["id"], status="queued")
            log.info(f"Task {task['id'][:8]} re-queued (attempt {task['attempt_count']}/{task['max_attempts']})")

async def main():
    mc = MCClient(
        base_url=os.environ["MC_API_URL"],
        secret=os.environ["MC_TELEMETRY_SECRET"],
    )
    interval = int(os.environ.get("DISPATCH_INTERVAL", 60))

    log.info(f"Dispatcher started (interval={interval}s)")
    while True:
        try:
            await dispatch_cycle(mc, AGENTS)
        except Exception as e:
            log.error(f"Dispatch cycle error: {e}", exc_info=True)
        await asyncio.sleep(interval)

if __name__ == "__main__":
    asyncio.run(main())
```

### 5.9 OpenClaw Agent Configuration

Agents must be configured in OpenClaw on the Mac Mini before the dispatcher can target them.

**Add agents:**

```bash
openclaw agents add rachel --workspace ~/.openclaw/workspace-rachel
openclaw agents add vanessa --workspace ~/.openclaw/workspace-vanessa
```

**Create identity files:**

`~/.openclaw/workspace-rachel/IDENTITY.md`:
```markdown
You are Rachel AI, Lead Operations Agent for MBrowne Mortgage.

You execute operational, development, and admin tasks assigned through Mission Control.
Each task is an atomic unit of work. Complete it fully and report your results.
Do not reference previous tasks or carry context forward.
```

`~/.openclaw/workspace-vanessa/IDENTITY.md`:
```markdown
You are Vanessa AI, Research and Content Agent for MBrowne Mortgage.

You execute marketing and content tasks assigned through Mission Control.
Your outputs go to human review before publication.
Each task is an atomic unit of work. Complete it fully and report your results.
Do not reference previous tasks or carry context forward.
```

**OpenClaw config** (`~/.openclaw/openclaw.json`):

```json5
{
  agents: {
    defaults: {
      timeoutSeconds: 570,
      model: { primary: "gpt-codex-5.1" },
    },
    list: [
      { id: "rachel", workspace: "~/.openclaw/workspace-rachel" },
      { id: "vanessa", workspace: "~/.openclaw/workspace-vanessa" },
    ],
  },
}
```

### 5.10 Process Management

The dispatcher runs as a background process managed by pm2 or launchd:

**pm2:**
```bash
pm2 start dispatcher.py --name mc-dispatcher --interpreter python3 --restart-delay 5000
pm2 save
```

**launchd (macOS):**
Create `~/Library/LaunchAgents/com.mbrowne.mc-dispatcher.plist` pointing to the dispatcher script. Set `KeepAlive: true` and `RunAtLoad: true`.

### 5.11 Logging

The dispatcher logs every significant action to stdout (captured by pm2/launchd):

| Event | Log Level | Example |
|---|---|---|
| Cycle start | DEBUG | `Dispatch cycle starting` |
| Lease expiry | INFO | `Expired 2 stale lease(s)` |
| Concurrency check | DEBUG | `rachel: running=0/1` |
| No work available | DEBUG | `rachel: no eligible tasks in ops, dev, admin` |
| Task claimed | INFO | `Claimed task a1b2c3d4 (Review SEO audit) for rachel` |
| Execution start | INFO | `Executing task a1b2c3d4... via rachel` |
| Task success | INFO | `Task a1b2c3d4 completed successfully (12340ms)` |
| Task blocked | INFO | `Task a1b2c3d4 blocked: needs_human_input` |
| Task failed | WARNING | `Task a1b2c3d4 failed: Tool error in email client` |
| Task re-queued | INFO | `Task a1b2c3d4 re-queued (attempt 1/3)` |
| Spawn failure | ERROR | `Failed to start execution for task a1b2c3d4: FileNotFoundError` |
| Cycle error | ERROR | `Dispatch cycle error: ConnectionError` |



---



## Appendix A: Acceptance Tests

| # | Test | Expected Result |
|---|---|---|
| 1 | Create a queued task for Rachel, run one dispatch cycle | Task goes to `done`, task_run has `outcome: success`, comment added with output |
| 2 | Create a queued task for Vanessa, run one dispatch cycle | Task goes to `in_review`, task_run has `outcome: success` |
| 3 | Claim a task, force OpenClaw to fail (bad model, timeout) | Task goes to `failed`, task_run has error_message, task re-queued if under max_attempts |
| 4 | Claim a task, OpenClaw binary not found | Task is released immediately, task_run records spawn error |
| 5 | Two queued tasks (one ops, one marketing), run one cycle | Both execute in parallel (Rachel + Vanessa), both complete |
| 6 | Agent at concurrency limit (task already in_progress with valid lease) | Dispatcher skips that agent, does not claim |
| 7 | Stale lease exists (lease_expires_at < now, status still in_progress) | `expire-leases` clears it, concurrency reads as 0, next task can be claimed |
| 8 | Task with attempt_count = max_attempts in queued status | Claim returns null, task is not picked up |
| 9 | Agent outputs NEEDS_HUMAN signal | Task goes to `blocked` with correct reason and detail |
| 10 | Dispatcher crashes mid-cycle, restarts | Stale lease expires, task retries on next cycle, no data loss |

## Appendix B: Future Enhancements (Not In Scope)

| Enhancement | Description | When |
|---|---|---|
| `sessions_spawn` integration | For multi-turn tasks that require back-and-forth | After run-once is stable |
| Server-side lease expiry | pg_cron or Supabase scheduled function instead of dispatcher call | After dispatch is reliable |
| `dispatched_pending_start` status | Distinguish "claimed" from "executing" for observability | When needed for debugging |
| Heartbeat/commentary logging | Dispatcher posts a commentary entry each cycle proving it's alive | Nice-to-have |
| Task output artifacts | Store structured outputs (not just comments) for downstream use | When tasks produce files/data |
| Token usage tracking | Parse OpenClaw's `--json` output for token counts, write to task_run | When cost tracking matters |

## Appendix C: Build Sequence

| # | Step | Owner | Depends On |
|---|---|---|---|
| 1 | Deploy Phase 0 fixes (lease-aware concurrency + attempt guard) | Website deploy + Supabase SQL | Done |
| 2 | Add session tracking columns to mc_tasks | Website (this repo) | Step 1 |
| 3 | Deploy Supabase migration (004 + re-run claim_task RPC) | Supabase SQL Editor | Step 2 |
| 4 | Verify missionctl CLI has required commands (Section 4.1) | CLI developer | Step 1 |
| 5 | Configure Rachel + Vanessa in OpenClaw | Mac Mini ops | OpenClaw installed |
| 6 | Build dispatcher (mc_client, executor, prompt, main loop) | Agent developer | Steps 3–5 |
| 7 | Integration test: single task end-to-end | All | Step 6 |
| 8 | Process management (pm2/launchd) + restart testing | Mac Mini ops | Step 7 |
| 9 | Run acceptance tests (Appendix A) | All | Step 8 |
