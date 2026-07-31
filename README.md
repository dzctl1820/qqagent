# QQAgent - QQ 群聊机器人

基于 **NapCat + NoneBot2** 的 QQ 群聊机器人，支持 AI 对话、指令响应、群管理和定时任务。

## 架构

```
QQ 客户端 (NTQQ)
    ↕
NapCat (OneBot 11 协议适配)
    ↕ 反向 WebSocket
NoneBot2 (本项目)
    ├── ai_chat      AI 对话插件
    ├── commands     指令响应插件
    ├── group_manage 群管理插件
    └── scheduler    定时任务插件
```

## 部署方式

### 方式一：Docker Compose 部署到云服务器（推荐）

> 适合：有一台云服务器（VPS），不想电脑一直开着。

#### 1. 准备云服务器

- 任意 Linux VPS（2核2G 即可），推荐腾讯云/阿里云轻量服务器
- 安装 Docker + Docker Compose：

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker
```

#### 2. 上传项目到服务器

```bash
# 方式一：Git 克隆
git clone <your-repo-url> /opt/qqagent
cd /opt/qqagent

# 方式二：SCP 上传
scp -r ./qqagent root@your-server-ip:/opt/qqagent
```

#### 3. 配置环境变量

```bash
cp .env.example .env
vi .env
```

填入你的 AI API Key、群号等配置。

#### 4. 一键启动

```bash
docker compose up -d --build
```

#### 5. 扫码登录 QQ

```bash
# 查看 NapCat 日志获取二维码
docker compose logs -f napcat
```

或访问 `http://your-server-ip:3000` 通过 WebUI 扫码登录。

#### 6. 配置 NapCat 反向 WebSocket

登录后在 NapCat WebUI (`http://your-server-ip:6099`) 中添加网络配置：

- **类型**: 反向 WebSocket 客户端
- **地址**: `ws://bot:8080/onebot/v11/ws`（Docker 内部网络，用容器名 `bot`）
- **心跳**: 30s

#### 7. 验证

```bash
# 查看机器人日志
docker compose logs -f bot
```

看到 `OneBot V11 | Bot xxxx Connected` 即表示成功。

#### 常用运维命令

```bash
docker compose restart bot      # 重启机器人
docker compose restart napcat   # 重启 NapCat
docker compose down             # 停止所有服务
docker compose up -d            # 启动所有服务
docker compose logs -f          # 查看所有日志
docker compose pull && docker compose up -d  # 更新 NapCat 镜像
```

> **安全建议**: 在云服务器防火墙/安全组中，只开放需要的端口（3000、6099 用于首次登录，之后可关闭），8080 端口不需要对外开放（Docker 内部通信）。

---

### 方式二：本地运行（开发调试用）

> 适合：本地开发调试，需要电脑保持开机。

#### 1. 安装 NapCat

```bash
docker run -d --name napcat \
  -p 3000:3000 \
  -p 6099:6099 \
  --restart=always \
  mlikiowa/napcat-docker:latest
```

或参考 [NapCat 官方文档](https://napneko.github.io/) 本地安装。

访问 `http://localhost:3000` 扫码登录 QQ。

#### 2. 配置 NapCat 反向 WebSocket

在 NapCat WebUI 中添加网络配置：

- **类型**: 反向 WebSocket 客户端
- **地址**: `ws://127.0.0.1:8080/onebot/v11/ws`
- **心跳**: 30s

#### 3. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

#### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入配置
```

> **AI API 说明**: 支持任何 OpenAI 兼容 API，包括 DeepSeek、通义千问等，只需修改 `AI_API_BASE` 和 `AI_MODEL`。

#### 5. 启动

```bash
python bot.py
```

## 功能说明

### AI 对话

- **@机器人 + 消息**: 直接与 AI 对话
- **`/ai <内容>`**: 通过前缀触发 AI 对话
- **`/clear`**: 清除你的 AI 对话上下文
- 每个用户在群内独立维护上下文，默认记忆 5 轮对话

### 指令列表

| 指令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/status` | 查看机器人运行状态 |
| `/time` | 查看当前时间 |
| `/clear` | 清除 AI 对话上下文 |
| `/ai <内容>` | 与 AI 对话 |

### 群管理

- **入群欢迎**: 新成员入群自动发送欢迎语
- **关键词回复**: 配置关键词和对应回复，消息中包含关键词时自动回复

### 定时任务

通过管理面板或配置文件添加定时推送任务，支持多个群、多个时间段。

### 管理面板

机器人内置 Web 可视化管理面板，无需修改代码即可动态调整所有配置：

- **访问地址**: `http://your-server-ip:8080/admin`
- **默认密钥**: `admin123`（首次登录后请及时修改）

#### 面板功能

| 功能 | 说明 |
|------|------|
| **AI 助手配置** | 修改 API 地址、模型、Key、系统提示词、触发前缀、记忆轮数，一键开关 AI 对话 |
| **群管理配置** | 编辑入群欢迎语，添加/删除关键词自动回复，独立开关欢迎和关键词功能 |
| **定时任务管理** | 添加/删除定时推送任务，指定群号、时间、消息内容，保存后立即生效 |
| **运行状态** | 查看机器人运行时长和各功能启用状态 |

#### 配置存储

管理面板的配置持久化在 `data/admin_config.json`，所有插件优先读取此文件。`.env` 中的配置仅作为首次启动的默认值。

#### 修改管理密钥

编辑 `data/admin_config.json` 中的 `admin.token` 字段，或直接在服务器上：

```bash
# Docker 部署
docker compose exec bot sh -c "echo '{\"admin\":{\"token\":\"your-new-token\"}}' > data/admin_config.json"
docker compose restart bot
```

## 项目结构

```
qqagent/
├── bot.py                      # 入口文件
├── .env.example                # 配置模板（复制为 .env 使用）
├── pyproject.toml              # 依赖管理
├── Dockerfile                  # 机器人 Docker 镜像
├── docker-compose.yml          # 一键部署（bot + napcat）
├── data/                       # 运行时数据（自动创建）
│   └── admin_config.json       # 管理面板配置（持久化）
└── plugins/
    ├── config_loader.py        # 统一配置加载器
    ├── admin/                  # 管理面板插件
    │   ├── db.py               # 配置存储层
    │   ├── api.py              # FastAPI API 路由
    │   ├── plugin.py           # 插件入口
    │   └── static/index.html   # Web UI 管理界面
    ├── ai_chat/                # AI 对话插件
    │   ├── config.py           # 插件配置（.env 回退）
    │   └── plugin.py           # 插件逻辑
    ├── commands/               # 指令响应插件
    │   └── plugin.py
    ├── group_manage/           # 群管理插件
    │   └── plugin.py
    └── scheduler/              # 定时任务插件
        └── plugin.py
```

## 扩展开发

### 添加新插件

1. 在 `plugins/` 下创建新目录
2. 创建 `__init__.py` 和 `plugin.py`
3. 在 `pyproject.toml` 的 `plugins` 列表中注册

### 示例：天气查询插件

```python
# plugins/weather/plugin.py
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment

weather_cmd = on_command("天气", priority=5, block=True)

@weather_cmd.handle()
async def handle_weather(bot: Bot, event: GroupMessageEvent):
    await weather_cmd.send(MessageSegment.reply(event.message_id) + "天气功能开发中...")
```

## 常见问题

**Q: NapCat 连接不上？**
- 确认 NapCat 已登录 QQ
- 检查反向 WebSocket 地址是否正确
- 确认端口未被占用

**Q: AI 对话无响应？**
- 通过管理面板检查 AI 配置是否正确（`http://your-ip:8080/admin`）
- 查看日志是否有 API 调用错误
- 确认 API 地址可访问

**Q: 如何更换 AI 模型？**
- 在管理面板「AI 助手」页面修改 API 地址、模型、Key
- 或编辑 `data/admin_config.json`
- 支持 OpenAI / DeepSeek / 通义千问等兼容 API

**Q: 管理面板打不开？**
- 确认机器人已启动且端口 8080 可访问
- Docker 部署时确保 8080 端口已映射
- 检查防火墙/安全组是否放行

## 技术栈

- [NoneBot2](https://nonebot.dev/) - Python 异步机器人框架
- [NapCat](https://napneko.github.io/) - OneBot 11 协议实现
- [OneBot V11 Adapter](https://onebot.adapters.nonebot.dev/) - 协议适配器
- [APScheduler](https://apscheduler.readthedocs.io/) - 定时任务调度
- [Tailwind CSS](https://tailwindcss.com/) + [Alpine.js](https://alpinejs.dev/) - 管理面板前端
