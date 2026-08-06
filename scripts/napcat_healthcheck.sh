#!/bin/bash
# NapCat 健康检查脚本
# 检测 NapCat 是否掉线，掉线则自动重启
# 用法: crontab -e -> */5 * * * * /www/wwwroot/qqagent/scripts/napcat_healthcheck.sh

PROJECT_DIR="/www/wwwroot/qqagent"
LOG_FILE="$PROJECT_DIR/logs/healthcheck.log"
WEBUI_PORT=6099

mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 1. 检查 napcat 容器是否在运行
CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' qqagent-napcat 2>/dev/null)
if [ "$CONTAINER_STATUS" != "running" ]; then
    log "napcat 容器未运行 (状态: $CONTAINER_STATUS)，正在启动..."
    cd "$PROJECT_DIR" && docker compose up -d napcat
    sleep 10
    log "napcat 容器已启动"
    exit 0
fi

# 2. 检查 bot 与 napcat 的 WebSocket 连接是否正常
# 如果 bot 日志最近 5 分钟内有 "closed by peer" 且没有后续的 "connected"，说明掉线了
BOT_LOG=$(docker logs --since 5m qqagent-bot 2>&1)
LAST_CLOSED=$(echo "$BOT_LOG" | grep "closed by peer" | tail -1)
LAST_CONNECTED=$(echo "$BOT_LOG" | grep "connected" | tail -1)

if [ -n "$LAST_CLOSED" ] && [ -z "$LAST_CONNECTED" ]; then
    log "检测到 WebSocket 断开且未重连，重启 napcat..."
    cd "$PROJECT_DIR" && docker compose restart napcat
    sleep 15
    log "napcat 已重启，等待重新连接..."

    # 再等 10 秒检查 bot 是否重新连上
    sleep 10
    NEW_LOG=$(docker logs --since 30s qqagent-bot 2>&1)
    if echo "$NEW_LOG" | grep -q "connected"; then
        log "bot 已重新连接 napcat"
    else
        log "警告: napcat 重启后 bot 仍未连接，可能需要扫码登录"
    fi
    exit 0
fi

# 3. 检查 WebUI 是否可访问（napcat 进程是否正常）
if ! curl -s -o /dev/null -m 5 "http://127.0.0.1:$WEBUI_PORT/" 2>/dev/null; then
    log "NapCat WebUI 不可访问，重启 napcat..."
    cd "$PROJECT_DIR" && docker compose restart napcat
    sleep 15
    log "napcat 已重启"
    exit 0
fi

log "napcat 运行正常"
