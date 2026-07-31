from nonebot import get_driver, logger
from nonebot.plugin import PluginMetadata

from .api import register_admin_routes

__plugin_meta__ = PluginMetadata(
    name="管理面板",
    description="Web 可视化管理面板，控制 AI、群管理、定时任务等配置",
    usage="访问 /admin 打开管理面板",
    type="application",
    config=None,
)

driver = get_driver()

# 在插件加载时直接注册路由到 FastAPI app
app = driver.server_app
register_admin_routes(app)
logger.info("管理面板已启动: http://localhost:8080/admin")
