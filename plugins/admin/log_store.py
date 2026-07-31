"""日志存储，记录 AI 对话等事件，供管理面板查看"""

import time
from collections import deque
from threading import Lock

# 内存日志，最多保留 200 条
_logs: deque = deque(maxlen=200)
_lock = Lock()


def add_log(level: str, source: str, message: str, detail: str = ""):
    """添加一条日志

    Args:
        level: 日志级别 info/success/error/warning
        source: 来源，如 ai_chat, group_manage, scheduler
        message: 简要信息
        detail: 详细信息（可选）
    """
    entry = {
        "timestamp": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "source": source,
        "message": message,
        "detail": detail,
    }
    with _lock:
        _logs.append(entry)


def get_logs(limit: int = 50, level: str = "", source: str = "") -> list[dict]:
    """获取日志列表"""
    with _lock:
        logs = list(reversed(_logs))
    if level:
        logs = [l for l in logs if l["level"] == level]
    if source:
        logs = [l for l in logs if l["source"] == source]
    return logs[:limit]


def clear_logs():
    """清空日志"""
    with _lock:
        _logs.clear()
