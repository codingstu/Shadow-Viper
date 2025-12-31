#!/bin/bash

# SpiderFlow 停止脚本

echo "🛑 停止 SpiderFlow 服务..."

# 停止后端
echo "停止后端服务..."
pkill -9 -f "uvicorn\|python.*app.main" 2>/dev/null

# 停止前端
echo "停止前端服务..."
pkill -9 -f "vite\|npm.*dev" 2>/dev/null

sleep 1
echo "✅ 所有服务已停止"
