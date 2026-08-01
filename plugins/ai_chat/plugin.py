import asyncio
import random
import time
from collections import defaultdict, deque
from typing import Any

import httpx
from nonebot import on_message, logger
from nonebot.adapters.qq import (
    Bot,
    MessageEvent,
    MessageSegment,
)
from nonebot.rule import to_me

from plugins.admin.log_store import add_log
from plugins.config_loader import get_ai_config

# 每个用户在群内的上下文: {group_openid: {member_openid: deque([{role, content}])}}
_contexts: dict[str, dict[str, deque[dict[str, Any]]]] = defaultdict(lambda: defaultdict(deque))

# 频率限制：每群每 2 分钟最多 3 条
_rate_limit: dict[str, deque] = defaultdict(lambda: deque(maxlen=3))
_RATE_WINDOW = 120  # 秒

# 活跃时段限制：8:00 - 23:00
_ACTIVE_HOURS = set(range(8, 24))

ai_chat = on_message(rule=to_me(), priority=10, block=True)


def _check_rate(group_openid: str) -> bool:
    """检查群内回复频率，True=允许回复"""
    now = time.time()
    q = _rate_limit[group_openid]
    while q and now - q[0] > _RATE_WINDOW:
        q.popleft()
    if len(q) >= 3:
        return False
    q.append(now)
    return True


def _is_active_hours() -> bool:
    """检查当前是否在活跃时段内"""
    return time.localtime().tm_hour in _ACTIVE_HOURS


async def _human_delay():
    """随机延迟 1-2 秒"""
    await asyncio.sleep(random.uniform(1, 2))


def _build_messages(group_openid: str, member_openid: str, user_text: str) -> list[dict[str, str]]:
    cfg = get_ai_config()
    ctx = _contexts[group_openid][member_openid]
    messages = [{"role": "system", "content": cfg.get("system_prompt", "")}]
    messages.extend(list(ctx))
    messages.append({"role": "user", "content": user_text})
    return messages


def _update_context(group_openid: str, member_openid: str, user_text: str, reply_text: str):
    cfg = get_ai_config()
    ctx = _contexts[group_openid][member_openid]
    ctx.append({"role": "user", "content": user_text})
    ctx.append({"role": "assistant", "content": reply_text})
    max_items = cfg.get("context_rounds", 5) * 2
    while len(ctx) > max_items:
        ctx.popleft()


async def _call_llm(messages: list[dict[str, str]]) -> str:
    cfg = get_ai_config()
    headers = {
        "Authorization": f"Bearer {cfg.get('api_key', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.get("model", "deepseek-chat"),
        "messages": messages,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{cfg.get('api_base', 'https://api.deepseek.com/v1')}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


@ai_chat.handle()
async def handle_at_ai(bot: Bot, event: MessageEvent):
    """@机器人 或私聊时触发 AI 对话"""
    cfg = get_ai_config()
    if not cfg.get("enabled", True):
        return
    text = event.get_plaintext().strip()
    if not text:
        await ai_chat.finish(MessageSegment.text("在吗？有什么可以帮你的~"))

    # 群聊用 group_openid，私聊用 c2c_前缀 + user_openid
    group_openid = getattr(event, "group_openid", None) or f"c2c_{event.get_user_id()}"
    member_openid = event.get_user_id()
    if not _is_active_hours():
        return
    if not _check_rate(group_openid):
        add_log("warning", "ai_chat", f"会话{group_openid[:12]}... 频率限制，跳过回复")
        return
    await _human_delay()
    messages = _build_messages(group_openid, member_openid, text)

    try:
        reply = await _call_llm(messages)
        _update_context(group_openid, member_openid, text, reply)
        await ai_chat.send(MessageSegment.text(reply))
        add_log("success", "ai_chat", f"会话{group_openid[:12]}... 用户{member_openid[:8]}...: {text[:30]}", f"回复: {reply[:80]}")
    except Exception as e:
        logger.error(f"AI 对话失败: {e}")
        add_log("error", "ai_chat", f"AI 对话失败: {text[:30]}", str(e))
        try:
            await ai_chat.send(MessageSegment.text("抱歉，我暂时开小差了，稍后再试~"))
        except Exception:
            pass
