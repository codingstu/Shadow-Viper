#!/bin/bash

# SpiderFlow 一键启动脚本（同时启动前后端）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎯 SpiderFlow 一键启动"
echo "=" 
echo ""

# 启动后端
echo "1️⃣  启动后端服务..."
bash start-backend.sh

if [ $? -ne 0 ]; then
    echo "❌ 后端启动失败！"
    exit 1
fi

echo ""
echo "2️⃣  启动前端服务..."
echo ""
echo "前端启动需要单独开一个终端，请在新终端运行:"
echo ""
echo "  cd $SCRIPT_DIR"
echo "  bash start-frontend.sh"
echo ""
echo "或者直接运行:"
echo ""
echo "  npm --prefix $SCRIPT_DIR/frontend run dev"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 后端已启动，请在新终端启动前端"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 后端 API: http://localhost:8000"
echo "📍 前端页面: http://localhost:5173"
echo ""
