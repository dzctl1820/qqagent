import sys
from typing import Any


def _env_ai_config() -> dict[str, Any]:
    from plugins.ai_chat.config import config as env_config
    return {
        "api_base": env_config.ai_api_base,
        "api_key": env_config.ai_api_key,
        "model": env_config.ai_model,
        "system_prompt": env_config.ai_system_prompt,
        "trigger_prefix": env_config.ai_trigger_prefix,
        "context_rounds": env_config.ai_context_rounds,
        "enabled": True,
    }


def get_ai_config() -> dict[str, Any]:
    """从 admin 配置存储读取 AI 配置，关键字段为空时回退到 .env"""
    env = _env_ai_config()
    try:
        from plugins.admin.db import get_section
        admin = get_section("ai")
        # admin 配置中 api_key 为空时用 .env 的值
        if not admin.get("api_key"):
            admin["api_key"] = env["api_key"]
        if not admin.get("api_base"):
            admin["api_base"] = env["api_base"]
        if not admin.get("model"):
            admin["model"] = env["model"]
        return admin
    except Exception:
        return env


def get_group_config() -> dict[str, Any]:
    """从 admin 配置存储读取群管理配置，回退到 .env"""
    try:
        from plugins.admin.db import get_section
        return get_section("group")
    except Exception:
        import json
        from nonebot import get_plugin_config
        from pydantic import BaseModel

        class EnvConfig(BaseModel):
            group_welcome: str = "欢迎加入本群！"
            group_keywords: str = "{}"

        env = get_plugin_config(EnvConfig)
        return {
            "welcome": env.group_welcome,
            "keywords": json.loads(env.group_keywords),
            "keyword_enabled": True,
            "welcome_enabled": True,
        }


def get_scheduler_config() -> dict[str, Any]:
    """从 admin 配置存储读取定时任务配置"""
    try:
        from plugins.admin.db import get_section
        return get_section("scheduler")
    except Exception:
        return {"jobs": []}
