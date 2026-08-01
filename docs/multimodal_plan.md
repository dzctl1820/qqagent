# QQAgent 多模态功能实现方案

> 目标：在现有 QQ 群聊机器人（NapCat + NoneBot2）基础上，新增**图像识别**、**图像生成**、**语音生成**三大 AI 功能。
> 本文档基于当前项目代码分析，给出可落地的分层实现方案。

---

## 一、现状分析

### 1.1 项目架构

```
QQ 客户端 (NTQQ)
    ↕
NapCat (OneBot 11 协议适配)
    ↕ 反向 WebSocket
NoneBot2 (本项目, Python asyncio)
    ├── ai_chat       AI 对话插件（LLM 文本对话）
    ├── commands      指令响应插件
    ├── group_manage  群管理插件
    ├── scheduler     定时任务插件
    └── admin         Web 管理面板 (FastAPI + index.html)
        └── db.py     配置持久化 (data/admin_config.json)
    └── config_loader.py  统一配置加载（admin 优先，.env 回退）
```

### 1.2 与本次功能强相关的现有实现

| 关注点 | 现状 | 影响 |
|--------|------|------|
| **AI 对话入口** | `plugins/ai_chat/plugin.py`，`@机器人` + `/ai 前缀` 两个 `on_message` 触发，`_build_messages()` 组装 text-only 消息 | 图像识别需在此处改为**多模态消息**结构 |
| **API 调用** | `_call_llm()` 仅请求 `POST {api_base}/chat/completions`，payload 为纯文本 `messages` | 需扩展支持 `content` 数组（含 `image_url`），并新增图像生成、语音生成两个独立调用器 |
| **图片接收** | 未处理 `MessageSegment.image` 的 `url` 字段 | 需新增从 url 下载/转 base64 的逻辑 |
| **配置系统** | `db.py` 存 `ai/group/scheduler/admin` 分区，`config_loader.py` 统一读取，admin 面板可改 | 新增 `vision/image/voice` 分区，沿用同一套模式 |
| **管理面板** | `static/index.html`（Alpine.js）Tab 结构 + 对应 FastAPI 路由 | 需新增 Tab 与配置项 |
| **依赖** | `pyproject.toml` 依赖最少，无媒体处理库 | 需增加相应依赖 |

### 1.3 当前 `_call_llm` 关键代码（准多模态基础）

```python
payload = {
    "model": cfg.get("model", "gpt-4o-mini"),
    "messages": messages,          # 目前是 [{role, content: str}]
    "max_tokens": 1024,
}
```

OpenAI 兼容 API 的多模态消息格式（Claude / OpenAI / Gemini 等大多兼容）：
```python
{"role": "user", "content": [
    {"type": "text", "text": "描述这张图片"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
]}
```

> 结论：现有架构**无需大改**即可支持三类功能，只需：(1) 新增三个服务调用层；(2) 扩展 `ai_chat` 消息组装；(3) 沿用配置/面板模式新增配置分区。攻击面小，可并行开发。

---

## 二、总体设计原则

1. **沿用现有架构模式**：新增功能都做成插件（`plugins/vision`、`plugins/api_clients`），注册进 `pyproject.toml`，复用 `admin/db.py` + `config_loader.py` 的配置读写。
2. **独立类型/分区**：图像生成、语音生成使用各自独立 API（模型与文本 LLM 往往不同），配置按 `image`、`voice` 分区，避免耦合在一个 `ai` 分区里。
3. **调用层复用**：抽一个统一的 `api_clients` 模块承载"识别 / 生成 / 语音"三个 provider 客户端，`ai_chat` 只做编排。
4. **安全边界**：媒体文件统一落盘到 `data/media/`，URL 处理防 SSRF（限制内网/本地地址），图片 base64 大小限制，管理员可开关各功能。
5. **OneBot 消息类型**：识别输入用 `MessageSegment.image.url`；生成输出用 `MessageSegment.image(file://...)` / `MessageSegment.record(file://...)` 发送本地文件，OneBot 会自动上传。

---

## 三、模块划分

```
plugins/
├── api_clients/           # 新增：AI Provider 调用层（供各插件复用）
│   ├── __init__.py
│   ├── text.py            #   LLM 文本+图片识别（多模态 chat/completions）→ 由 ai_chat 调用
│   ├── image_gen.py       #   图像生成客户端（images/generations 或第三方绘画 API）
│   ├── voice_gen.py       #   语音合成客户端（TTS / audio/speech）
│   └── media.py           #   图片 url 下载、转 base64、头像/临时文件等工具
├── vision/                # 新增：图像识别插件（升级 ai_chat 或独立 on_message）
│   ├── __init__.py
│   ├── config.py
│   └── plugin.py
├── image_gen/             # 新增：图像生成插件
│   ├── __init__.py
│   ├── config.py
│   └── plugin.py
├── voice_gen/             # 新增：语音生成插件
│   ├── __init__.py
│   ├── config.py
│   └── plugin.py
└── ai_chat/               # 修改：让文本对话可携带图片上下文
    └── plugin.py
```

配套改动：
- `pyproject.toml`：`plugins` 列表新增三项；`dependencies` 增加（见 §4.1）。
- `plugins/admin/db.py`：`_DEFAULT_CONFIG` 新增 `image`、`voice`、`vision` 分区。
- `plugins/config_loader.py`：新增 `get_image_config()` / `get_voice_config()`。
- `admin/api.py` + `static/index.html`：新增对应配置页 + API 路由。

---

## 四、各功能实现方案

### 4.1 依赖准备（`pyproject.toml`）

```toml
dependencies = [
    "nonebot2[fastapi]>=2.3.0",
    "nonebot-adapter-onebot>=2.4.0",
    "nonebot-plugin-apscheduler>=0.4.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    # 新增
    "aiofiles>=23.2.0",        # 异步读写媒体文件
]
```
> 图片转 base64 用标准库 `base64`；url 下载用现有 `httpx`。**无需** Pillow/ffmpeg（本方案不做服务端图片压缩/音频转码，交给上游 API）。

---

### 4.2 图像识别（Vision）

**触发方式**：`@机器人 + 图片`（多数主流模型都识别不了纯文本模型，故识别能力放在 ai_chat 或独立入口）。

**方案A（推荐，改动最小）**：直接升级 `ai_chat`
- 在 `handle_at_ai` 中，若事件含 `MessageSegment.image`，取其 `url`，通过 `media.download_image_to_base64()` 转为 base64 data URI。
- `_build_messages` 支持段落化 content（list 形式），识别结果走原有文本对话回流。
- 触发条件用 `to_me()` + 含图片。纯前缀 `/ai` 文本场景不变。

**方案B（独立 /看图 指令）**：新建 `vision` 插件
- `on_command("看图")` / `on_command("识别")`，参数取图片 url。
- 更贴近"识别工具"定位，与对话解耦，便于后续加专用识别模型（如 Claude 4.x 视觉、通义千问 VL）。

**消息组装示例**
```python
payload = {
    "model": cfg.get("model"),      # 需为视觉模型，如 claude-4-5 / gpt-4o / qwen-vl
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt or "请描述这张图片的内容与构图"},
            {"type": "image_url", "image_url": {"url": base64_data_uri}},
        ],
    }],
    "max_tokens": 1024,
}
```
注意：识别要求 `model` 支持 vision；若用户把模型配成纯文本模型（如 deepseek-chat），错误信息需明确提示"请配置视觉模型"。

**上下文与防滥用**：
- 图片 base64 仅存在于本次请求，不写入 `_contexts`（避免图片塞爆内存上下文）；可在文本中追加一句"[你刚才收到一张图片]"轻量提示。
- 限制单图大小（默认 5MB），超限返回提示。

---

### 4.3 图像生成（Image Generation）

**触发方式**：`/画 <描述>` 或 `/作图 <描述>` 指令（优先级建议 `on_command`，priority 5~10）。

**调用层 `image_gen.py`**：支持两种后端
1. **OpenAI 兼容 `images/generations`**（DALL-E 系、部分国产兼容服务）
   ```python
   POST {image.api_base}/images/generations
   {"model": "...", "prompt": "...", "size": "1024x1024", "n": 1, "response_format": "url|b64_json"}
   ```
2. **第三方绘图 HTTP API**（Stable Diffusion / Midjourney 代理等）：走 `httpx`，模型/地址/size 由配置驱动，返回图 url。

**发送**：下载生成的图片到 `data/media/image_gen/`，用 `MessageSegment.image(file:///app/data/media/image_gen/xxx.png)` 发送（OneBot 本地文件回传）。
> 说明：OneBot V11 的 `file://` 路径需在 **NapCat 容器内可访问**。本项目 bot 与 napcat 分属两容器，路径需共享。见 §6 部署注意事项。

**配置分区 `image`**：
```jsonc
{
  "image": {
    "enabled": true,
    "api_base": "https://api.openai.com/v1",
    "api_key": "",
    "model": "dall-e-3",
    "size": "1024x1024",        // 或 512/2048
    "provider": "openai",        // openai | custom
    "trigger": "/画"
  }
}
```

---

### 4.4 语音生成（TTS / Voice Generation）

**触发方式**：`/说 <文本>` 或 `/语音 <文本>`。

**调用层 `voice_gen.py`**：两种后端
1. **OpenAI-compatible `/audio/speech`**（返回 mp3 字节流）
   ```python
   POST {voice.api_base}/audio/speech
   {"model": "tts-1", "input": "...", "voice": "alloy"}
   # 也支持实时/云端 TTS 如火山、Azure、阿里等，统一封装为“输入文本→音频 bytes”
   ```
2. **自定义 TTS API**（Edge-TTS、火山方舟、CosyVoice 等），同样封装成"文本 → 音频文件"。

**发送**：音频落盘 `data/media/voice_gen/xxx.mp3`，`MessageSegment.record(file://...)` 发送（OneBot 语音，会自动转 silk 上传）。

**配置分区 `voice`**：
```jsonc
{
  "voice": {
    "enabled": true,
    "api_base": "https://api.openai.com/v1",
    "api_key": "",
    "model": "tts-1",
    "voice": "alloy",
    "speed": 1.0,
    "provider": "openai",
    "trigger": "/说"
  }
}
```

---

## 五、管理面板改造（`admin`）

沿用现有 `db.py` 分区 + Alpine.js Tab 模式，新增 **两个 Tab**：

1. **图像生成**（`image`）：enabled 开关、api_base、api_key、model、尺寸下拉、provider。
2. **语音生成**（`voice`）：enabled 开关、api_base、api_key、model、音色下拉、语速。
3. **视觉识别**：并入「AI 助手」Tab 或独立一项，提示"需配置支持图片的模型"，并暴露"识别开关"。

**后端路由**：`admin/api.py` 仿照 `/api/ai` 增写 `/api/image`、`/api/voice`（同样走 `_safe_ai` 式 key 脱敏，新增 `_safe_image/_safe_voice`）。
**前端**：`index.html` 的 `tabs` 数组加两项 + `loadImage()/loadVoice()/saveImage()/saveVoice()`。

---

## 六、部署与运维注意事项

1. **媒体目录**：统一 `data/media/`，建议在 `docker-compose.yml` 中给 `bot` 与 `napcat` **共享同一个磁盘卷**（或用 `file://` 指向 bot 容器内路径 + SSHFS/命名卷），否则 NapCat 读不到生成文件。
   - 更稳的方案：生成后下载图片/音频到 `data/media/`，用 **相对 bot 进程的绝对路径** 发 `file://`，并在 napcat 侧把这个目录挂载为同一路径。
2. **依赖安装**：Dockerfile 用清华源，新增依赖无需改 Dockerfile（`pip install -e .` 会读 pyproject）。
3. **视觉模型必须**：识别时若配置的是纯文本模型（如 `deepseek-chat`），需捕获错误并明确提示。
4. **API Key 安全**：`image`/`voice` 分区照抄 `_safe_ai` 做 key 截断返回，避免面板回显明文。
5. **频率限制（可选）**：生成类是高频高消耗功能，可在群内做用户频率限制（存入 `data`，复用 context 结构思路），防止被刷。

---

## 七、实施顺序（里程碑）

| 阶段 | 内容 | 预估工作量 |
|------|------|-----------|
| **M0** | 依赖补充、`img_gen/voice` 配置分区 + DB 默认值 + config_loader 读取 | 小 |
| **M1** | 图像识别：`media.py` 工具 + `ai_chat` 多模态消息组装 + 图片触发 | 中 |
| **M2** | 图像生成：`api_clients/image_gen.py` + `/画` 指令 + 本地文件发送 | 中 |
| **M3** | 语音生成：`api_clients/voice_gen.py` + `/说` 指令 + 语音发送 | 中 |
| **M4** | 管理面板：`image`/`voice`／识别配置 Tab + API 路由 + key 脱敏 | 中 |
| **M5** | Docker 共享媒体卷、频率限制、SSRF 防护、README 文档 | 小 |
| **M6** | 联调 + 多模型兼容验证（视觉模型/绘画 API/TTS API 各验一个） | 中 |

**建议**：M1 与 M2/M3 相互独立，可并行派发子 Agent 实现；M4 依赖 M2/M3 的配置字段定稿。

---

## 八、风险与对策

| 风险 | 对策 |
|------|------|
| 识别需要视觉模型，但用户配的是文本模型 | 启动/调用时校验 model，错误明确提示 |
| 生成图片/音频 napcat 加载失败（容器路径隔离） | §6 媒体目录共享方案；失败时回退 base64 或提示 |
| base64 图片导致 payload 过大/上下文膨胀 | 限制图片大小，仅本次请求携带，不写长期 context |
| API Key 泄露 / 面板明文回显 | 复用 `_safe_*` 脱敏；面板只显示"已设置" |
| 高频刷生成接口产生费用 | admin 加开关 + 用户频率限制 |
| SSRF（用户图片 url 指向内网） | 下载前过滤内网/回环地址（httpbin 等） |
| 各 provider 兼容性差异 | 统一封装 Provider 抽象，配置驱动，出错信息友好 |
```
