from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from pathlib import Path

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from config import Settings
from state import safe_month


def decrypt_lark_body(encrypt: str, encrypt_key: str) -> dict:
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    raw = base64.b64decode(encrypt)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    pad = padded[-1]
    text = padded[:-pad].decode("utf-8")
    return json.loads(text)


def unwrap_event(body: dict, settings: Settings) -> dict:
    if "encrypt" in body:
        if not settings.lark_encrypt_key:
            raise ValueError("LARK_ENCRYPT_KEY is required for encrypted events")
        body = decrypt_lark_body(body["encrypt"], settings.lark_encrypt_key)
    return body


def verify_token(body: dict, settings: Settings) -> None:
    token = body.get("token") or body.get("header", {}).get("token")
    if settings.lark_verification_token and token and token != settings.lark_verification_token:
        raise ValueError("invalid lark verification token")


def normalize_event(body: dict) -> dict:
    if {"user_id", "event_id", "message_id"}.issubset(body):
        return body

    header = body.get("header", {})
    event = body.get("event", {})
    message = event.get("message", {})
    sender_id = event.get("sender", {}).get("sender_id", {})
    message_type = message.get("message_type", "text")
    content = json.loads(message.get("content") or "{}")
    text = content.get("text", "")
    files: list[dict] = []
    if message_type in {"file", "image", "media"}:
        files.append(
            {
                "file_id": content.get("file_key") or content.get("image_key") or content.get("file_id"),
                "title": content.get("file_name") or content.get("name") or message_type,
            }
        )
    return {
        "user_id": sender_id.get("open_id") or sender_id.get("user_id"),
        "event_id": header.get("event_id"),
        "message_id": message.get("message_id"),
        "type": "file" if files and not text else "mixed" if files else "text",
        "text": text,
        "files": files,
        "created_at": header.get("create_time"),
    }


class LarkClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: str | None = None

    def tenant_token(self) -> str:
        if self._token:
            return self._token
        if not self.settings.lark_app_id or not self.settings.lark_app_secret:
            raise RuntimeError("LARK_APP_ID and LARK_APP_SECRET are required")
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.settings.lark_app_id, "app_secret": self.settings.lark_app_secret},
            )
            response.raise_for_status()
            data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(data)
        self._token = data["tenant_access_token"]
        return self._token

    def reply_text(self, message_id: str | None, text: str) -> None:
        if not self.settings.lark_enable_replies or not message_id:
            return
        headers = {"Authorization": f"Bearer {self.tenant_token()}"}
        payload = {"msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)}
        url = f"https://open.larksuite.com/open-apis/im/v1/messages/{message_id}/reply"
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()


def publish_with_cli(root: Path, month: str, state: dict, dry_run: bool = False) -> dict:
    month = safe_month(month)
    report = root / "reports" / f"{month}.md"
    if not report.exists():
        raise FileNotFoundError(f"report not found: {report}")
    doc = state.get("documents", {}).get(month, {}).get("doc")
    rel = "@" + report.resolve().relative_to(root.resolve()).as_posix()
    if doc:
        cmd = ["lark-cli", "docs", "+update", "--api-version", "v2", "--doc", doc, "--command", "overwrite", "--doc-format", "markdown", "--content", rel, "--format", "json", "--as", "user"]
    else:
        cmd = ["lark-cli", "docs", "+create", "--api-version", "v2", "--doc-format", "markdown", "--content", rel, "--parent-position", "my_library", "--format", "json", "--as", "user"]
    if dry_run:
        return {"dry_run": True, "command": subprocess.list2cmdline(cmd)}
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    payload = json.loads(result.stdout)
    document = payload.get("data", {}).get("document", {})
    state.setdefault("documents", {})[month] = {
        "doc": document.get("document_id") or document.get("token") or doc,
        "url": document.get("url"),
    }
    return payload
