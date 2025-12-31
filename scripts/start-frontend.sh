#!/bin/bash

# SpiderFlow 前端启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/frontend"

echo "🚀 启动 SpiderFlow 前端服务..."
echo "📍 工作目录: $(pwd)"

# 检查依赖
if [ ! -d "node_modules" ]; then
    echo "📦 检测到缺少依赖，正在安装..."
    npm install
fi

# 启动前端
echo "⏳ 启动 Vite 开发服务器..."
npm run dev
