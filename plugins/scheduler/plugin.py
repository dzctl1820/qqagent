from typing import Any

from nonebot import get_bot, get_driver, logger
from nonebot.plugin import PluginMetadata
from nonebot_plugin_apscheduler import scheduler

from plugins.config_loader import get_scheduler_config

__plugin_meta__ = PluginMetadata(
    name="定时任务插件",
    description="定时推送消息到QQ群",
    usage="通过管理面板配置定时任务",
    type="application",
    config=None,
)


async def _send_scheduled_message(group_openid: str, message: str):
    try:
        bot = get_bot()
        await bot.call_api(
            "send_group_message",
            group_openid=group_openid,
            message_type=0,
            content=message,
        )
        logger.info(f"定时消息已发送到群 {group_openid[:8]}...")
    except Exception as e:
        logger.error(f"定时消息发送失败: {e}")


def _register_jobs():
    # 清除旧任务
    for job in scheduler.get_jobs():
        if job.id.startswith("scheduled_msg_"):
            scheduler.remove_job(job.id)
    cfg = get_scheduler_config()
    jobs = cfg.get("jobs", [])
    for idx, job in enumerate(jobs):
        group_openid = job.get("group_openid") or job.get("group_id", "")
        hour = job.get("hour", 0)
        minute = job.get("minute", 0)
        message = job.get("message", "")

        if not group_openid or not message:
            logger.warning(f"定时任务 #{idx} 配置不完整，跳过")
            continue

        job_id = f"scheduled_msg_{group_openid[:8]}_{hour}_{minute}_{idx}"

        scheduler.add_job(
            _send_scheduled_message,
            "cron",
            hour=hour,
            minute=minute,
            id=job_id,
            args=[group_openid, message],
            replace_existing=True,
        )
        logger.info(f"已注册定时任务: 群{group_openid[:8]}... 每日 {hour:02d}:{minute:02d}")


def reload_jobs():
    """供 admin 插件调用，重新加载定时任务"""
    _register_jobs()


@get_driver().on_startup
async def _startup():
    _register_jobs()
