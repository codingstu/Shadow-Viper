# CHANGELOG - Phase 2: 数据同步和逻辑迁移

**日期**: 2026-01-01  
**版本**: 2.0.0  
**状态**: 开发中

## 概述

Phase 2是SpiderFlow和viper-node-store的战略性集成，目标是：
1. 实现实时数据同步（Webhook + 轮询混合）
2. 将检测逻辑迁移到viper-node-store
3. 实现用户发起的精确测速功能
4. 完整的文档化和架构说明

---

## 🎯 主要目标

### 1. 数据实时同步架构

**问题**：SpiderFlow的节点数据需要实时同步到viper-node-store，避免数据不一致

**解决方案**：Webhook + 轮询混合策略

#### Webhook（主要机制）
- **方向**: SpiderFlow → viper-node-store（实时推送）
- **触发**: SpiderFlow完成检测后自动推送
- **优势**:
  - ✅ 实时（毫秒级延迟）
  - ✅ 低流量（仅在数据变更时发送）
  - ✅ 立即可用
- **流量估算**: ~10-30MB/月

#### 轮询（备用机制）
- **方向**: viper-node-store → SpiderFlow（5分钟一次）
- **触发**: 定时任务，每5分钟检查一次
- **优势**:
  - ✅ 可靠（即使Webhook失败也能同步）
  - ✅ 简单实现
- **流量估算**: ~12-42MB/月

**混合优势**:
```
Webhook失败 → 轮询接管
轮询延迟 → Webhook补偿
总流量 ≈ 30MB/月 ✅ (在可接受范围内)
```

### 2. 检测逻辑迁移

**现状**: 检测逻辑集中在SpiderFlow，viper-node-store只是数据存储

**改进方案**:
- 将node_hunter.py的核心检测模块复制到viper-node-store
- SpiderFlow保持原有功能（用作主检测源）
- viper-node-store增加补充检测能力
- 共享CF Worker实例（全球边缘节点）

**优势**:
- ✅ 提高可用性（支持多地检测）
- ✅ 分散负载（不完全依赖Azure)
- ✅ 为用户精确测速做准备

### 3. 用户精确测速

**快速测速** (现有，基于延迟估算)
- 前端HEAD请求 → 计算延迟 → 推算速度
- 流量消耗: < 1KB
- 速度: ~1秒

**精确测速** (新增，真实下载文件)
- 用户点击[精确测速]按钮
- 显示流量消耗提示（如：50MB文件 = 50MB流量）
- 用户确认后开始下载
- 实际测量真实速度
- 流量消耗: 取决于测试文件大小

**实现方案**:
```
前端精确测速 → 下载50MB文件 → 测量真实速度
或者
后端精确测速 → 使用CF Worker → 全球节点代理下载
```

---

## 📁 新增文件结构

### viper-node-store

```
viper-node-store/
├── webhook_receiver.py          # Webhook接收器
│   ├── verify_webhook_signature() - 签名验证
│   ├── load_nodes_from_file() - 加载本地数据
│   ├── merge_node_data() - 合并节点数据
│   └── POST /webhook/nodes-update - Webhook端点
│
├── data_sync.py                 # 数据同步模块
│   ├── SyncState - 同步状态跟踪
│   ├── calculate_nodes_hash() - 检测数据变更
│   ├── poll_spiderflow_nodes() - 轮询同步
│   ├── DataSyncScheduler - 定时调度器
│   └── get_sync_statistics() - 同步统计
│
├── app_fastapi.py               # FastAPI主应用
│   ├── GET /api/nodes - 获取节点列表
│   ├── POST /webhook/nodes-update - Webhook推送
│   ├── GET /api/sync/status - 同步状态
│   ├── GET /api/stats/summary - 统计汇总
│   └── POST /api/nodes/precision-test - 精确测速
│
└── requirements.txt             # 更新依赖
    └── +fastapi, +uvicorn, +APScheduler
```

### SpiderFlow

```
backend/
├── webhook_push.py              # Webhook推送模块 (新增)
│   ├── generate_webhook_signature() - 生成签名
│   ├── push_nodes_to_viper() - 推送节点
│   ├── PushHistory - 推送历史记录
│   └── test_webhook_connection() - 连接测试
│
└── app/modules/node_hunter/
    └── node_hunter.py           # 修改
        └── +集成webhook_push
```

---

## 🔐 安全机制

### Webhook签名验证

**目的**: 防止非授权的数据推送

**算法**:
```python
# SpiderFlow端（发送者）:
message = json_payload + "." + timestamp
signature = HMAC-SHA256(message, shared_secret)

# viper-node-store端（接收者）:
expected = HMAC-SHA256(message, shared_secret)
assert signature == expected  # 验证失败返回401
```

**配置**:
```bash
# 两端必须设置相同的WEBHOOK_SECRET
export WEBHOOK_SECRET="spiderflow-viper-sync-2026"
```

---

## 🔄 工作流程

### 场景1: 检测完成推送

```
SpiderFlow完成检测
    ↓
生成签名 (payload + timestamp + secret)
    ↓
POST /webhook/nodes-update (包含签名)
    ↓
viper-node-store验证签名
    ↓
✅ 签名正确 → 更新本地数据库
❌ 签名错误 → 返回401 Unauthorized
```

### 场景2: Webhook失败兜底

```
Webhook推送失败 (网络问题/超时)
    ↓
最多重试3次，每次间隔5秒
    ↓
仍然失败 → 记录到推送历史
    ↓
viper-node-store定时轮询 (5分钟)
    ↓
✅ 轮询发现数据变更 → 同步新数据
```

### 场景3: 用户精确测速

```
用户点击[精确测速]
    ↓
前端显示对话框: "将下载50MB文件，消耗50MB流量"
    ↓
用户确认
    ↓
前端或后端开始下载真实文件
    ↓
记录下载时间和文件大小
    ↓
计算真实速度 = 文件大小 / 下载时间
    ↓
显示结果给用户
```

---

## 📊 流量统计

### 月流量估算（所有操作）

| 机制 | 单次流量 | 频率 | 月流量 | 说明 |
|-----|--------|------|--------|------|
| Webhook | ~100KB | 每次检测 (1/天) | ~3MB | 仅数据变更时 |
| 轮询 | ~100KB | 5分钟 | ~12-42MB | 289-869次/月 |
| 前端测速 | <1KB | 用户点击 | ~0MB | 可忽略 |
| 后端测速HEAD | <1KB | 用户点击 | ~0MB | 可忽略 |
| 精确测速 | 50-100MB | 用户选择 | 按需计费 | 用户可见消耗 |
| **总计** | - | - | **~30MB基础** | +精确测速按需 |

**Azure额度**: 100-200GB/月  
**我们使用**: ~30MB基础 + 精确测速按需 ✅ 完全在预算内

---

## 🛠️ 实现细节

### 1. Webhook Receiver (webhook_receiver.py)

**主要功能**:
- 监听 POST /webhook/nodes-update
- 验证HMAC-SHA256签名
- 合并新节点数据到本地DB
- 异步同步到Supabase/IPFS

**签名验证流程**:
```python
def verify_webhook_signature(payload_str, timestamp, signature):
    message = f"{payload_str}.{timestamp}"
    expected = HMAC-SHA256(message, secret)
    return timing_safe_compare(expected, signature)
```

**数据合并策略**:
```python
def merge_node_data(existing, new_nodes):
    # 按URL去重
    # 新节点覆盖旧节点（保留历史记录）
    # 维护同步历史
    return merged_data
```

### 2. Data Sync Module (data_sync.py)

**核心组件**:

**SyncState**: 追踪同步状态
```python
class SyncState:
    - last_webhook_time: 最后Webhook时间
    - last_poll_time: 最后轮询时间
    - last_sync_hash: 数据哈希
    - webhook_received_count: Webhook统计
    - poll_received_count: 轮询统计
```

**DataSyncScheduler**: 管理定时轮询
```python
class DataSyncScheduler:
    async def start()  # 启动5分钟轮询
    async def stop()   # 停止轮询
```

**变更检测**:
```python
def calculate_nodes_hash(nodes):
    # 对节点列表计算SHA256
    # 用于检测是否有新数据
    # 避免不必要的重复同步
```

### 3. FastAPI主应用 (app_fastapi.py)

**主要端点**:

| 端点 | 方法 | 说明 |
|-----|------|------|
| /api/nodes | GET | 获取节点列表（支持筛选） |
| /api/nodes/export | POST | 导出节点数据 |
| /webhook/nodes-update | POST | 接收Webhook推送 |
| /api/sync/status | GET | 获取同步状态 |
| /api/sync/poll-now | POST | 手动触发轮询 |
| /api/stats/summary | GET | 统计汇总 |
| /api/stats/top-nodes | GET | 排名靠前节点 |
| /api/nodes/precision-test | POST | 精确测速 |

### 4. SpiderFlow Webhook推送 (webhook_push.py)

**核心函数**:

```python
async def push_nodes_to_viper(nodes, event_type, total_count, verified_count):
    # 1. 构造Webhook负载
    payload = {
        "event_type": "nodes_updated",
        "timestamp": "2026-01-01T12:00:00Z",
        "nodes": nodes,
        "total_count": 150,
        "verified_count": 145
    }
    
    # 2. 生成签名
    timestamp, signature = generate_webhook_signature(payload)
    
    # 3. 发送到viper-node-store
    # 4. 支持重试 (最多3次)
    # 5. 记录推送历史
```

**使用方式**:
```python
# 在node_hunter.py检测完成后调用
from webhook_push import push_nodes_to_viper

await push_nodes_to_viper(
    nodes=verified_nodes,
    event_type="batch_test_complete",
    total_count=150,
    verified_count=145
)
```

---

## 🚀 部署步骤

### 第一步: 安装依赖

```bash
# viper-node-store
cd /Users/ikun/study/Learning/viper-node-store
pip install -r requirements.txt

# SpiderFlow (已包含)
cd /Users/ikun/study/Learning/SpiderFlow/backend
pip install -r requirements.txt
```

### 第二步: 配置环境变量

```bash
# 设置shared secret (必须两端一致)
export WEBHOOK_SECRET="spiderflow-viper-sync-2026"

# SpiderFlow端
export VIPER_WEBHOOK_URL="http://localhost:8002/webhook/nodes-update"

# viper-node-store端
export SPIDERFLOW_API_URL="http://localhost:8001"
export POLL_INTERVAL="300"  # 5分钟
```

### 第三步: 启动服务

```bash
# 终端1: viper-node-store API
cd /Users/ikun/study/Learning/viper-node-store
python -m uvicorn app_fastapi:app --host 0.0.0.0 --port 8002

# 终端2: SpiderFlow API
cd /Users/ikun/study/Learning/SpiderFlow/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 第四步: 测试连接

```bash
# 测试webhook连接
curl -X POST http://localhost:8002/webhook/test-connection

# 测试轮询同步
curl -X POST http://localhost:8002/api/sync/poll-now

# 获取同步状态
curl http://localhost:8002/api/sync/status
```

---

## 📝 配置示例

### SpiderFlow 环境变量 (.env)

```env
# Webhook推送配置
WEBHOOK_SECRET=spiderflow-viper-sync-2026
VIPER_WEBHOOK_URL=http://localhost:8002/webhook/nodes-update

# 其他配置...
```

### viper-node-store 环境变量 (.env)

```env
# 接收Webhook配置
WEBHOOK_SECRET=spiderflow-viper-sync-2026

# 轮询SpiderFlow配置
SPIDERFLOW_API_URL=http://localhost:8001
POLL_INTERVAL=300  # 秒（5分钟）

# 其他配置...
```

---

## 🧪 测试场景

### 测试1: Webhook推送成功

```bash
# 模拟SpiderFlow检测完成，推送10个节点
curl -X POST http://localhost:8002/webhook/nodes-update \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "nodes_updated",
    "timestamp": "2026-01-01T12:00:00Z",
    "nodes": [
      {
        "url": "vmess://...",
        "name": "SG节点",
        "country": "SG",
        "latency": 123.45,
        "speed": 45.67,
        "availability": 95.5,
        "protocol": "vmess"
      }
    ],
    "signature": "abc123..."
  }'
```

### 测试2: 轮询同步

```bash
# 手动触发轮询
curl -X POST http://localhost:8002/api/sync/poll-now

# 检查轮询结果
curl http://localhost:8002/api/sync/status
```

### 测试3: 节点查询和过滤

```bash
# 获取所有节点
curl http://localhost:8002/api/nodes

# 查询新加坡节点
curl "http://localhost:8002/api/nodes?country=SG"

# 查询速度≥50MB/s的节点
curl "http://localhost:8002/api/nodes?min_speed=50"
```

---

## ✅ 验收标准

- [x] Webhook接收器实现完成
- [x] 轮询同步机制实现完成
- [x] 签名验证机制实现完成
- [x] 本地数据库合并逻辑完成
- [x] FastAPI主应用完成
- [x] SpiderFlow集成ready
- [ ] 前端精确测速UI（下一步）
- [ ] 检测逻辑迁移完成（下一步）
- [ ] 用户测试和反馈
- [ ] 生产环境部署

---

## 📚 相关文档

- [数据同步架构设计](PHASE2_DATA_SYNC_DESIGN.md) - 详细设计文档
- [API参考](API_REFERENCE.md) - 完整API文档
- [Webhook集成指南](WEBHOOK_INTEGRATION_GUIDE.md) - 集成步骤
- [故障排除](TROUBLESHOOTING.md) - 常见问题解决

---

## 🎉 下一步

1. **前端精确测速UI** - 在NodeHunter.vue中添加[精确测速]按钮
2. **检测逻辑复制** - 将node_hunter逻辑复制到viper-node-store
3. **测试验证** - 全面测试数据同步流程
4. **文档完善** - 补充API文档和使用指南
5. **生产部署** - 在Azure上部署新的数据同步层

---

**状态**: 🔄 进行中  
**预计完成**: 2026-01-05  
**维护者**: 系统开发团队
