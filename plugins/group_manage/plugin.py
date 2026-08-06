from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
    MessageSegment,
)

from plugins.config_loader import get_group_config

# 入群欢迎限流：每个群 60 秒内最多发一次
_welcome_last_sent: dict[int, float] = {}
_WELCOME_COOLDOWN = 60.0

keyword_matcher = on_message(priority=50, block=False)


@keyword_matcher.handle()
async def handle_keyword(bot: Bot, event: GroupMessageEvent):
    cfg = get_group_config()
    if not cfg.get("keyword_enabled", True):
        return
    text = event.get_plaintext().strip()
    keywords = cfg.get("keywords", {})
    for keyword, reply in keywords.items():
        if keyword in text:
            await keyword_matcher.send(MessageSegment.text(reply))
            return


welcome_matcher = on_notice(priority=10, block=False)


@welcome_matcher.handle()
async def handle_group_increase(bot: Bot, event: GroupIncreaseNoticeEvent):
    cfg = get_group_config()
    if not cfg.get("welcome_enabled", True):
        return
    # 限流：同一群 60 秒内只发一次
    import time
    now = time.time()
    last = _welcome_last_sent.get(event.group_id, 0)
    if now - last < _WELCOME_COOLDOWN:
        return
    _welcome_last_sent[event.group_id] = now
    welcome = cfg.get("welcome", "欢迎加入本群！")
    await bot.call_api(
        "send_group_msg",
        group_id=event.group_id,
        message=MessageSegment.text(welcome),
    )
