# KAI Lark Daily Report

本目录是飞书日报 Bot 的本地 Webhook MVP。

## 运行

```powershell
uv sync
$env:NO_PROXY="api.llm.ustc.edu.cn,open.larksuite.com"
$env:LLM_BASE_URL="https://api.llm.ustc.edu.cn/"
$env:LLM_API_KEY="<your key>"
$env:LLM_MODEL="deepseek-v4-pro"
$env:LARK_APP_ID="<app id>"
$env:LARK_APP_SECRET="<app secret>"
$env:LARK_VERIFICATION_TOKEN="<verification token>"
$env:LARK_ENCRYPT_KEY="<encrypt key>"
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

飞书事件回调地址：

```text
https://chief-hatchet-sash.ngrok-free.dev/lark/events
```

## 接口

- `POST /lark/events`：飞书事件入口，支持 URL verification、明文事件和加密事件。
- `POST /simulate`：本地模拟自定义 payload。
- `POST /daily/generate`：手动生成日报。
- `POST /daily/publish`：用 `lark-cli docs +create/+update` 发布月度文档。
- `GET /state`：查看本地状态。

## 自检

```powershell
uv run python self_check.py
```

## MVP 简化

- 单用户。
- 文件消息只保存元数据，不下载文件内容。
- 审核流程先跳过，任务完成直接生成小结，日报生成直接保存草稿。
- 发布沿用本机 `lark-cli`，需要先完成 `lark-cli` 登录和文档权限配置。
