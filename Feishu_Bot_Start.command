#!/bin/bash
# 自动进入脚本所在目录
cd "$(dirname "$0")"

echo "------------------------------------------------"
echo "🚀 正在启动 OpenClaw 飞书机器人..."
echo "------------------------------------------------"

# 检查是否安装了必要的库
echo "📦 检查依赖环境..."
pip3 install -r requirements.txt > /dev/null 2>&1

# 启动机器人
echo "🤖 机器人服务正在运行中..."
echo "💡 提示：请保持此窗口开启。如果需要停止，请按 Control + C。"
echo "------------------------------------------------"

python3 OpenClaw_GEO/feishu_bot.py
