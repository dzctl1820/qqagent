#!/bin/bash
# NapCat 健康检查脚本
# 检测 NapCat 是否掉线，掉线则自动重启
# 用法: crontab -e -> */5 * * * * /www/wwwroot/qqagent/scripts/napcat_healthcheck.sh

PROJECT_DIR="/www/wwwroot/qqagent"
LOG_FILE="$PROJECT_DIR/logs/healthcheck.log"
WEBUI_PORT=6099
RESTART_FLAG="$PROJECT_DIR/logs/.napcat_restarting"

mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 如果正在重启中（10 分钟内），跳过检查避免重复重启
if [ -f "$RESTART_FLAG" ]; then
    FLAG_TIME=$(stat -c %Y "$RESTART_FLAG" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    DIFF=$((NOW - FLAG_TIME))
    if [ "$DIFF" -lt 600 ]; then
        exit 0
    fi
    rm -f "$RESTART_FLAG"
fi

# 1. 检查 napcat 容器是否在运行
CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' qqagent-napcat 2>/dev/null)
if [ "$CONTAINER_STATUS" != "running" ]; then
    log "napcat 容器未运行 (状态: $CONTAINER_STATUS)，正在启动..."
    touch "$RESTART_FLAG"
    cd "$PROJECT_DIR" && docker compose up -d napcat
    sleep 15
    log "napcat 容器已启动"
    exit 0
fi

# 2. 检查 bot 与 napcat 的 WebSocket 连接是否正常
BOT_LOG=$(docker logs --since 5m qqagent-bot 2>&1)
LAST_CLOSED=$(echo "$BOT_LOG" | grep "closed by peer" | tail -1)
LAST_CONNECTED=$(echo "$BOT_LOG" | grep "connected" | tail -1)

if [ -n "$LAST_CLOSED" ] && [ -z "$LAST_CONNECTED" ]; then
    log "检测到 WebSocket 断开且未重连，重启 napcat..."
    touch "$RESTART_FLAG"
    cd "$PROJECT_DIR" && docker compose restart napcat
    sleep 20
    log "napcat 已重启，等待重新连接..."

    NEW_LOG=$(docker logs --since 30s qqagent-bot 2>&1)
    if echo "$NEW_LOG" | grep -q "connected"; then
        log "bot 已重新连接 napcat（session 有效，无需扫码）"
        rm -f "$RESTART_FLAG"
    else
        log "警告: napcat 重启后 bot 仍未连接，可能 session 失效需要扫码"
        log "请访问 WebUI 扫码: http://<服务器IP>:6099/webui"
    fi
    exit 0
fi

# 3. 检查 WebUI 是否可访问
if ! curl -s -o /dev/null -m 5 "http://127.0.0.1:$WEBUI_PORT/" 2>/dev/null; then
    log "NapCat WebUI 不可访问，重启 napcat..."
    touch "$RESTART_FLAG"
    cd "$PROJECT_DIR" && docker compose restart napcat
    sleep 20
    log "napcat 已重启"
    exit 0
fi

# 4. 检查 napcat 日志中是否有掉线关键词
NAPCAT_LOG=$(docker logs --since 5m qqagent-napcat 2>&1)
if echo "$NAPCAT_LOG" | grep -qi "offline\|掉线\|kicked\|被踢\|login.*fail\|登录失败\|session.*expire"; then
    log "检测到 napcat 掉线关键词，重启 napcat..."
    touch "$RESTART_FLAG"
    cd "$PROJECT_DIR" && docker compose restart napcat
    sleep 20
    NEW_LOG=$(docker logs --since 30s qqagent-bot 2>&1)
    if echo "$NEW_LOG" | grep -q "connected"; then
        log "重启后 bot 已重新连接"
        rm -f "$RESTART_FLAG"
    else
        log "警告: 重启后仍未连接，可能需要扫码"
    fi
    exit 0
fi

log "napcat 运行正常"
