INTENT_PROMPT = """你是日报 Bot 的意图解析器。只输出 JSON。
intent 只能是 new_task, switch_task, finish_task, add_material, generate_daily, publish, unknown。
字段：intent, task_id, task_title, text。
用户输入：{text}
"""

SUMMARY_PROMPT = """根据任务材料生成简短任务小结。只输出 JSON：{{"summary":"..."}}。
任务标题：{title}
材料：
{materials}
"""

DAILY_PROMPT = """根据上下文生成日报草稿。只输出 JSON：{{"draft":"..."}}。
日报格式：
## 今日完成
- ...
## 关键产出
- ...
## 问题与风险
- ...
## 明日计划
- ...

上下文：
{context}
"""
