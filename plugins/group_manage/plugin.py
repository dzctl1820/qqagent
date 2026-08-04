from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageSegment,
)

from plugins.config_loader import get_group_config

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
