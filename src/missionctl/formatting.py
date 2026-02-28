from __future__ import annotations

import json
from typing import Any


def format_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)


def format_text_claim(data: dict[str, Any] | None) -> str:
    if not data:
        return "No eligible tasks"
    task = data.get("task", {})
    task_run = data.get("task_run", {})
    task_id = task.get("id", "<unknown>")
    attempt = task.get("attempt_count", "<unknown>")
    run_id = task_run.get("id", "<unknown>")
    title = task.get("title", "")
    queue = task.get("queue", "")
    priority = task.get("priority", "")
    lines = [f"Claimed task {task_id} (attempt {attempt})", f"Run ID: {run_id}"]
    if title:
        lines.append(f"Title: {title}")
    if queue:
        lines.append(f"Queue: {queue}")
    if priority:
        lines.append(f"Priority: {priority}")
    return "\n".join(lines)


def format_text_concurrency(data: dict[str, Any]) -> str:
    return f"Running: {data.get('running', 0)} / {data.get('max', 0)}"


def format_text_list(items: list[dict[str, Any]], columns: list[str]) -> str:
    if not items:
        return "No results"
    rows: list[str] = []
    for item in items:
        rows.append(", ".join(f"{col}={item.get(col)}" for col in columns))
    return "\n".join(rows)


def format_text_detail(item: dict[str, Any], fields: list[str]) -> str:
    return "\n".join(f"{field}={item.get(field)}" for field in fields)
