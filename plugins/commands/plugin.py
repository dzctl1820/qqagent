import time
from datetime import datetime

from nonebot import on_command
from nonebot.adapters.qq import (
    Bot,
    MessageEvent,
    MessageSegment,
)

help_cmd = on_command("help", priority=5, block=True)
status_cmd = on_command("status", priority=5, block=True)
time_cmd = on_command("time", priority=5, block=True)
clear_cmd = on_command("clear", priority=5, block=True)

BOT_START_TIME = time.time()


@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    help_text = (
        "📋 可用指令列表\n"
        "━━━━━━━━━━━━━\n"
        "/help - 显示本帮助\n"
        "/status - 查看机器人状态\n"
        "/time - 查看当前时间\n"
        "/clear - 清除你的AI对话上下文\n"
        "@机器人 <内容> - 直接与AI对话\n"
        "━━━━━━━━━━━━━\n"
        "更多功能开发中..."
    )
    await help_cmd.send(MessageSegment.text(help_text))


@status_cmd.handle()
async def handle_status(bot: Bot, event: MessageEvent):
    uptime = int(time.time() - BOT_START_TIME)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    uptime_str = f"{h}h {m}m {s}s"
    status_text = (
        f"🤖 机器人状态\n"
        f"运行时长: {uptime_str}\n"
        f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"状态: ✅ 正常运行"
    )
    await status_cmd.send(MessageSegment.text(status_text))


@time_cmd.handle()
async def handle_time(bot: Bot, event: MessageEvent):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await time_cmd.send(MessageSegment.text(f"🕐 当前时间: {now}"))


@clear_cmd.handle()
async def handle_clear(bot: Bot, event: MessageEvent):
    from plugins.ai_chat.plugin import _contexts
    group_openid = getattr(event, "group_openid", None) or f"c2c_{event.get_user_id()}"
    member_openid = event.get_user_id()
    if group_openid in _contexts and member_openid in _contexts[group_openid]:
        _contexts[group_openid][member_openid].clear()
    await clear_cmd.send(MessageSegment.text("✅ AI对话上下文已清除"))
