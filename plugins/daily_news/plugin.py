import asyncio
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from nonebot import get_bot, get_driver, logger, on_command
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.plugin import PluginMetadata
from nonebot_plugin_apscheduler import scheduler

from plugins.config_loader import get_ai_config
from plugins.admin.log_store import add_log

__plugin_meta__ = PluginMetadata(
    name="每日时事日报",
    description="每天中午12点自动发送编程/AI时事日报到群",
    usage="自动运行，也可用 /日报 手动触发",
    type="application",
    config=None,
)

# 东八区时区
_TZ_CN = timezone(timedelta(hours=8))

# 目标群列表（从环境变量读取，逗号分隔）
_DAILY_NEWS_GROUPS: list[int] = []
_raw = os.getenv("DAILY_NEWS_GROUPS", "")
if _raw:
    _DAILY_NEWS_GROUPS = [int(g.strip()) for g in _raw.split(",") if g.strip()]

# 新闻源：IT之家热榜、36kr快讯、机器之心、Hacker News
_NEWS_SOURCES = [
    {
        "url": "https://www.ithome.com/rss/",
        "type": "rss",
    },
    {
        "url": "https://news.ycombinator.com/rss",
        "type": "rss",
    },
    {
        "url": "https://www.chinaz.com/rss/ai.xml",
        "type": "rss",
    },
]


def _parse_rss_items(xml_text: str, limit: int = 20) -> list[dict[str, str]]:
    """从 RSS XML 中提取标题、链接和发布日期"""
    items = []
    pattern = r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?(?:<pubDate>(.*?)</pubDate>)?.*?</item>"
    for match in re.finditer(pattern, xml_text, re.DOTALL | re.IGNORECASE):
        title = match.group(1).strip()
        link = match.group(2).strip()
        pub_date = match.group(3) or ""
        # 去掉 CDATA
        title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)
        link = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", link)
        if title and link:
            items.append({"title": title, "link": link, "date": pub_date.strip()})
        if len(items) >= limit:
            break
    return items


async def _fetch_news() -> list[dict[str, str]]:
    """从多个 RSS 源抓取最新新闻"""
    all_items: list[dict[str, str]] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
        for source in _NEWS_SOURCES:
            url = source["url"]
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                items = _parse_rss_items(resp.text, limit=15)
                all_items.extend(items)
                logger.info(f"RSS {url} 获取到 {len(items)} 条")
            except Exception as e:
                logger.warning(f"RSS 获取失败 {url}: {e}")

    # 去重
    seen = set()
    unique = []
    for item in all_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    return unique[:30]


def _filter_tech_news(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """过滤出与编程/AI/科技相关的新闻"""
    keywords = [
        "AI", "人工智能", "大模型", "GPT", "LLM", "机器学习", "深度学习",
        "编程", "代码", "程序员", "开发者", "软件", "GitHub", "开源",
        "Python", "Java", "JavaScript", "Rust", "Go语言", "C++",
        "芯片", "GPU", "算力", "云计算", "服务器", "数据库",
        "科技", "互联网", "腾讯", "阿里", "字节", "百度", "华为",
        "微软", "谷歌", "Google", "Apple", "苹果", "Meta", "OpenAI",
        "Claude", "DeepSeek", "智能", "自动化", "机器人",
    ]
    filtered = []
    for item in items:
        title = item["title"]
        if any(kw.lower() in title.lower() for kw in keywords):
            filtered.append(item)
    return filtered


async def _generate_daily_report(news_items: list[dict[str, str]]) -> str:
    """用 AI 生成日报"""
    cfg = get_ai_config()

    # 准备新闻标题列表
    titles = "\n".join(f"{i+1}. {item['title']}" for i, item in enumerate(news_items[:20]))

    now = datetime.now(_TZ_CN).strftime("%Y年%m月%d日")
    system_prompt = cfg.get("system_prompt", "")
    user_prompt = f"""今天是{now}。以下是最新的科技新闻标题列表：

{titles}

请从中挑选10条最有价值、与编程/AI/科技最相关的新闻，整理成一份详细的日报。格式要求：

📰 爱可斯的每日科技日报 | {now}

1. 【标题】两到三句话详细说明新闻内容和意义
2. 【标题】两到三句话详细说明新闻内容和意义
...（共10条）

要求：
- 每条新闻用两到三句话详细概括核心内容和影响，不要只有一句话
- 保持专业但语气活泼可爱，符合爱可斯的人设
- 最后加一句简短的总结或鼓励语
- 不要加链接
- 不要使用任何Markdown格式（不要用**、*、#、`等符号），用纯文本和emoji排版
- 用序号和换行来组织内容，不要用Markdown标题或加粗"""

    headers = {
        "Authorization": f"Bearer {cfg.get('api_key', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.get("model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 2048,
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


async def _send_daily_news(group_id: int):
    """抓取新闻并发送日报到指定群"""
    try:
        logger.info(f"开始生成日报，目标群: {group_id}")
        news = await _fetch_news()
        if not news:
            logger.warning("未获取到任何新闻")
            return

        tech_news = _filter_tech_news(news)
        if not tech_news:
            tech_news = news[:10]
            logger.info("未过滤到科技新闻，使用全部新闻")

        report = await _generate_daily_report(tech_news)
        bot = get_bot()
        await bot.call_api("send_group_msg", group_id=group_id, message=report)
        add_log("success", "daily_news", f"日报已发送到群{group_id}", report[:100])
        logger.info(f"日报已发送到群 {group_id}")
    except Exception as e:
        logger.error(f"日报发送失败: {e}")
        add_log("error", "daily_news", f"日报发送失败", str(e))


async def _daily_news_task():
    """定时任务：向所有配置的群发送日报"""
    if not _DAILY_NEWS_GROUPS:
        logger.warning("DAILY_NEWS_GROUPS 未配置，跳过日报发送")
        return
    for group_id in _DAILY_NEWS_GROUPS:
        await _send_daily_news(group_id)
        await asyncio.sleep(2)


def _register_daily_news_job():
    """注册每天中午12点（东八区）的定时任务"""
    for job in scheduler.get_jobs():
        if job.id == "daily_news":
            scheduler.remove_job(job.id)

    # cron 使用 UTC 时间，东八区 12:00 = UTC 04:00
    scheduler.add_job(
        _daily_news_task,
        "cron",
        hour=4,
        minute=0,
        timezone="UTC",
        id="daily_news",
        replace_existing=True,
    )
    logger.info("每日时事日报定时任务已注册: 每天北京时间 12:00")


@get_driver().on_startup
async def _startup():
    _register_daily_news_job()


# 手动触发命令
daily_news_cmd = on_command("日报", priority=5, block=True)


@daily_news_cmd.handle()
async def handle_daily_news():
    """手动触发日报发送"""
    await daily_news_cmd.send(MessageSegment.text("正在收集最新科技新闻，请稍等~"))
    try:
        news = await _fetch_news()
        if not news:
            await daily_news_cmd.finish(MessageSegment.text("暂时获取不到新闻，稍后再试~"))
            return
        tech_news = _filter_tech_news(news)
        if not tech_news:
            tech_news = news[:10]
        report = await _generate_daily_report(tech_news)
        await daily_news_cmd.finish(MessageSegment.text(report))
    except Exception as e:
        logger.error(f"手动日报生成失败: {e}")
        await daily_news_cmd.finish(MessageSegment.text("日报生成失败了，稍后再试~"))
