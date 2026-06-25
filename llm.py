from __future__ import annotations

import json
import re

import httpx

from config import Settings
from prompts import DAILY_PROMPT, DRAFT_TEMPLATE, INTENT_PROMPT, SUMMARY_PROMPT, SUMMARY_TEMPLATE


def extract_json(text: str) -> dict:
    if text is None:
        raise ValueError("LLM returned empty content")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete_json(self, prompt: str) -> dict:
        if self.settings.llm_mode == "mock":
            return {"intent": "add_material", "task_id": None, "task_title": None, "text": prompt[-80:]}
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required")
        url = self.settings.llm_base_url.rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": "Return one valid JSON object only. No markdown. No explanation."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        with httpx.Client(timeout=60, trust_env=False) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return extract_json(content)

    def parse_intent(self, text: str, task_list: str = "暂无任务。") -> dict:
        stripped = text.strip()
        if stripped in {"任务列表", "查看任务", "列出任务", "当前任务"}:
            return {"intent": "list_tasks", "task_id": None, "task_title": None, "text": stripped}
        if stripped.startswith(("新任务", "创建一个任务", "创建任务")):
            title = stripped
            for sep in ["：", ":"]:
                if sep in title:
                    title = title.split(sep, 1)[1]
                    break
            title = title.replace("创建一个任务", "", 1).replace("创建任务", "", 1).replace("新任务", "", 1).strip(" ：:")
            return {"intent": "new_task", "task_id": None, "task_title": title, "text": stripped}
        for prefix in ["切换到", "切到", "切换任务到", "切换任务"]:
            if stripped.startswith(prefix):
                return {"intent": "switch_task", "task_id": None, "task_title": stripped[len(prefix):].strip(" ：:"), "text": stripped}
        if "生成日报" in stripped or stripped in {"日报", "今天日报"}:
            return {"intent": "generate_daily", "task_id": None, "task_title": None, "text": stripped}
        if "发布" in stripped:
            return {"intent": "publish", "task_id": None, "task_title": None, "text": stripped}
        finish_words = ["这个任务完成", "任务完成", "总结一下", "总结这个任务", "收尾"]
        if any(word in stripped for word in finish_words):
            return {"intent": "finish_task", "task_id": None, "task_title": None, "text": stripped}
        if stripped.startswith(("完成了", "已完成", "添加了", "补充", "记录")):
            return {"intent": "add_material", "task_id": None, "task_title": None, "text": stripped}
        return self.complete_json(INTENT_PROMPT.format(user_text_input=stripped, task_list=task_list))

    def summarize_task(self, task: dict) -> str:
        text_blocks = []
        file_blocks = []
        for material in task.get("materials", []):
            if material["type"] == "text":
                text_blocks.append(f"- {material['text']}")
            else:
                file_blocks.append(f"- {material.get('title') or material.get('file_id')}")
        if self.settings.llm_mode == "mock":
            return f"# 任务目标\n{task['title']}\n\n# 关键结果\n已记录 {len(text_blocks) + len(file_blocks)} 条材料。\n\n# 后续事项\n暂无。"
        data = self.complete_json(
            SUMMARY_PROMPT.format(
                text_blocks="\n".join(text_blocks) or "暂无。",
                file_blocks="\n".join(file_blocks) or "暂无。",
                summary_template=SUMMARY_TEMPLATE,
            )
        )
        return data.get("summary", "").strip()

    def draft_daily(self, finished_task_blocks: str, ongoing_task_blocks: str) -> str:
        if self.settings.llm_mode == "mock":
            return "# 今日完成\n- 已记录今日任务材料\n\n# 明日计划\n- 继续推进\n\n# 需要的相关支持\n- 暂无"
        data = self.complete_json(
            DAILY_PROMPT.format(
                finished_task_blocks=finished_task_blocks,
                ongoing_task_blocks=ongoing_task_blocks,
                draft_template=DRAFT_TEMPLATE,
            )
        )
        return data.get("draft", "").strip()
