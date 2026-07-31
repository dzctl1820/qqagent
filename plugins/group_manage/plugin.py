from nonebot import on_notice, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
    MessageSegment,
)

from plugins.config_loader import get_group_config

welcome_notice = on_notice(priority=5, block=True)
keyword_matcher = on_message(priority=50, block=False)


@welcome_notice.handle()
async def handle_group_increase(bot: Bot, event: GroupIncreaseNoticeEvent):
    cfg = get_group_config()
    if not cfg.get("welcome_enabled", True):
        return
    user_id = event.user_id
    group_id = event.group_id
    at_seg = MessageSegment.at(user_id)
    welcome = f"{at_seg} {cfg.get('welcome', '欢迎加入本群！')}"
    await bot.send_group_msg(group_id=group_id, message=welcome)


@keyword_matcher.handle()
async def handle_keyword(bot: Bot, event: GroupMessageEvent):
    cfg = get_group_config()
    if not cfg.get("keyword_enabled", True):
        return
    text = event.get_plaintext().strip()
    keywords = cfg.get("keywords", {})
    for keyword, reply in keywords.items():
        if keyword in text:
            await keyword_matcher.send(MessageSegment.reply(event.message_id) + reply)
            return
