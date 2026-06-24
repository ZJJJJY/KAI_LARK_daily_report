from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_mode: str
    lark_app_id: str
    lark_app_secret: str
    lark_verification_token: str
    lark_encrypt_key: str
    lark_enable_replies: bool


def settings() -> Settings:
    return Settings(
        data_root=Path(os.getenv("DATA_ROOT", "./data")),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.llm.ustc.edu.cn/"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "deepseek-v4-pro"),
        llm_mode=os.getenv("LLM_MODE", "real"),
        lark_app_id=os.getenv("LARK_APP_ID", ""),
        lark_app_secret=os.getenv("LARK_APP_SECRET", ""),
        lark_verification_token=os.getenv("LARK_VERIFICATION_TOKEN", ""),
        lark_encrypt_key=os.getenv("LARK_ENCRYPT_KEY", ""),
        lark_enable_replies=os.getenv("LARK_ENABLE_REPLIES", "false").lower() == "true",
    )
