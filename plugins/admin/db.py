import json
import os
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(os.environ.get("BOT_DATA_DIR", "./data"))
_CONFIG_FILE = _CONFIG_DIR / "admin_config.json"

_DEFAULT_CONFIG: dict[str, Any] = {
    "ai": {
        "api_base": "",
        "api_key": "",
        "model": "",
        "system_prompt": "",
        "trigger_prefix": "",
        "context_rounds": 0,
        "enabled": True,
    },
    "group": {
        "welcome": "欢迎加入本群！请阅读群公告~",
        "keywords": {},
        "keyword_enabled": True,
        "welcome_enabled": True,
    },
    "scheduler": {
        "jobs": [],
    },
    "admin": {
        "token": "admin123",
    },
}


def _ensure_dir():
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    _ensure_dir()
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        merged = _deep_merge(_DEFAULT_CONFIG, saved)
        return merged
    save_config(_DEFAULT_CONFIG)
    return _DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]):
    _ensure_dir()
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def update_section(section: str, data: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    if section not in config:
        config[section] = {}
    config[section].update(data)
    save_config(config)
    return config[section]


def get_section(section: str) -> dict[str, Any]:
    config = load_config()
    return config.get(section, {})


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
