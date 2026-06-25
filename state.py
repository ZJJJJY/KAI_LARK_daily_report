from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterator

_LOCK = Lock()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().date().isoformat()


def empty_state() -> dict:
    return {
        "current_task_id": None,
        "next_task_num": 1,
        "processed_event_ids": [],
        "tasks": [],
        "daily_reports": {},
        "documents": {},
    }


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "state.json"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(empty_state())

    def load(self) -> dict:
        self.ensure()
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    @contextmanager
    def edit(self) -> Iterator[dict]:
        # ponytail: single-process lock; use SQLite when this becomes multi-worker.
        with _LOCK:
            state = self.load()
            yield state
            self.save(state)


def make_task(state: dict, title: str) -> dict:
    task_id = f"T{state['next_task_num']:04d}"
    stamp = now()
    state["next_task_num"] += 1
    task = {
        "id": task_id,
        "title": title.strip() or "未命名任务",
        "status": "active",
        "materials": [],
        "summary": None,
        "created_at": stamp,
        "updated_at": stamp,
        "completed_at": None,
    }
    state["tasks"].append(task)
    state["current_task_id"] = task_id
    return task


def current_task(state: dict) -> dict | None:
    task_id = state.get("current_task_id")
    return find_task(state, task_id) if task_id else None


def find_task(state: dict, key: str | None) -> dict | None:
    if not key:
        return None
    key = key.strip()
    for task in state["tasks"]:
        if task["id"] == key or task["title"] == key:
            return task
    matches = [task for task in state["tasks"] if key in task["title"] or task["title"] in key]
    if len(matches) == 1:
        return matches[0]
    scored = [(longest_common_substring(key, task["title"]), task) for task in state["tasks"]]
    scored = sorted(scored, key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= 4 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def longest_common_substring(a: str, b: str) -> int:
    best = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            if j - i <= best:
                continue
            if a[i:j] in b:
                best = j - i
    return best


def add_text(task: dict, text: str, message_id: str | None = None) -> None:
    stamp = now()
    task["materials"].append({"type": "text", "text": text, "message_id": message_id, "created_at": stamp})
    task["updated_at"] = stamp


def add_files(task: dict, files: list[dict], message_id: str | None = None) -> None:
    stamp = now()
    for file in files:
        task["materials"].append(
            {
                "type": "file",
                "file_id": file.get("file_id"),
                "title": file.get("title") or file.get("name"),
                "message_id": message_id,
                "created_at": stamp,
            }
        )
    task["updated_at"] = stamp


def first_line(text: str) -> str:
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


def task_touched_on(task: dict, day: str) -> bool:
    dates = [date_prefix(task.get("created_at")), date_prefix(task.get("updated_at")), date_prefix(task.get("completed_at"))]
    dates += [date_prefix(m.get("created_at")) for m in task.get("materials", [])]
    return day in dates


def date_prefix(value: str | None) -> str:
    return value[:10] if value else ""


def render_task_list(state: dict) -> str:
    tasks = state.get("tasks", [])
    if not tasks:
        return "暂无任务。"
    return "\n".join(f"- {task['id']} {task['title']}（{task['status']}）" for task in tasks)


def render_task_block(task: dict) -> str:
    lines = [f"- {task['id']} {task['title']}（{task['status']}）"]
    if task.get("summary"):
        lines.append(f"  小结：{task['summary']}")
    for material in task.get("materials", []):
        if material["type"] == "text":
            lines.append(f"  文本：{material['text']}")
        else:
            lines.append(f"  文件：{material.get('title') or material.get('file_id')}")
    return "\n".join(lines)


def render_daily_task_blocks(state: dict, day: str) -> tuple[str, str]:
    tasks = [task for task in state["tasks"] if task_touched_on(task, day)]
    finished = [render_task_block(task) for task in tasks if task.get("status") == "completed"]
    ongoing = [render_task_block(task) for task in tasks if task.get("status") != "completed"]
    return "\n\n".join(finished) or "暂无。", "\n\n".join(ongoing) or "暂无。"


def safe_month(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("month must be YYYY-MM")
    return value
