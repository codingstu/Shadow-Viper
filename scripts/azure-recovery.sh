#!/bin/bash

# SpiderFlow Azure VM 快速恢复脚本
# 用途：在 DNS 故障或 Supabase 不可用时快速恢复后端

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║       SpiderFlow 快速恢复脚本 (Azure VM)                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/home/azureuser/spiderflow"
PYTHON_CMD="python -m backend.app.main"

# 1. 检查项目目录
echo "1️⃣ 检查项目目录..."
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 项目目录不存在: $PROJECT_DIR"
    exit 1
fi
cd "$PROJECT_DIR"
echo "✅ 项目目录: $PROJECT_DIR"

# 2. 拉取最新代码
echo ""
echo "2️⃣ 拉取最新代码..."
git pull origin dev
echo "✅ 代码已更新"

# 3. 杀死旧进程
echo ""
echo "3️⃣ 停止旧后端进程..."
pkill -f main.py || true
pkill -f "python -m backend.app.main" || true
sleep 1
echo "✅ 旧进程已停止"

# 4. 激活虚拟环境
echo ""
echo "4️⃣ 激活虚拟环境..."
if [ ! -d "$PROJECT_DIR/backend/venv" ]; then
    echo "❌ 虚拟环境不存在，请先执行: python -m venv backend/venv"
    exit 1
fi
source "$PROJECT_DIR/backend/venv/bin/activate"
echo "✅ 虚拟环境已激活"

# 5. 启动后端（后台）
echo ""
echo "5️⃣ 启动后端..."
nohup python -m backend.app.main > "$PROJECT_DIR/backend/backend.log" 2>&1 &
BACKEND_PID=$!
echo "✅ 后端已启动 (PID: $BACKEND_PID)"

# 6. 等待启动
echo ""
echo "6️⃣ 等待后端启动完成..."
sleep 3

# 7. 检查启动状态
echo ""
echo "7️⃣ 检查启动状态..."
if ps -p $BACKEND_PID > /dev/null; then
    echo "✅ 后端进程运行中"
    
    # 查看最后几行日志
    echo ""
    echo "📋 最新日志："
    tail -10 "$PROJECT_DIR/backend/backend.log"
else
    echo "❌ 后端启动失败！"
    echo ""
    echo "📋 完整日志："
    cat "$PROJECT_DIR/backend/backend.log"
    exit 1
fi

# 8. 网络诊断
echo ""
echo "8️⃣ 网络诊断..."
echo ""
echo "   DNS 配置："
cat /etc/resolv.conf | grep -E "^nameserver" || echo "   ⚠️ 未配置任何 DNS 服务器"
echo ""
echo "   Supabase 连接测试："
nslookup postgresql.supabase.co 2>&1 | head -5 || echo "   ⚠️ DNS 无法解析 postgresql.supabase.co"

# 9. 完成
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   ✅ 恢复完成！                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 启动状态："
echo "   • 后端 PID: $BACKEND_PID"
echo "   • 日志位置: $PROJECT_DIR/backend/backend.log"
echo "   • 监控日志: tail -f $PROJECT_DIR/backend/backend.log"
echo ""
echo "🧪 测试前端："
echo "   • 打开浏览器访问 http://localhost:8000"
echo "   • 或执行: curl http://localhost:8000/stats"
echo ""
echo "🔧 如果 DNS 故障，后端会自动使用内存缓存模式"
echo "   • 数据保存在内存中（重启后丢失）"
echo "   • API 继续正常工作（无 502 错误）"
echo ""
