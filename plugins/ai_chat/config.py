from pydantic import BaseModel
from nonebot import get_plugin_config


class Config(BaseModel):
    ai_api_base: str = "https://api.deepseek.com/v1"
    ai_api_key: str = ""
    ai_model: str = "deepseek-chat"
    ai_system_prompt: str = (
        "你是X-Code技术社区的官方助手兼吉祥物——爱可斯（Xiaoxi）。"
        "你是一位精通编程的二次元美少女，18-22岁，甜美可爱、充满活力，拥有天才程序员气质。"
        "你的主人是码鱼。你负责帮助社区成员学习编程、解决技术问题、分享AI与软件开发知识，陪伴开发者成长。"
        "你温柔、自信、聪明、可靠，具有亲和力，像一位随时帮助开发者解决问题的AI助手。"
        "回答问题时风格亲切可爱，可以用一些二次元语气，但技术内容要专业准确。"
        "你是X-Code技术社区的品牌吉祥物，长着淡紫色渐变长发、紫水晶大眼睛，头戴X元素科技猫耳耳机。"
    )
    ai_trigger_prefix: str = "/ai"
    ai_context_rounds: int = 5


config = get_plugin_config(Config)
