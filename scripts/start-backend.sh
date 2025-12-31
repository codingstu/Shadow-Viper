#!/bin/bash

# SpiderFlow 后端启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 启动 SpiderFlow 后端服务..."
echo "📍 工作目录: $SCRIPT_DIR"

# 检查是否已有进程运行
if ps aux | grep -E "uvicorn|python.*app.main" | grep -v grep > /dev/null; then
    echo "⚠️  检测到已有后端服务在运行，先清理旧进程..."
    pkill -9 -f "uvicorn\|python.*app.main" 2>/dev/null
    sleep 2
    echo "✅ 旧进程已清理"
fi

# 启动后端
nohup python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --no-access-log > backend.log 2>&1 &

# 保存进程ID
echo $! > backend.pid

sleep 3

# 验证启动是否成功
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ 后端服务已启动！"
    echo "📍 API 地址: http://localhost:8000"
    echo "📍 API 文档: http://localhost:8000/docs"
    echo ""
    echo "查看日志: tail -f backend.log"
else
    echo "❌ 后端启动失败，查看日志:"
    tail -20 backend.log
    exit 1
fi
