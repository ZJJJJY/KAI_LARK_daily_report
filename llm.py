from __future__ import annotations

import json
import re

import httpx

from config import Settings
from prompts import DAILY_PROMPT, INTENT_PROMPT, SUMMARY_PROMPT


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

    def parse_intent(self, text: str) -> dict:
        stripped = text.strip()
        if stripped.startswith("新任务"):
            title = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
            return {"intent": "new_task", "task_id": None, "task_title": title, "text": stripped}
        if "生成日报" in stripped or stripped in {"日报", "今天日报"}:
            return {"intent": "generate_daily", "task_id": None, "task_title": None, "text": stripped}
        if "发布" in stripped:
            return {"intent": "publish", "task_id": None, "task_title": None, "text": stripped}
        finish_words = ["这个任务完成", "任务完成", "总结一下", "总结这个任务", "收尾"]
        if any(word in stripped for word in finish_words):
            return {"intent": "finish_task", "task_id": None, "task_title": None, "text": stripped}
        if stripped.startswith("完成了") or stripped.startswith("已完成"):
            return {"intent": "add_material", "task_id": None, "task_title": None, "text": stripped}
        return self.complete_json(INTENT_PROMPT.format(text=stripped))

    def summarize_task(self, task: dict) -> str:
        materials = []
        for material in task.get("materials", []):
            if material["type"] == "text":
                materials.append(f"- {material['text']}")
            else:
                materials.append(f"- 文件：{material.get('title') or material.get('file_id')}")
        if self.settings.llm_mode == "mock":
            return f"{task['title']}：已记录 {len(materials)} 条材料。"
        data = self.complete_json(SUMMARY_PROMPT.format(title=task["title"], materials="\n".join(materials)))
        return data.get("summary", "").strip()

    def draft_daily(self, context: str) -> str:
        if self.settings.llm_mode == "mock":
            return "## 今日完成\n- 已记录今日任务材料\n\n## 关键产出\n- 日报草稿\n\n## 问题与风险\n- 暂无\n\n## 明日计划\n- 继续推进"
        data = self.complete_json(DAILY_PROMPT.format(context=context))
        return data.get("draft", "").strip()
