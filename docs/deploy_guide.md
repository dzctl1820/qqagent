# QQ Bot 部署运维手册

## 项目架构

| 容器 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| qqagent-napcat | mlikiowa/napcat-docker:latest | 3001, 6099 | NapCat 协议端，处理 QQ 登录和消息收发 |
| qqagent-bot | qqagent-bot (本地构建) | 8080 | NoneBot2 机器人，运行插件逻辑 |

连接方式：NapCat 通过反向 WebSocket 连接 NoneBot（`ws://bot:8080/onebot/v11/ws`）

## 首次部署

### 1. 拉取代码

```bash
cd /www/wwwroot/qqagent
git pull origin main
```

### 2. 启动容器

```bash
docker compose up -d --build
```

### 3. NapCat 扫码登录

```bash
# 获取 WebUI token
docker compose logs napcat 2>&1 | grep "WebUi Token" | tail -1
```

浏览器打开 `http://服务器IP:6099/webui?token=xxx`，扫码登录 QQ。

### 4. 配置反向 WebSocket

在 NapCat WebUI 中：

1. **网络配置** → **新建** → **WebSocket 客户端**
2. 填写：
   - **URL**: `ws://bot:8080/onebot/v11/ws`
   - **消息格式**: `String`
   - **Token**: 留空
   - **心跳间隔**: `30000`
   - **重连间隔**: `5000`
3. **启用** → **保存**

### 5. 验证连接

```bash
docker compose logs bot 2>&1 | grep "connected"
```

看到 `OneBot V11 | Bot 3381615312 connected` 即成功。

## 日常运维命令

### 更新代码并重建

```bash
cd /www/wwwroot/qqagent
git pull origin main
docker compose up -d --build bot
```

### 代码有冲突时强制覆盖

```bash
git fetch origin
git reset --hard origin/main
docker compose up -d --build bot
```

### 查看日志

```bash
# bot 实时日志
docker compose logs -f bot

# bot 最近 30 行
docker compose logs bot 2>&1 | tail -30

# napcat 实时日志
docker compose logs -f napcat

# napcat 最近 20 行
docker compose logs napcat 2>&1 | tail -20

# 查看表情包加载状态
docker compose logs bot 2>&1 | grep "表情包"

# 查看连接状态
docker compose logs bot 2>&1 | grep "connected"
```

### 容器管理

```bash
# 查看容器状态
docker compose ps

# 重启 bot
docker compose restart bot

# 重启 napcat
docker compose restart napcat

# 进入 bot 容器
docker exec -it qqagent-bot bash

# 查看 bot 容器内文件
docker exec qqagent-bot ls -la /app/data/media/emojis/
```

### 清理旧容器

```bash
# 删除旧的 lagrange 容器
docker rm -f qqagent-lagrange

# 启动并清理孤儿容器
docker compose up -d --remove-orphans
```

## NapCat WebUI

```bash
# 查看 WebUI token
docker compose logs napcat 2>&1 | grep "WebUi Token" | tail -1

# 查看 WebUI 完整 URL
docker compose logs napcat 2>&1 | grep "WebUi User Panel Url" | tail -1
```

浏览器打开 `http://服务器IP:6099/webui?token=xxx`

## NapCat 掉线处理

NapCat 掉线后需要重新扫码登录：

```bash
# 重启 napcat 生成新二维码
docker compose restart napcat
sleep 5

# 获取 WebUI URL
docker compose logs napcat 2>&1 | grep "WebUi User Panel Url" | tail -1
```

浏览器打开 URL，在 WebUI 中扫码登录。登录后 NapCat 会自动重连 bot。

## 表情包管理

### 目录结构

```
data/media/emojis/
├── happy/       开心、高兴
├── laugh/       笑死、爆笑
├── shy/         害羞、脸红
├── sad/         难过、伤心
├── angry/       生气、怒
├── surprised/   惊讶、震惊
├── love/        喜欢、心动
├── think/       思考、纠结
├── ok/          好的、收到
└── sleepy/      困了、晚安
```

支持格式：png、jpg、jpeg、gif、webp

### 添加表情包

```bash
# 创建目录（首次）
mkdir -p /www/wwwroot/qqagent/data/media/emojis/{happy,laugh,shy,sad,angry,surprised,love,think,ok,sleepy}

# 上传表情包到对应情绪目录
# 使用 rz 或 scp 上传
rz  # 上传到当前目录后移动到对应子目录

# 确认文件
ls -R /www/wwwroot/qqagent/data/media/emojis/
```

### 情绪关键词映射

| 情绪 | 关键词 |
|------|--------|
| happy | 开心、高兴、哈哈、嘻嘻、快乐、好玩、有趣、耶、太棒了、好耶 |
| laugh | 笑死、爆笑、草、乐、绷不住、笑、哈哈哈 |
| shy | 害羞、脸红、不好意思、羞、捂脸 |
| sad | 难过、伤心、呜呜、哭、悲伤、叹气、唉 |
| angry | 生气、气死、怒、哼、可恶 |
| surprised | 惊讶、天哪、哇、不会吧、震惊、居然 |
| love | 喜欢、爱你、心动、么么、抱抱、温暖 |
| think | 思考、想想、嗯、让我看看、琢磨、纠结 |
| ok | 好的、没问题、收到、了解、明白 |
| sleepy | 困了、睡觉、晚安、累、休息 |

AI 回复匹配到关键词时发对应情绪表情包；未匹配到时有 30% 概率随机发一张。

## 配置文件说明

### .env

| 变量 | 说明 | 示例 |
|------|------|------|
| DRIVER | NoneBot 驱动 | ~fastapi+~httpx+~websockets |
| HOST | 监听地址 | 0.0.0.0 |
| PORT | 监听端口 | 8080 |
| AI_API_BASE | AI API 地址 | https://api.deepseek.com/v1 |
| AI_API_KEY | AI API Key | sk-xxx |
| AI_MODEL | AI 模型 | deepseek-chat |
| AI_SYSTEM_PROMPT | AI 系统提示词 | 你是爱可斯... |
| AI_TRIGGER_PREFIX | AI 触发前缀 | /ai |
| AI_CONTEXT_ROUNDS | 上下文轮数 | 5 |
| GROUP_WELCOME | 入群欢迎语 | 欢迎加入本群！ |
| GROUP_KEYWORDS | 关键词自动回复 | JSON 格式 |
| SCHEDULER_JOBS | 定时任务 | JSON 格式 |

### docker-compose.yml

- napcat 服务：QQ 协议端，暴露 3001（WS）和 6099（WebUI）端口
- bot 服务：NoneBot2 机器人，暴露 8080 端口，挂载 `./data:/app/data`
- 两容器通过 `bot-net` 网络互通，可用容器名互相访问

### NapCat 配置文件

- `napcat/config/onebot11_ws.json`：反向 WebSocket 客户端配置
- `napcat/data/`：QQ 登录态持久化目录

## 管理面板

访问 `http://服务器IP:8080/admin` 可管理：

- AI 配置（系统提示词、模型、API Key 等）
- 群管理配置（欢迎语、关键词）
- 定时任务配置
- 日志查看

## 故障排查

### Bot 收不到消息

1. 检查 NapCat 是否在线：`docker compose ps`
2. 检查连接状态：`docker compose logs bot 2>&1 | grep "connected"`
3. 如果没连上，检查 NapCat WebUI 中的反向 WS 配置是否启用
4. 如果 NapCat 掉线，重启并重新扫码

### AI 不回复

1. 检查是否在活跃时段（8:00-23:00）
2. 检查频率限制（每群每 2 分钟最多 3 条）
3. 查看 bot 日志：`docker compose logs bot 2>&1 | tail -30`

### 表情包不发送

1. 检查日志中表情包加载数量：`docker compose logs bot 2>&1 | grep "表情包"`
2. 确认容器内有文件：`docker exec qqagent-bot ls -R /app/data/media/emojis/`
3. 如果为 0，检查宿主机 `data/media/emojis/` 目录是否有图片

### 消息显示"暂不可查看"

NapCat WebUI 中消息格式需设置为 `String`（不是 `Array`）。
