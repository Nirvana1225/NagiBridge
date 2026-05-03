#!/bin/bash
# NagiBridge Channel 一键启动 — 在CC里粘贴: ! bash ~/source/NagiBridge/scripts/start_channel.sh
# 启动channel server + 输出提示

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INBOX="$HOME/nagi/overlay_inbox.jsonl"
mkdir -p "$(dirname "$INBOX")"
touch "$INBOX"

# 杀旧的
pkill -f "channel_server.py" 2>/dev/null
sleep 0.5

# 启动
cd "$SCRIPT_DIR"
nohup python channel_server.py > /dev/null 2>&1 &
sleep 1

if curl -s http://localhost:9000/ | grep -q "listening"; then
    echo "Channel server OK (:9000)"
else
    echo "Channel server FAILED"
    exit 1
fi
