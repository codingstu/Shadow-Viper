# SpiderFlow 项目架构与功能说明

**最后更新**：2026-01-01 Round 5 (CF Worker 迁移)  
**版本**：1.0

---

## 📐 整体架构

```
SpiderFlow/
├── backend/                 # 后端服务 (FastAPI + APScheduler)
│   ├── app/main.py         # 主应用入口、路由配置
│   ├── app/modules/
│   │   ├── node_hunter/    # 🔴 核心模块：节点爬虫 & 检测引擎
│   │   ├── proxy/          # 代理池管理
│   │   ├── crawler/        # 爬虫引擎
│   │   └── ... (其他功能模块)
│   └── requirements.txt
│
├── frontend/                # 前端服务 (Vue3 + Naive UI)
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   └── components/
│   │       ├── NodeHunter/NodeHunter.vue  # 🔴 节点猎手主界面
│   │       └── ... (其他组件)
│   └── package.json
│
└── 文档/
    ├── PROJECT_ARCHITECTURE.md      # 本文档
    ├── CHANGELOG.md                  # 改动历史
    └── API_REFERENCE.md              # API 参考
```

---

## 🎯 核心功能

### 1. **节点猎手（NodeHunter）**

#### 后端职责 (`backend/app/modules/node_hunter/node_hunter.py`)
- **节点爬取**：从多个订阅源并发爬取节点（V2Ray/Clash/纯文本格式）
- **节点检测**：使用 Clash + Xray 进行活性检测，记录延迟、速度、是否可用
- **国家识别**：通过名称、IP、API 调用识别节点所属国家/地区
- **缓存管理**：将验证通过的节点存到 `verified_nodes.json`（Top 150 个）
- **定时调度**：每 6h 爬虫、1h 检测、1h 同步一次

#### 前端职责 (`frontend/src/components/NodeHunter/NodeHunter.vue`)
- **实时仪表盘**：显示活跃节点数、检测进度、下次扫描时间
- **节点列表**：按国家/地区分组，支持展开/折叠、排序、搜索
- **显示控制**：
  - Socks/HTTP 显示开关（默认隐藏）
  - 中国节点显示开关（默认隐藏、默认折叠）
- **系统日志**：实时显示后端检测日志，智能滚动（不干扰用户阅读）
- **节点操作**：复制、二维码、单个测速、导入 Clash

---

## 🔄 工作流程

### 扫描流程
```
┌─────────────────────────────────────────────────────────┐
│ 1. 定时触发（或用户点击"扫描"）                           │
└────────────────┬────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 2. 爬虫阶段 (_fetch_all_subscriptions + _fetch_china_nodes)
│    • 从 20+ 订阅源并发爬取                                │
│    • 解析 V2Ray/Clash 配置                               │
│    • 提取必要字段（host, port, protocol, etc）           │
└────────────────┬────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 3. 入队到待检测队列 (pending_nodes_queue)               │
│    • 去重（相同 host:port 只保留一份）                   │
│    • 字段规范化                                          │
└────────────────┬────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 4. 批量检测阶段 (_batch_test_pending_nodes)             │
│    • 使用 Clash 进行活性检测（HTTP 502/超时判断）        │
│    • 并发度 5-10，单节点 10s 超时                        │
│    • 记录延迟、检测状态                                   │
└────────────────┬────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 5. 结果保存和分类                                        │
│    • 活跃节点：加入 self.nodes                           │
│    • 失败节点：加入重试队列，最多重试 3 次               │
│    • 持久化：Top 150 个节点到 verified_nodes.json        │
└────────────────┬────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 6. 前端更新                                              │
│    • 后端通过 API 返回节点列表（已过滤）                 │
│    • 前端按国家分组、展开/折叠、渲染                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🌍 国家地区识别流程

### 三层识别逻辑

```
节点国家字段值
    ▼
├─ 正规化 (normalize_country)
│  ├─ 检查是否 2 字母代码 (如 "TR")  ✓ 直接返回
│  ├─ NAME_TO_CODE 子串匹配            ✓ 返回对应代码
│  └─ 未匹配 → 继续第二层
│
├─ IP 查询 (_get_country_code_from_ip)
│  ├─ 缓存检查                        ✓ 返回缓存
│  ├─ 调用 ipapi.co API（2s 超时）    ✓ 返回结果
│  └─ 超时/失败 → 继续第三层
│
├─ 节点名称推断 (_guess_country_from_name)
│  ├─ 60+ 国家关键词匹配
│  │  ├─ 包含缩写 (TR, IT, DE)
│  │  ├─ 包含全名 (Turkey, Italy)
│  │  ├─ 包含中文 (土耳其, 意大利)
│  │  ├─ 包含城市 (Istanbul, Milan)
│  │  └─ 包含机场代码 (IST, MXP)
│  ├─ 正则提取国家代码 (如 (TR) → TR)
│  └─ 未匹配 → 返回 UNK
│
└─ UNK (未知区域)
```

### 关键字列表覆盖范围

| 地区 | 国家 | 示例 |
|------|------|------|
| 亚洲 | 中国、香港、台湾、日本、新加坡、韩国、泰国、越南、印度等 | CN, HK, JP, SG, TH, VN, IN |
| 中东 | 土耳其、阿联酋、沙特、以色列等 | TR, AE, SA, IL |
| 欧洲 | 英国、德国、法国、意大利、西班牙、俄罗斯等 | GB, DE, FR, IT, ES, RU |
| 北美 | 美国、加拿大、墨西哥 | US, CA, MX |
| 南美 | 巴西、阿根廷、智利等 | BR, AR, CL |
| 大洋洲 | 澳洲、新西兰 | AU, NZ |
| 非洲 | 南非、埃及、尼日利亚 | ZA, EG, NG |

---

## 🎛️ 显示控制开关

### 后端状态管理

```python
class NodeHunter:
    def __init__(self):
        self.show_socks_http = False    # 默认隐藏 Socks/HTTP
        self.show_china_nodes = False   # 默认隐藏中国节点
```

### API 端点

| 方法 | 端点 | 参数 | 功能 |
|------|------|------|------|
| GET | `/nodes/socks_http_status` | - | 获取 Socks/HTTP 显示状态 |
| POST | `/nodes/toggle_socks_http` | `show: bool` | 切换显示状态 |
| GET | `/nodes/china_nodes_status` | - | 获取中国节点显示状态 |
| POST | `/nodes/toggle_china_nodes` | `show: bool` | 切换显示状态 |
| GET | `/api/nodes` | `show_socks_http`, `show_china_nodes` | 获取过滤后的节点列表 |

### 前端状态管理

```javascript
const showSocksHttp = ref(false);       // 当前状态
const showChinaNodes = ref(false);      // 当前状态
const expandedGroups = ref({});         // 每个国家分组的展开/折叠状态

// 初始化：从后端加载状态
await fetchToggleStatus();

// 切换时：同时更新本地状态 + 调用后端 API
async function toggleSocksHttp(value) {
  showSocksHttp.value = value;
  await api.post('/nodes/toggle_socks_http', null, { params: { show: value } });
  fetchStats();  // 刷新列表
}
```

---

## 📊 数据结构

### 节点对象 (Node) - ✅ Round 4 真实速度测试

```json
{
  "id": "host:port",
  "protocol": "vmess|vless|ss|trojan|socks5|http",
  "host": "1.2.3.4",
  "port": 8080,
  "country": "US",
  "name": "VMESS-US-Server-1",
  "delay": 45,
  "speed": 67.30,
  "alive": true,
  "test_results": {
    "total_score": 95,
    "tcp_ping_ms": 45,
    "connection_time_ms": 48,
    "is_alive": true,
    "last_check_time": "2025-12-31T23:30:00"
  }
}
```

**字段说明**：

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `delay` | int | TCP Ping | **真实 TCP 延迟（毫秒）**，±5ms 精度。未测试时为 -1 |
| `speed` | float | 下载测试 | **真实下载速度（MB/s）**，基于 10MB Cloudflare 文件下载。未测试时为 0 |
| `alive` | bool | Clash 检测 | 节点是否活跃（可连接） |
| `test_results` | object | 诊断数据 | 详细的网络诊断结果对象 |

**速度测试实现**（Round 4 优化）：
- 🟢 **初始化**：`delay=-1, speed=0`（表示未测试）
- 🟡 **自动测试**：后台批量扫描时调用 `test_node_network()` 获取延迟
- 🔵 **用户手动测试**：点击 [测试] 按钮时：
  1. TCP Ping → 获取真实延迟 `delay`
  2. 代理下载 10MB 文件 → 获取真实速度 `speed`
  3. 缓存结果，避免重复测试
- 🔴 **失败处理**：
  - 节点无法连接 → `alive=false, delay=-1, speed=0`
  - 速度测试超时 → 自动降级使用基于延迟的估计算法

---

### 分组对象 (Group)

```json
{
  "group_name": "US",
  "nodes": [
    { /* node object */ },
    { /* node object */ }
  ]
}
```

---

## 📡 通信模式

### 初始化
```
前端启动
  ↓ GET /nodes/socks_http_status
  ↓ GET /nodes/china_nodes_status
后端返回切换状态
  ↓ GET /api/nodes (with params)
前端接收 + 分组 + 渲染
```

### 轮询更新
```
每 3 秒
  ↓ GET /nodes/stats (获取检测日志、下次扫描时间)
  ↓ GET /api/nodes (获取节点列表)
前端自动更新列表 + 日志
```

### 用户交互
```
用户切换开关 → POST /nodes/toggle_xxx → 后端更新状态
                                    ↓
                            GET /api/nodes（刷新列表）
前端显示新的节点列表（已过滤）
```

---

## 🔧 技术栈

### 后端
- **Framework**：FastAPI
- **并发**：asyncio + aiohttp
- **调度**：APScheduler
- **检测**：Clash + Xray
- **缓存**：JSON 文件
- **国家识别**：ipapi.co API

### 前端
- **框架**：Vue3
- **UI**：Naive UI
- **HTTP**：axios
- **样式**：Tailwind CSS

---

## 📝 文件索引

| 文件 | 功能 | 最后更新 |
|------|------|---------|
| `backend/app/modules/node_hunter/node_hunter.py` | 核心爬虫+检测引擎 | 2025-12-31 |
| `backend/app/main.py` | API 路由+过滤逻辑 | 2025-12-31 |
| `frontend/src/components/NodeHunter/NodeHunter.vue` | 仪表盘+节点列表 | 2025-12-31 |
| `CHANGELOG.md` | 所有改动历史 | 2025-12-31 |
| `API_REFERENCE.md` | API 端点详细文档 | 2025-12-31 |

---

## 🚀 快速启动

### 启动后端
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 启动前端
```bash
cd frontend
npm install
npm run dev
```

---

## 📌 重要概念

- **爬虫周期**：6 小时一次，仅负责爬取，不检测
- **检测周期**：1 小时一次，对队列中的节点进行活性检测
- **检测超时**：单节点 10 秒，超时判定为失败
- **重试机制**：失败的节点会重新加入队列，最多重试 3 次
- **缓存策略**：Top 150 个通过检测的节点存到本地，启动时加载
- **国家识别**：优先级 → 规范化 > IP查询 > 名称推断
