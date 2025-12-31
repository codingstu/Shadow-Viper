#!/bin/bash
# Cloudflare Worker 检测测试脚本

# 配置
CF_WORKER_URL="${CF_WORKER_URL:-https://your-worker.workers.dev}"

echo "🔍 测试 Cloudflare Worker 节点检测"
echo "URL: $CF_WORKER_URL"
echo

# 测试数据
TEST_DATA='{
  "nodes": [
    {"host": "1.1.1.1", "port": 443, "id": "cloudflare-dns", "country": "US"},
    {"host": "8.8.8.8", "port": 53, "id": "google-dns", "country": "US"},
    {"host": "208.67.222.222", "port": 53, "id": "opendns", "country": "US"}
  ]
}'

echo "📤 发送测试请求..."
echo "测试节点: Cloudflare DNS (1.1.1.1:443), Google DNS (8.8.8.8:53), OpenDNS (208.67.222.222:53)"
echo

# 发送请求
RESPONSE=$(curl -s -X POST "$CF_WORKER_URL" \
  -H "Content-Type: application/json" \
  -d "$TEST_DATA")

# 检查响应
if [ $? -eq 0 ]; then
    echo "✅ 请求成功!"
    echo "📊 检测结果:"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
else
    echo "❌ 请求失败!"
    echo "请检查:"
    echo "1. CF_WORKER_URL 环境变量是否正确设置"
    echo "2. Worker 是否已正确部署"
    echo "3. URL 是否可访问"
fi

echo
echo "💡 使用提示:"
echo "• 设置环境变量: export CF_WORKER_URL=https://your-worker.workers.dev"
echo "• 集成到后端: 在 SpiderFlow 中设置 CF_WORKER_URL 环境变量"
echo "• 触发检测: curl -X POST http://127.0.0.1:8000/nodes/trigger"