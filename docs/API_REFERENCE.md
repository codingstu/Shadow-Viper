# SpiderFlow API 参考文档

**最后更新**：2026-01-01 Round 5  
**版本**：1.1 (CF Worker 迁移版)

---

## 📡 基础信息

- **Base URL**：`http://localhost:8000`
- **API Prefix**：`/nodes`, `/api`
- **超时**：10s
- **格式**：JSON

---

## 🔍 节点查询 API

### GET `/api/nodes` - 获取过滤后的节点列表

获取根据显示开关过滤后的活跃节点列表。

#### 请求

```http
GET /api/nodes?show_socks_http=false&show_china_nodes=true&limit=500
```

#### 查询参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `show_socks_http` | boolean | null | 显示 Socks/HTTP 节点（null=使用服务器状态） |
| `show_china_nodes` | boolean | null | 显示中国节点（null=使用服务器状态） |
| `limit` | integer | 50 | 返回节点数量限制（1-500） |

#### 响应 (200 OK)

```json
[
  {
    "id": "209.126.84.189:443",
    "protocol": "vmess",
    "host": "209.126.84.189",
    "port": 443,
    "country": "US",
    "name": "VMESS-US-Server",
    "link": "vmess://...",
    "content": "{ /* 节点完整信息 JSON */ }",
    "speed": 5.0,
    "delay": 150,
    "latency": 150,
    "is_free": true
  },
  ...
]
```

#### 错误响应

```json
{
  "detail": "Invalid parameters"
}
```

#### 示例

```bash
# 隐藏 Socks/HTTP，显示中国节点
curl "http://localhost:8000/api/nodes?show_socks_http=false&show_china_nodes=true&limit=100"

# 使用服务器默认状态
curl "http://localhost:8000/api/nodes?limit=50"
```

---

### GET `/nodes/stats` - 获取统计信息

获取系统统计、日志、下次扫描时间。

#### 请求

```http
GET /nodes/stats
```

#### 响应 (200 OK)

```json
{
  "count": 15,
  "running": false,
  "logs": [
    "[23:10:48] 🎉 全部测试完成",
    "[23:10:47] 📈 Clash 检测完成 - 总计: 50, 可用: 15",
    "[23:10:00] 🚀 开始全网扫描..."
  ],
  "nodes": [
    {
      "group_name": "US",
      "nodes": [ /* node objects */ ]
    },
    {
      "group_name": "DE",
      "nodes": [ /* node objects */ ]
    }
  ],
  "next_scan_time": 1735689600.0
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | int | 活跃节点总数 |
| `running` | bool | 是否正在扫描 |
| `logs` | array[string] | 最近 100 条日志（最新优先） |
| `nodes` | array[object] | 按国家分组的节点（仅统计，不含详情） |
| `next_scan_time` | float | 下次扫描的 Unix 时间戳 |

#### 示例

```bash
curl http://localhost:8000/nodes/stats
```

---

## 🎛️ 显示控制 API

### GET `/nodes/socks_http_status` - 获取 Socks/HTTP 显示状态

#### 请求

```http
GET /nodes/socks_http_status
```

#### 响应 (200 OK)

```json
{
  "show_socks_http": false
}
```

#### 示例

```bash
curl http://localhost:8000/nodes/socks_http_status
```

---

### POST `/nodes/toggle_socks_http` - 切换 Socks/HTTP 显示

#### 请求

```http
POST /nodes/toggle_socks_http?show=true
```

#### 查询参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `show` | boolean | ✓ | true=显示，false=隐藏 |

#### 响应 (200 OK)

```json
{
  "status": "success",
  "show_socks_http": true,
  "message": "socks/http 节点显示已开启"
}
```

#### 示例

```bash
# 显示 Socks/HTTP
curl -X POST "http://localhost:8000/nodes/toggle_socks_http?show=true"

# 隐藏 Socks/HTTP
curl -X POST "http://localhost:8000/nodes/toggle_socks_http?show=false"
```

---

### GET `/nodes/china_nodes_status` - 获取中国节点显示状态

#### 请求

```http
GET /nodes/china_nodes_status
```

#### 响应 (200 OK)

```json
{
  "show_china_nodes": false
}
```

#### 示例

```bash
curl http://localhost:8000/nodes/china_nodes_status
```

---

### POST `/nodes/toggle_china_nodes` - 切换中国节点显示

#### 请求

```http
POST /nodes/toggle_china_nodes?show=false
```

#### 查询参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `show` | boolean | ✓ | true=显示，false=隐藏 |

#### 响应 (200 OK)

```json
{
  "status": "success",
  "show_china_nodes": false,
  "message": "中国节点显示已关闭"
}
```

#### 示例

```bash
# 显示中国节点
curl -X POST "http://localhost:8000/nodes/toggle_china_nodes?show=true"

# 隐藏中国节点
curl -X POST "http://localhost:8000/nodes/toggle_china_nodes?show=false"
```

---

## 🚀 操作 API

### POST `/nodes/trigger` - 手动触发扫描

立即启动一次全网扫描周期。

#### 请求

```http
POST /nodes/trigger
```

#### 响应 (200 OK)

```json
{
  "status": "success",
  "message": "扫描已启动"
}
```

#### 响应 (当扫描已在进行中)

```json
{
  "status": "scanning",
  "message": "扫描已在进行中，跳过本次执行"
}
```

#### 示例

```bash
curl -X POST http://localhost:8000/nodes/trigger
```

---

### POST `/nodes/test_all` - 测试全部节点

对所有活跃节点进行速度/延迟测试。

#### 请求

```http
POST /nodes/test_all
```

#### 响应 (200 OK)

```json
{
  "status": "started",
  "message": "全量测试已启动"
}
```

#### 示例

```bash
curl -X POST http://localhost:8000/nodes/test_all
```

---

### POST `/nodes/test_single` - 测试单个节点 (✅ Round 4 真实速度测试)

#### 请求

```http
POST /nodes/test_single
Content-Type: application/json

{
  "host": "209.126.84.189",
  "port": 443
}
```

#### 请求体

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `host` | string | ✓ | 节点 IP 或域名 |
| `port` | integer | ✓ | 节点端口 |

#### 响应 (200 OK - 测试成功)

```json
{
  "status": "ok",
  "delay": 45,
  "speed": 67.30,
  "result": {
    "tcp_ping_ms": 45,
    "connection_time_ms": 48,
    "total_score": 95,
    ...
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `ok` (成功) / `fail` (失败) / `error` (错误) |
| `delay` | integer | **真实 TCP 延迟（毫秒）**，精确度 ±5ms |
| `speed` | float | **真实下载速度（MB/s）**，基于 10MB Cloudflare CDN 文件下载 |
| `result` | object | 详细的网络诊断结果（连接时间、评分等） |

**速度测试说明**：
- ✅ **真实下载**：代理通过 Cloudflare 下载 10MB 文件，精确计算速度
- ✅ **缓存机制**：同一节点 5 分钟内重复测试时使用缓存结果
- ✅ **自动降级**：如果下载测试超时，使用基于延迟的估计算法
- ✅ **失败处理**：无法连接返回 `status: "fail"`

#### 响应 (测试失败)

```json
{
  "status": "fail",
  "message": "Node unreachable"
}
```

#### 响应 (节点不存在)

```json
{
  "status": "error",
  "message": "Node not found"
}
```

#### 示例

```bash
# 测试单个节点的真实速度和延迟
curl -X POST http://localhost:8000/nodes/test_single \
  -H "Content-Type: application/json" \
  -d '{
    "host": "209.126.84.189",
    "port": 443
  }'

# 响应示例
# {
#   "status": "ok",
#   "delay": 45,
#   "speed": 67.30
# }
```

---

### GET `/nodes/qrcode` - 生成节点二维码

#### 请求

```http
GET /nodes/qrcode?host=209.126.84.189&port=443
```

#### 查询参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `host` | string | ✓ | 节点 IP 或域名 |
| `port` | integer | ✓ | 节点端口 |

#### 响应 (200 OK)

```json
{
  "qrcode_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
}
```

#### 示例

```bash
curl "http://localhost:8000/nodes/qrcode?host=209.126.84.189&port=443"
```

---

### POST `/nodes/add_source` - 添加自定义订阅源

#### 请求

```http
POST /nodes/add_source
Content-Type: application/json

{
  "url": "https://example.com/subscribe"
}
```

#### 请求体

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `url` | string | ✓ | 订阅链接（HTTP/HTTPS） |

#### 响应 (200 OK)

```json
{
  "status": "ok",
  "message": "添加成功，已加入扫描队列"
}
```

#### 响应 (URL 已存在)

```json
{
  "status": "error",
  "message": "该源已存在"
}
```

#### 示例

```bash
curl -X POST http://localhost:8000/nodes/add_source \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://raw.githubusercontent.com/example/nodes.txt"
  }'
```

---

### GET `/nodes/subscription` - 获取订阅链接

获取 Clash 兼容的订阅链接。

#### 请求

```http
GET /nodes/subscription
```

#### 响应 (200 OK)

```json
{
  "subscription": "http://localhost:8000/nodes/clash/config"
}
```

#### 示例

```bash
curl http://localhost:8000/nodes/subscription
```

---

## 📊 完整调用流程示例

### 初始化（前端启动时）

```javascript
// 1. 获取开关状态
const [socksStatus, chinaStatus] = await Promise.all([
  fetch('http://localhost:8000/nodes/socks_http_status'),
  fetch('http://localhost:8000/nodes/china_nodes_status')
]);

// 2. 获取节点列表（使用服务器默认状态）
const response = await fetch('http://localhost:8000/api/nodes?limit=500');
const nodes = await response.json();

// 3. 启用 3 秒轮询
setInterval(() => {
  fetch('http://localhost:8000/nodes/stats')
    .then(r => r.json())
    .then(data => {
      // 更新日志、下次扫描时间
      updateUI(data);
    });
}, 3000);
```

### 用户切换显示开关

```javascript
async function toggleSocksHttp(show) {
  // 1. 更新服务器状态
  await fetch(`http://localhost:8000/nodes/toggle_socks_http?show=${show}`, {
    method: 'POST'
  });
  
  // 2. 刷新节点列表（传递最新的开关状态）
  const response = await fetch(
    `http://localhost:8000/api/nodes?show_socks_http=${show}&show_china_nodes=${showChinaNodes}`
  );
  const nodes = await response.json();
  
  // 3. 前端更新显示
  updateNodesList(nodes);
}
```

---

## 🔐 安全建议

- 所有 POST 请求建议添加 CSRF 防护
- 生产环境建议添加 API 认证
- 建议限制单 IP 的请求频率（DDoS 防护）
- 不要在客户端暴露真实服务器地址，使用代理或 CDN

---

## 🐛 常见错误

| 状态码 | 错误 | 解决方案 |
|------|------|---------|
| 404 | `Not Found` | 检查 API 路由是否正确 |
| 422 | `Unprocessable Entity` | 查询参数格式错误 |
| 500 | `Internal Server Error` | 检查后端日志 |
| 503 | `Service Unavailable` | 后端服务未启动 |

---

## 📝 测试命令集合

```bash
# 获取统计信息
curl http://localhost:8000/nodes/stats | jq

# 获取节点列表
curl "http://localhost:8000/api/nodes?limit=10" | jq

# 获取开关状态
curl http://localhost:8000/nodes/socks_http_status | jq
curl http://localhost:8000/nodes/china_nodes_status | jq

# 切换显示
curl -X POST "http://localhost:8000/nodes/toggle_socks_http?show=true"
curl -X POST "http://localhost:8000/nodes/toggle_china_nodes?show=true"

# 手动扫描
curl -X POST http://localhost:8000/nodes/trigger

# 测试单个节点
curl -X POST http://localhost:8000/nodes/test_single \
  -H "Content-Type: application/json" \
  -d '{"host":"209.126.84.189","port":443}'

# 添加订阅源
curl -X POST http://localhost:8000/nodes/add_source \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/subscribe"}'
```

---

**文档版本**：1.0  
**最后更新**：2025-12-31 23:10  
**维护人**：AI Assistant
