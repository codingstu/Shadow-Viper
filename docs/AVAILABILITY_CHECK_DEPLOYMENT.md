# 🚀 多层级节点可用性检测系统 - 部署指南

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│ 三层分布式检测架构                                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│ 🌐 第1层：快速检测（Aliyun FC / Cloudflare Worker）  │
│    • TCP 连接测试                    [20-30s]       │
│    • HTTP 代理功能测试                              │
│    • DNS 基础检测                                    │
│    └─ 过滤掉明显不可用的节点                        │
│                                                      │
│ 🔧 第2层：深度检测（SpiderFlow 后端）               │
│    • 协议握手验证 (VMess/VLESS/Trojan)              │
│    • 真实代理功能测试                               │
│    • 健康评分计算                    [2-5min]       │
│    └─ 标记为 VERIFIED 或 SUSPECT                    │
│                                                      │
│ 💚 第3层：持续监测（SpiderFlow 后端）               │
│    • 定期心跳检测                    [5min/次]      │
│    • 自动故障转移                                   │
│    • 历史数据追踪                                   │
│    └─ 实时更新节点状态                              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## 文件说明

### 1. 后端模块（SpiderFlow）

#### `real_availability_check.py`（核心检测模块）
```
功能：
✓ 多层级节点可用性检测
✓ TCP 连接测试
✓ DNS 解析测试
✓ HTTP 代理功能测试
✓ 协议握手验证（VMess/VLESS/Trojan）
✓ 健康评分系统
✓ 批量并发检测

集成方式：
from .real_availability_check import (
    check_node_basic_availability,      # 第1-3层检测
    check_node_full_availability,       # 第1-4层检测（含握手）
    check_nodes_batch,                  # 批量检测
    AvailabilityLevel,                  # 可用性等级枚举
    filter_by_availability_level,       # 等级过滤
    get_health_statistics               # 统计信息
)
```

#### `node_hunter.py`（修改内容）
新增方法：`_test_nodes_with_new_system()`
```python
# 替代原来的 test_and_update_nodes()
# 使用新的多层级检测系统
# 自动关联节点和检测结果
# 计算健康评分
```

### 2. Aliyun FC 部署

#### `aliyun_fc_availability_check.py`
```
轻量级版本，可直接部署到 Aliyun Function Compute
特点：
- 仅执行 TCP + HTTP 基础检测
- 避免超时（FC 限制 15 分钟）
- 支持批量并发
- 无需复杂依赖

部署步骤：
1. 复制 aliyun_fc_availability_check.py 到 FC
2. 配置环境变量（如需要）
3. 创建 HTTP 触发
4. 测试 API 端点
```

### 3. Cloudflare Worker 部署

#### `cloudflare_worker_availability_check.js`
```
超轻量级版本，纯 JavaScript
特点：
- 全球 CDN 加速
- 30 秒超时限制内完成
- 无服务器基础设施
- 完全免费（免费额度）

部署步骤：
1. 登录 Cloudflare Dashboard
2. 创建新的 Worker
3. 复制 cloudflare_worker_availability_check.js 代码
4. 部署并获取 Workers URL
5. 在 SpiderFlow 配置中调用

CF Worker 的限制：
❌ 无法执行真实的代理 HTTP 请求
❌ 不支持原生 TCP Socket
❌ 30 秒执行超时
✓ 仅用于快速的存活检测
```

## 可用性等级说明

```
DEAD (0)      ❌ 不可用
  └─ TCP 连接失败

SUSPECT (1)   ⚠️ 可疑
  └─ TCP 通但代理不通（标准协议）

BASIC (2)     ✓ 基础可用
  └─ HTTP 测试通过
  └─ 或 TCP 通（复杂协议如 VMess）

VERIFIED (3)  ✅ 已验证
  └─ 通过协议握手验证
  └─ 健康评分 >= 80

HEALTHY (4)   💚 健康
  └─ 连续监测通过
  └─ 历史评分稳定
```

## 部署方案对比

| 方案 | 检测深度 | 执行时间 | 成本 | 适用场景 |
|------|---------|--------|------|--------|
| **CF Worker** | 快速检测 | 20-30s | 免费 | 预过滤，海外检测 |
| **Aliyun FC** | 快速检测 | 30-60s | 低 | 大陆检测，速度测试 |
| **后端深度** | 完整检测 | 2-5min | 低 | 精确验证，握手检测 |
| **后端监测** | 持续监测 | 5min/次 | 低 | 长期稳定性追踪 |

## 推荐部署策略

### 方案 A：经济版（推荐新手）
```
1. 使用后端的 _test_nodes_with_new_system()
   └─ 内置 TCP + HTTP + 握手验证
   └─ 无需外部云函数

成本：仅需 SpiderFlow 后端
优点：简单易维护，功能完整
缺点：初次扫描较慢（2-5 分钟）
```

### 方案 B：高效版（推荐生产）
```
1. Aliyun FC 快速过滤
   └─ 扫描 → TCP+HTTP 基础检测 → 保留可用的

2. 后端深度验证 + 监测
   └─ 对 FC 筛选的结果做握手验证
   └─ 5 分钟定期监测

流程：
原始节点 (N个)
  ↓
[Aliyun FC] 快速过滤 (20-30s) → 预筛选的节点 (50%)
  ↓
[后端深度] 握手验证 + 监测 (2-5min) → 最终可用节点 (20-30%)

优点：整体速度快，精度高
成本：FC 调用费用（通常很低）
```

### 方案 C：全球分布版（推荐大规模）
```
1. CF Worker 海外检测
   └─ 全球 CDN 位置，代表海外可达性

2. Aliyun FC 大陆检测
   └─ 大陆机房，代表大陆可达性

3. 后端深度验证
   └─ 同时发出 CF + FC 请求
   └─ 并行执行，快速获得全球覆盖

优点：全球检测，区域覆盖
成本：CF 免费 + FC 按量计费
```

## 集成步骤

### 第 1 步：安装依赖（仅后端需要）
```bash
# 如果还未安装
pip install aiohttp
```

### 第 2 步：启用新系统
```bash
# 在 SpiderFlow 后端 .env 文件中添加
NEW_AVAILABILITY_CHECK_ENABLED=true
```

### 第 3 步：配置 Aliyun FC（可选）
```bash
# 如果使用 Aliyun FC，部署函数
# 获得 FC 访问地址，例如：
# ALIYUN_AVAILABILITY_CHECK_URL=https://your-region-xxx.fc.aliyun.com/2016-08-15/proxy/xxx/

# 在 .env 配置
ALIYUN_AVAILABILITY_CHECK_URL=https://...
```

### 第 4 步：配置 CF Worker（可选）
```bash
# 部署 Worker，获得访问地址，例如：
# https://your-worker.workers.dev/

# 在 .env 配置
CF_WORKER_AVAILABILITY_CHECK_URL=https://your-worker.workers.dev/
```

### 第 5 步：重启后端
```bash
# 在 SpiderFlow/backend 目录
. .venv/bin/activate
uvicorn app.main:app --reload
```

## API 接口示例

### SpiderFlow 后端接口
```bash
# 获取节点统计信息（包含检测结果）
curl http://127.0.0.1:8000/nodes/stats
```

### Aliyun FC 接口（如已部署）
```bash
curl -X POST https://your-fc-url/nodes/check \
  -H "Content-Type: application/json" \
  -d '{
    "nodes": [
      {"host": "1.1.1.1", "port": 443, "id": "node1", "country": "US"}
    ]
  }'
```

### Cloudflare Worker 接口（如已部署）
```bash
curl -X POST https://your-worker.workers.dev/ \
  -H "Content-Type: application/json" \
  -d '{
    "nodes": [
      {"host": "1.1.1.1", "port": 443, "id": "node1", "country": "US"}
    ]
  }'
```

## 常见问题

### Q1: 为什么我的节点在测速中可用但实际不能用？
**A:** 之前的系统仅做速度测试，现在新系统添加了：
- TCP 握手验证（确认端口真的开放）
- HTTP 代理功能测试（确认代理真的工作）
- 协议握手验证（确认协议配置正确）

### Q2: 新系统会不会删除我的真实可用节点？
**A:** 不会。新系统设置了严格的保护机制：
- 连续 3 次失败才标记为不可用
- 5 分钟后自动重试
- 一旦恢复就立即标记为可用

### Q3: 可以在 Cloudflare 完全执行所有检测吗？
**A:** 不行。CF Worker 有两个限制：
- ❌ 30 秒执行超时（复杂检测需要 2-5 分钟）
- ❌ 无法发送通过代理的真实 HTTP 请求

建议：CF 用于快速预过滤，后端用于深度检测。

### Q4: 新系统对我的节点数据库有什么影响？
**A:** 完全兼容。新系统添加了额外字段但不破坏现有数据：
```json
{
  "host": "1.1.1.1",
  "port": 443,
  // ... 原始字段 ...
  "alive": true,
  "availability_level": "VERIFIED",  // 🆕
  "health_score": 85,                // 🆕
  "latency": 150,
  "protocol_verified": true          // 🆕
}
```

## 性能预期

### 后端单次扫描
```
输入：500 个节点
并发：20
执行时间：3-5 分钟
过滤率：60-70%（输出 150-200 个可用节点）
CPU 占用：10-20%
内存占用：50-100 MB
```

### Aliyun FC 执行
```
输入：500 个节点
执行时间：30-60 秒
成本：~0.01-0.05 元（根据执行时间）
并发限制：无（按次按量计费）
```

### Cloudflare Worker
```
输入：20-50 个节点（受 30s 限制）
执行时间：< 20 秒
成本：免费（免费额度足够）
并发限制：默认 10 并发
```

## 故障排除

### 问题 1：检测全部失败
```
解决方案：
1. 检查网络连接
2. 检查 DNS 设置
3. 验证节点地址是否正确
4. 查看后端日志: tail -f /tmp/uvicorn_restart.log
```

### 问题 2：CF Worker 超时
```
解决方案：
1. 减少单批节点数（< 20）
2. 增加并发间隔
3. 仅用于基础检测，复杂验证在后端执行
```

### 问题 3：内存溢出
```
解决方案：
1. 减少并发数（--max_concurrent 10）
2. 分批处理
3. 定期重启后端
```

## 下一步

1. ✅ 已部署：多层级检测系统
2. ⬜ 待部署：CF Worker（可选）
3. ⬜ 待部署：Aliyun FC（可选）
4. ⬜ 待实现：自动故障恢复策略
5. ⬜ 待实现：Web Dashboard 可视化

有任何问题，请查看 SpiderFlow 后端日志！
