from pydantic import BaseModel
from nonebot import get_plugin_config


class Config(BaseModel):
    ai_api_base: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_system_prompt: str = "你是一个友好的QQ群聊AI助手，回答简洁有趣。"
    ai_trigger_prefix: str = "/ai"
    ai_context_rounds: int = 5


config = get_plugin_config(Config)
