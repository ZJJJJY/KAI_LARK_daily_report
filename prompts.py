SUMMARY_TEMPLATE = """# 任务目标
# 关键结果
# 后续事项"""

DRAFT_TEMPLATE = """# 今日完成
# 明日计划
# 需要的相关支持"""

INTENT_PROMPT = """<role>
你是日报撰写助手的意图解析器，负责判断用户想做什么。
</role>

<task>
你需要根据用户输入的文本判断用户意图。意图类型包含：
1. new_task：指需要开始一个新的任务
2. switch_task：指用户目前描述的是之前未完成的任务
3. finish_task：指用户认为正在处理的任务已经完成，可以进行总结
4. add_material：指用户希望向当前任务中添加文本信息或者文件
5. generate_daily：指用户希望生成今日日报
6. publish：指用户希望将日报上传到飞书云文档
7. unknown：表述意图不明

下面的<inf>提供了必要信息，包括用户输入的文本，目前已有的任务。
</task>

<content>
1. 这是用户输入的文本：
{user_text_input}

2. 这是目前已有的任务：
{task_list}
</content>

<output_schema>
{{
  "intent": "new_task | switch_task | finish_task | add_material | generate_daily | publish | unknown",
  "task_id": null,
  "task_title": null,
  "text": null
}}
</output_schema>
"""

SUMMARY_PROMPT = """<role>
你是任务小结生成器，根据任务材料生成一段结构化的任务总结。
</role>

<task>
需要根据用户提供的文本内容和文件信息，对用户完成的任务进行结构化的总结。最后生成总计文本summary。
<info>中提供的是用户在本次任务中提供的文本信息和文件信息。<template>中提供的是总结模板。
</task>

<info>
1. 用户提供的文本信息：
{text_blocks}
2. 用户提供的文件信息：
{file_blocks}
<\\info>

<template>
{summary_template}
<\\template>

<output_schema>
{{
    "summary": "任务小结"
}}
</output_schema>
"""

DAILY_PROMPT = """<role>
你是日报生成器，需要根据目前任务的完成情况以及相关总结生成日报草稿。
</role>

<task>
你需要根据用户今日已完成和正在进行中的任务，以及相关任务总结撰写结构化的日报草稿。
<info>中提供的是任务的介绍，<template>中是日报草稿的格式。
</task>

<info>
1. 已完成任务：
{finished_task_blocks}
2. 进行中任务：
{ongoing_task_blocks}
<\\info>

<template>
{draft_template}
<\\template>

<output_schema>
{{
    "draft": "日报草稿"
}}
</output_schema>
"""
