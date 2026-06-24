from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from config import settings
from lark import LarkClient, normalize_event, publish_with_cli, unwrap_event, verify_token
from llm import LLMClient
from state import Store, add_files, add_text, current_task, find_task, make_task, now, render_daily_context, today

app = FastAPI(title="KAI Lark Daily Report")


def deps():
    cfg = settings()
    return cfg, Store(cfg.data_root), LLMClient(cfg), LarkClient(cfg)


def handle_payload(payload: dict) -> str:
    cfg, store, llm, lark = deps()
    text = (payload.get("text") or "").strip()
    files = payload.get("files") or []
    message_id = payload.get("message_id")
    event_id = payload.get("event_id") or message_id

    with store.edit() as state:
        if event_id and event_id in state["processed_event_ids"]:
            return "duplicate event ignored"
        if event_id:
            state["processed_event_ids"] = (state["processed_event_ids"] + [event_id])[-500:]

        intent = llm.parse_intent(text) if text else {"intent": "add_material", "text": ""}
        name = intent.get("intent", "unknown")

        if name == "new_task":
            task = make_task(state, intent.get("task_title") or text)
            if text:
                add_text(task, intent.get("text") or text, message_id)
            if files:
                add_files(task, files, message_id)
            reply = f"已创建任务：{task['title']}"
        elif name == "switch_task":
            task = find_task(state, intent.get("task_id") or intent.get("task_title") or text)
            if not task:
                reply = "没找到这个任务，请发任务编号或完整标题。"
            else:
                state["current_task_id"] = task["id"]
                reply = f"已切换到任务：{task['title']}"
        elif name == "finish_task":
            task = current_task(state)
            if not task:
                reply = "当前没有任务，请先发“新任务：任务名”。"
            else:
                if text:
                    add_text(task, intent.get("text") or text, message_id)
                if files:
                    add_files(task, files, message_id)
                task["summary"] = llm.summarize_task(task)
                task["status"] = "completed"
                task["completed_at"] = now()
                state["current_task_id"] = None
                reply = f"已生成任务小结：{task['summary']}"
        elif name == "generate_daily":
            day = today()
            draft = llm.draft_daily(render_daily_context(state, day))
            state.setdefault("daily_reports", {})[day] = {"draft": draft, "updated_at": now()}
            report_path = store.root / "reports" / f"{day[:7]}.md"
            report_path.write_text(f"# {day} 日报\n\n{draft}\n", encoding="utf-8")
            reply = f"已生成今日日报草稿：\n{draft}"
        elif name == "publish":
            day = today()
            if day not in state.get("daily_reports", {}):
                draft = llm.draft_daily(render_daily_context(state, day))
                state.setdefault("daily_reports", {})[day] = {"draft": draft, "updated_at": now()}
                (store.root / "reports" / f"{day[:7]}.md").write_text(f"# {day} 日报\n\n{draft}\n", encoding="utf-8")
            result = publish_with_cli(store.root, day[:7], state)
            reply = f"已发布：{result.get('data', {}).get('document', {}).get('url') or state.get('documents', {}).get(day[:7], {}).get('doc')}"
        elif name == "add_material":
            task = current_task(state)
            if not task:
                reply = "当前没有任务，请先发“新任务：任务名”。"
            else:
                if text:
                    add_text(task, intent.get("text") or text, message_id)
                if files:
                    add_files(task, files, message_id)
                reply = f"已补充到任务：{task['title']}"
        else:
            reply = "我没理解，要新建任务、补充材料，还是生成日报？"

    lark.reply_text(message_id, reply)
    return reply


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/lark/events")
async def lark_events(request: Request) -> dict:
    cfg = settings()
    try:
        body = unwrap_event(await request.json(), cfg)
        verify_token(body, cfg)
        if body.get("type") == "url_verification" and body.get("challenge"):
            return {"challenge": body["challenge"]}
        payload = normalize_event(body)
        return {"ok": True, "reply": handle_payload(payload)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/simulate")
def simulate(payload: dict) -> dict:
    return {"ok": True, "reply": handle_payload(payload)}


@app.get("/state")
def get_state() -> dict:
    _, store, _, _ = deps()
    return store.load()


@app.post("/daily/generate")
def daily_generate(payload: dict | None = None) -> dict:
    _, store, llm, _ = deps()
    day = (payload or {}).get("date") or today()
    with store.edit() as state:
        draft = llm.draft_daily(render_daily_context(state, day))
        state.setdefault("daily_reports", {})[day] = {"draft": draft, "updated_at": now()}
        path = store.root / "reports" / f"{day[:7]}.md"
        path.write_text(f"# {day} 日报\n\n{draft}\n", encoding="utf-8")
    return {"ok": True, "date": day, "draft": draft}


@app.post("/daily/publish")
def daily_publish(payload: dict | None = None) -> dict:
    _, store, _, _ = deps()
    month = (payload or {}).get("month") or today()[:7]
    dry_run = bool((payload or {}).get("dry_run"))
    with store.edit() as state:
        return {"ok": True, "result": publish_with_cli(store.root, month, state, dry_run=dry_run)}
