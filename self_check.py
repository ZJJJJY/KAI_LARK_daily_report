from __future__ import annotations

import os
import tempfile

from fastapi.testclient import TestClient

os.environ["LLM_MODE"] = "mock"
os.environ["LARK_ENABLE_REPLIES"] = "false"

from app import app  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATA_ROOT"] = tmp
        client = TestClient(app)
        assert client.get("/health").json()["ok"] is True
        event = {
            "user_id": "u1",
            "event_id": "e1",
            "message_id": "m1",
            "type": "text",
            "text": "新任务：飞书日报 Bot",
            "files": [],
        }
        assert "已创建任务" in client.post("/simulate", json=event).json()["reply"]
        event |= {"event_id": "e2", "message_id": "m2", "text": "完成了 webhook 状态机"}
        assert "已补充" in client.post("/simulate", json=event).json()["reply"]
        event |= {"event_id": "e3", "message_id": "m3", "text": "这个任务完成了"}
        assert "已生成任务小结" in client.post("/simulate", json=event).json()["reply"]
        daily = client.post("/daily/generate", json={}).json()
        assert daily["ok"] and "今日完成" in daily["draft"]
    print("self-check passed")


if __name__ == "__main__":
    main()
