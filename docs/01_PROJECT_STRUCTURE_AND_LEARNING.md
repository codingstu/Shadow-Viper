# SpiderFlow 项目结构与学习记录

**最后更新**：2026-01-05  
**维护人**：AI Assistant + 开发团队  
**文档状态**：✅ 持续更新中

---

## 📑 目录

1. [整体架构](#整体架构)
2. [核心模块详解](#核心模块详解)
3. [技术栈与学习内容](#技术栈与学习内容)
4. [部署架构演变](#部署架构演变)
5. [学习总结](#学习总结)

---

## 整体架构

```
SpiderFlow (影流) - 全功能代理节点爬虫+检测系统
│
├── 📦 Frontend (Vue3 + Naive UI + Tailwind CSS)
│   ├── 节点猎手 - 实时爬虫+检测仪表盘
│   ├── 代理池 - 活跃节点实时显示
│   ├── 爬虫引擎 - 网页爬虫工具
│   ├── 数据精炼 - 数据处理工具
│   ├── AI中枢 - AI模型管理
│   ├── 网络状态 - 系统监控
│   └── 访客追踪 - 用户分析
│
├── 🔧 Backend (FastAPI + APScheduler)
│   ├── modules/
│   │   ├── node_hunter/           # 🔴 核心：节点爬虫+多层级检测
│   │   │   ├── node_hunter.py     # 主逻辑：爬取、检测、去重、同步
│   │   │   ├── clash_basic_check.py # Clash内核检测 (VMess/VLESS等)
│   │   │   ├── v2ray_check.py     # Xray内核检测 (Hysteria等)
│   │   │   ├── simple_availability_check.py # 快速可用性检测
│   │   │   ├── real_speed_test.py # 真实速度测试
│   │   │   ├── advanced_speed_test.py # 双地区测速 (Aliyun FC + CF Worker)
│   │   │   ├── config_generator.py # Clash配置生成
│   │   │   ├── parsers.py         # V2Ray/Clash格式解析
│   │   │   ├── supabase_helper.py # Supabase数据库同步
│   │   │   └── ... (其他辅助模块)
│   │   │
│   │   ├── proxy/                 # 代理池管理
│   │   ├── crawler/               # 网页爬虫
│   │   ├── cyber_range/           # 靶场服务
│   │   ├── eagle_eye/             # IP信息查询
│   │   ├── game/                  # 游戏相关
│   │   ├── ai_hub/                # AI模型管理
│   │   ├── system/                # 系统监控
│   │   └── visitor_tracker/       # 访客追踪
│   │
│   ├── core/
│   │   └── ai_hub.py              # AI接口集成 (Claude/GPT等)
│   │
│   ├── main.py                    # FastAPI主应用
│   └── requirements.txt            # 依赖管理
│
├── 🚀 Cloudflare Worker (边缘计算)
│   └── test-speed.js              # 全球双地区速度测试
│
└── 📄 Documentation
    ├── 01_PROJECT_STRUCTURE_AND_LEARNING.md (本文档)
    ├── 02_FIXES_AND_OPTIMIZATION_LOG.md    (修复优化记录)
    └── ... (其他参考文档)
```

---

## 核心模块详解

### 1. 节点猎手 (Node Hunter)

#### 核心流程

```
爬取阶段 (6h一次)
  ↓
获取订阅链接 → 并发爬取 → 格式解析 → 去重(host:port)
  ↓
检测阶段 (1h一次) - 三层级检测
  ↓
第1层: 云端快速过滤 (可选)
  ├─ Aliyun FC (国内节点)
  └─ Cloudflare Worker (海外节点)
  ↓
第2层: 本地Clash检测 (并发度5)
  ├─ 启动mihomo进程
  ├─ 通过127.0.0.1:port代理测试
  └─ 记录延迟+可用性
  ↓
第3层: 本地Xray检测 (并发度3)
  ├─ 启动xray进程
  ├─ 测试其他协议 (Hysteria等)
  └─ 补充Clash失败的节点
  ↓
速度测试 (双地区)
  ├─ 大陆: Aliyun FC
  └─ 海外: Cloudflare Worker
  ↓
同步阶段 (1h一次)
  └─ 上传验证通过的节点到 Supabase
```

#### 关键数据结构

```python
node = {
    'name': 'HK_Node_001',
    'host': '1.2.3.4',
    'port': 443,
    'protocol': 'vless',          # VMess/VLESS/Trojan/Shadowsocks
    'alive': True,                # 是否可用
    'availability_level': 'VERIFIED',  # VERIFIED/BASIC/UNAVAILABLE
    'latency': 50,                # 延迟(ms)
    'health_score': 95,           # 健康分(0-100)
    'speed': 85.5,                # 速度估算(MB/s)
    'mainland_score': 90,         # 大陆测速分
    'mainland_latency': 45,       # 大陆延迟
    'overseas_score': 92,         # 海外测速分
    'overseas_latency': 48,       # 海外延迟
    'country': 'HK',              # 国家识别
    'updated_at': '2026-01-05T17:00:00'
}
```

#### 关键函数

- `_test_nodes_with_new_system()` - 三层级检测主函数
- `check_nodes_clash()` - Clash内核检测批处理
- `check_nodes_v2ray()` - Xray内核检测批处理
- `upload_to_supabase()` - Supabase数据库同步

---

### 2. 多协议支持

#### Clash兼容协议
- VMess (含ws/tcp/tls)
- VLESS (含ws/tcp/reality)
- Trojan
- Shadowsocks (SS)
- SOCKS5
- HTTP/HTTPS

#### Xray专属协议
- Hysteria/Hysteria2
- Wireguard
- TUIC
- NaiveProxy

#### 优先级策略
1. 优先用Clash (启动快，并发高)
2. Clash失败的节点用Xray补充
3. 仅Xray支持的协议直接用Xray

---

## 技术栈与学习内容

### 后端 (Python + FastAPI)

#### 学习重点

1. **异步编程**
   - `asyncio` 并发任务调度
   - `aiohttp`/`httpx` 异步HTTP客户端
   - **关键学习**：在 httpx 0.25.2 中，使用 `proxy="..."` 而非 `proxies={}`

2. **进程管理**
   - `asyncio.create_subprocess_exec()` 启动子进程
   - 临时文件管理 (`tempfile`)
   - 优雅的进程清理 (try-finally-kill)

3. **配置管理**
   - YAML配置文件 (Clash/Xray)
   - JSON配置文件
   - 环境变量管理 (.env)

4. **数据库集成**
   - Supabase (PostgreSQL SaaS)
   - 异步数据操作
   - 错误重试机制

5. **定时调度**
   - APScheduler 后台任务
   - cron表达式配置
   - 任务冲突防护

6. **日志管理**
   - 分级日志 (DEBUG/INFO/WARNING/ERROR)
   - 文件+控制台输出
   - 生产环境可观察性

#### 核心依赖版本

```
fastapi==0.126.0              # Web框架
httpx==0.25.2                 # 异步HTTP (关键：proxy参数兼容性)
aiohttp==3.13.2               # 异步HTTP备选
APScheduler==3.11.1           # 定时调度
pydantic==2.12.5              # 数据验证
python-dotenv==1.2.1          # 环境变量
supabase==1.x                 # Supabase客户端
```

---

### 前端 (Vue3 + TypeScript)

#### 学习重点

1. **Vue3 Composition API**
   - `ref`/`reactive`/`computed`
   - `watchEffect`/`watch` 响应式
   - 生命周期钩子

2. **WebSocket实时通信**
   - 实时接收后端日志
   - 进度更新推送
   - 自动重连机制

3. **组件化架构**
   - 拆分大型组件
   - Props/Emits通信
   - 插槽(Slots)复用

4. **状态管理**
   - Pinia/Vuex全局状态
   - 跨组件通信

5. **UI框架集成**
   - Naive UI 组件库
   - Tailwind CSS 样式
   - 响应式设计

#### 核心库版本

```json
"vue": "^3.3.0",
"naive-ui": "^2.34.0",
"tailwindcss": "^3.3.0",
"vite": "^4.4.0"
```

---

### 云平台集成

#### Cloudflare Workers (边缘计算)

**学习内容**：
- JavaScript 异步编程 (Promises/async-await)
- 分布式计算
- CDN流量优化

**优势**：
- ✅ 全球200+数据中心
- ✅ 零冷启动
- ✅ 自动扩展
- ✅ 免费额度充足 (10万请求/天)

#### Supabase (数据库SaaS)

**学习内容**：
- PostgreSQL基础SQL
- 实时数据库 (Realtime)
- 行级安全策略 (RLS)
- 异步客户端使用

---

## 部署架构演变

### V1: 本地全检测 (2024年)
```
SpiderFlow Backend (Azure VM)
  ├─ 爬虫
  ├─ Clash检测
  └─ 速度测试 ❌ 流量爆表 (150GB/月)
```

**问题**：
- ❌ Azure免费账户限制（100-200GB流量/月）
- ❌ 内存OOM（1GB不足）
- ❌ 流量成本高

### V2: 分离速度测试 (2026-01-01)

```
Cloudflare Worker (全球边缘)
  ├─ 大陆测速 (Aliyun FC)
  └─ 海外测速 (Cloudflare Worker)
         ↑
      回调
         ↑
SpiderFlow Backend (Azure VM)
  ├─ 爬虫
  ├─ Clash/Xray检测
  └─ 双地区速度测试结果收集
```

**优势**：
- ✅ 节省主服务器流量 (从1GB/次→100MB)
- ✅ 响应更快 (边缘节点更近)
- ✅ 天然支持多地区
- ✅ 成本更低

---

## 学习总结

### 开发过程中的关键学习点

#### 1. 异步编程的坑

**问题**：一开始混用同步/异步代码
```python
# ❌ 错误：同步操作阻塞事件循环
response = requests.get(url)  # 阻塞

# ✅ 正确：全异步
response = await client.get(url)  # 非阻塞
```

**学习**：异步不仅是为了速度，更是为了不阻塞其他任务。

#### 2. httpx 版本兼容性

**问题**：不同版本的参数名差异
```python
# httpx 0.24及之前：支持 proxies
async with httpx.AsyncClient(proxies={...})

# httpx 0.25+：不支持 proxies，用 proxy
async with httpx.AsyncClient(proxy="...")

# httpx 0.25+ 如果需要HTTP/HTTPS分别：用 mounts
async with httpx.AsyncClient(mounts={
    "http://": httpx.AsyncHTTPTransport(proxy="..."),
    "https://": httpx.AsyncHTTPTransport(proxy="..."),
})
```

**学习**：总是检查依赖版本，不要假设向前/向后兼容。

#### 3. 进程管理

**问题**：Clash/Xray进程没有正确清理
```python
# ❌ 错误：进程泄漏
process = await asyncio.create_subprocess_exec(...)
# 没有 kill

# ✅ 正确：使用try-finally
process = None
try:
    process = await asyncio.create_subprocess_exec(...)
    ...
finally:
    if process and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except:
            process.kill()
```

**学习**：进程资源必须显式清理，不能依赖GC。

#### 4. 云平台选择

**问题**：Azure免费账户达到流量限制
**解决**：选择流量优化的方案（Cloudflare Workers）

**学习**：
- 不同云平台有不同优势（计算/存储/流量）
- 要根据瓶颈选择对应的解决方案
- 分布式思想：把任务下沉到更靠近目标的地方

#### 5. 数据库同步

**问题**：Supabase凭证管理、环境变量加载、异步操作
```python
# 学到的最佳实践
1. .env文件用绝对路径加载
2. 异步操作要用 await
3. 凭证不要硬编码，用环境变量
4. 写入权限需要配置RLS规则
```

---

## 关键文件索引

| 文件 | 功能 | 关键难点 |
|------|------|--------|
| `node_hunter.py` | 爬虫+检测主逻辑 | 三层级检测协调、去重、同步 |
| `clash_basic_check.py` | Clash内核检测 | 进程启动、临时配置、代理连接 |
| `v2ray_check.py` | Xray内核检测 | 配置生成、JSON序列化 |
| `advanced_speed_test.py` | 双地区测速 | 异步HTTP、流式下载、速度计算 |
| `supabase_helper.py` | 数据库同步 | 环境变量、异步操作、凭证管理 |
| `real_speed_test.py` | 实时速度测试 | 代理配置、流式下载 |

---

## 总结

SpiderFlow 是一个**全功能、生产级别**的代理节点爬虫+检测系统。通过这个项目，学到了：

✅ **后端**：异步编程、进程管理、定时调度、数据库集成  
✅ **前端**：Vue3、WebSocket、实时通信、UI组件库  
✅ **云平台**：Cloudflare Workers、Supabase、多地区部署  
✅ **架构**：分布式思想、性能优化、成本控制  
✅ **工程**：日志管理、错误处理、资源清理、环境隔离  

**核心原则**：
- 优先用异步，不要阻塞
- 资源用完必须清理
- 凭证不要硬编码
- 日志要详细（便于调试）
- 定期验证部署的有效性
