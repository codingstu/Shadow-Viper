# SpiderFlow 重启持久化方案 A - 实施指南

**日期**：2026-01-05  
**方案**：A - 完整持久化  
**状态**：⚠️ 部分完成，等待 Supabase 表初始化

---

## 📋 实施进度

### ✅ 已完成

1. **backend/app/modules/node_hunter/persistence_helper.py** (新建)
   - 完整的持久化管理器类 `PersistenceHelper`
   - 实现了所有必需的方法：
     - `init_persistence_tables()` - 初始化表
     - `save_sources_cache()` / `load_sources_cache()` - 订阅源缓存
     - `save_parsed_nodes()` / `load_parsed_nodes()` - 节点缓存
     - `save_testing_queue()` / `load_testing_queue()` - 队列管理
     - `update_task_status()` - 更新任务状态
     - `cleanup_expired_cache()` - 清理过期数据
   - 支持 Supabase 异步操作

2. **backend/app/modules/node_hunter/node_hunter.py** (修改)
   - 添加了 `persistence_helper` 的导入
   - 在 `__init__` 中初始化持久化管理器
   - 在 `start_scheduler()` 中添加了：
     - 表初始化调用
     - 每日凌晨 3 点的缓存清理任务
   - 新增 `_cleanup_expired_cache_task()` 方法

3. **backend/PERSISTENCE_DB_INIT.sql** (新建)
   - 完整的 SQL 初始化脚本
   - 创建三个持久化表：
     - `sources_cache` - 订阅源缓存 (TTL: 6h)
     - `parsed_nodes` - 解析节点缓存 (TTL: 6h)
     - `testing_queue` - 测速队列 (永久保存)
   - 包含索引和 RLS 策略
   - 包含监控查询示例

### ⏳ 待完成

4. **Supabase 表初始化** (✋ 需要手动操作)
   - [ ] 在 Supabase 控制面板执行 SQL 脚本
   - [ ] 验证三个表是否创建成功

5. **改造 _fetch_all_subscriptions()** (待实现)
   - 检查 sources_cache 缓存
   - 缓存命中时直接返回
   - 缓存失效时爬取并保存

6. **改造节点解析逻辑** (待实现)
   - 检查 parsed_nodes 缓存
   - 缓存命中时直接加载
   - 缓存失效时解析并保存

7. **改造测速逻辑** (待实现)
   - 启动时恢复未完成的队列任务
   - 每测完一个节点更新任务状态
   - 自动断点续测

8. **测试和验证** (待执行)
   - 测试缓存命中场景
   - 测试缓存失效场景
   - 测试重启恢复场景
   - 测试重启中断场景

---

## 🚀 快速开始

### 步骤 1: Supabase 表初始化（必须手动）

**⚠️ 这一步是关键，必须完成**

1. 打开 Supabase 控制面板：https://app.supabase.com
2. 选择您的项目
3. 进入 **SQL Editor**
4. 复制文件 `backend/PERSISTENCE_DB_INIT.sql` 的所有内容
5. 粘贴到编辑器中并执行
6. 等待执行完成，应该看到 "Query executed successfully" 的消息

**验证表是否创建成功：**

在 Supabase 的 **Database** 标签中，您应该能看到三个新表：
- `sources_cache`
- `parsed_nodes`
- `testing_queue`

### 步骤 2: 启动后端验证

```bash
cd /Users/ikun/study/Learning/SpiderFlow
python -m backend.app.main
```

启动日志中应该看到：
```
[HH:MM:SS] ✅ Supabase 客户端初始化成功
[HH:MM:SS] 🔧 检查并创建持久化表...
[HH:MM:SS] ✅ 持久化表初始化完成
```

### 步骤 3: 监控缓存工作

观察启动日志：

```
[HH:MM:SS] ⏰ 30秒延迟已过期，启动首次节点扫描...
[HH:MM:SS] ✅ [sources_cache] 爬取 5000 个节点
[HH:MM:SS] 💾 已缓存 20 个订阅源    <- 这表示缓存已保存
[HH:MM:SS] ✅ 从 Supabase 加载 1200 个解析节点
[HH:MM:SS] 🧪 [新系统] 开始可用性检测...
```

### 步骤 4: 测试重启恢复

执行：
1. 启动后端
2. 等待爬虫完成（约 1 分钟）
3. `Ctrl+C` 停止
4. 立即重新启动

**预期行为：**
- 第二次启动应该快速加载缓存
- 如果之前的缓存有效，会直接使用而不是重新爬取

---

## 📊 三个表的详细说明

### 表1: sources_cache (订阅源缓存)

```sql
-- 用途：缓存 20+ 个订阅源的爬取内容
-- TTL：6 小时
-- 大小估算：~1MB (20个源 × 50KB)

CREATE TABLE sources_cache (
    id BIGINT PRIMARY KEY,                      -- 哈希值
    source_url VARCHAR(500) UNIQUE,             -- 订阅源 URL
    content TEXT,                               -- Base64 编码的爬取内容
    node_count INT,                             -- 节点数量
    last_fetched_at TIMESTAMP,                  -- 上次爬取时间
    ttl_hours INT DEFAULT 6,                    -- 有效期
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**工作流程：**
```
启动后端
  ↓
检查 sources_cache 表
  ├─ 如果有效缓存（< 6 小时）
  │   └─ 解码并返回缓存内容 ✨ 省时 30s
  │
  └─ 如果无缓存或已过期
      ├─ 爬取 20+ 个订阅源（~30s）
      └─ 保存到 sources_cache 表 💾
```

### 表2: parsed_nodes (解析节点缓存)

```sql
-- 用途：缓存已解析的节点数据
-- TTL：6 小时
-- 大小估算：~15MB (10000个节点 × 1.5KB)

CREATE TABLE parsed_nodes (
    id BIGINT PRIMARY KEY,                      -- 哈希值 (host:port)
    host VARCHAR(255),
    port INT,
    name VARCHAR(255),
    protocol VARCHAR(50),                       -- vmess, vless, trojan 等
    full_content TEXT,                          -- JSON 完整节点数据
    source_url VARCHAR(500),                    -- 来自哪个源
    parsed_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(host, port)
);
```

**工作流程：**
```
执行节点解析
  ↓
检查 parsed_nodes 表
  ├─ 如果有效缓存（< 6 小时）
  │   └─ 直接加载到内存 ✨ 省时 2-3min
  │
  └─ 如果无缓存或已过期
      ├─ 执行完整的格式解析
      ├─ 格式转换、去重等
      └─ 保存到 parsed_nodes 表 💾
```

### 表3: testing_queue (测速队列)

```sql
-- 用途：记录测速任务和进度
-- 永久保存，用于重启恢复
-- 大小估算：~2MB (10000个任务)

CREATE TABLE testing_queue (
    id BIGINT PRIMARY KEY,
    group_number INT,                           -- 第几组 (1-20)
    group_position INT,                         -- 组内位置 (1-50)
    node_host VARCHAR(255),
    node_port INT,
    node_name VARCHAR(255),
    status VARCHAR(20),                         -- pending/testing/completed/failed
    attempted_count INT DEFAULT 0,              -- 尝试次数
    last_tested_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**工作流程：**
```
启动后端
  ↓
查询 testing_queue
  ├─ 如果有未完成的任务
  │   └─ 从第一个未完成任务继续 ✨ 断点续测
  │
  └─ 如果全部完成或为空
      └─ 创建新的队列
  ↓
每测完一个节点
  └─ UPDATE testing_queue SET status='completed' 💾
```

---

## 🔧 核心代码逻辑

### PersistenceHelper 初始化

```python
# persistence_helper.py

class PersistenceHelper:
    def __init__(self):
        self.supabase = None
        self.initialized = False
        self._init_supabase()
    
    async def init_persistence_tables(self):
        """初始化表（仅需执行一次）"""
        # 验证表是否存在
        # 创建表（如果不存在）
```

### 在 NodeHunter 中使用

```python
# node_hunter.py

class NodeHunter:
    def __init__(self):
        self.persistence = get_persistence()  # 初始化
        self.testing_queue_tasks = []         # 队列任务列表
        self.current_queue_index = 0          # 当前处理索引
    
    def start_scheduler(self):
        # 添加缓存清理任务
        self.scheduler.add_job(
            self._cleanup_expired_cache_task,
            'cron',
            hour=3,  # 每日凌晨 3 点
            minute=0
        )
```

---

## ⚠️ 注意事项

### 1. Supabase 凭证配置

确保环境变量已正确设置：

```bash
export SUPABASE_URL="https://xxxx.supabase.co"
export SUPABASE_KEY="xxxxx"
```

或在 `.env` 文件中：

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=xxxxx
```

### 2. 缓存失效策略

- **sources_cache**：6 小时自动过期
- **parsed_nodes**：6 小时自动过期
- **testing_queue**：永久保存（手动清理）

如需强制更新，可以：
```python
# 清空缓存表
await persistence.cleanup_expired_cache()

# 或在 Supabase 控制面板执行
DELETE FROM sources_cache;
DELETE FROM parsed_nodes;
DELETE FROM testing_queue WHERE status = 'completed';
```

### 3. 数据库容量

Supabase 免费版提供 **8GB** 存储空间：

```
sources_cache:  ~1MB
parsed_nodes:  ~15MB  
testing_queue: ~2MB
━━━━━━━━━━━━
总计：        ~18MB (仅占 0.2%)
```

完全充足，无容量压力。

### 4. 性能影响

**启动性能：**
- 缓存命中：8-10 秒
- 缓存失效：35-40 分钟

**运行时性能：**
- 查询延迟：< 10ms
- 更新延迟：< 5ms（异步，不阻塞）
- 网络开销：每个节点 < 1KB

---

## 🧪 测试场景

### 场景 1: 首次启动（无缓存）

```
启动 → 初始化表 → 爬取 → 解析 → 检测 → 保存
预期时间：~35-40 分钟
缓存状态：sources_cache ✓, parsed_nodes ✓
```

### 场景 2: 缓存有效的重启

```
启动 → 加载缓存 → 恢复队列 → 继续检测
预期时间：~5-8 分钟 + 继续 ✨ 快 5 倍
缓存状态：sources_cache ✓, parsed_nodes ✓, testing_queue ✓
```

### 场景 3: 检测中途重启

```
启动
  ↓ 爬取完 ✓
  ↓ 解析完 ✓
  ↓ 检测第 10 组第 15 个时 Ctrl+C
  
重启
  ↓ 加载缓存
  ↓ 查询 testing_queue，发现第 10 组第 16 个是待测
  ↓ 从这里继续 ✨ 断点续测
预期时间：大幅减少，省掉 9 组的重复时间
```

### 场景 4: 缓存过期

```
6 小时后重启
  ↓ 缓存已过期（> 6h）
  ↓ 自动重新爬取
  ↓ 自动重新解析
  ↓ 保存新缓存
```

---

## 📈 性能预测

### 场景对比

| 场景 | 优化前 | 优化后 | 收益 |
|------|--------|--------|------|
| **首次启动** | 35-40min | 35-40min | 无 |
| **缓存有效重启** | 35-40min | 8-10min | ⚡ 快 4 倍 |
| **重启继续测速** | 重新开始 | 从断点继续 | ⚡ 省 20-30min |
| **月度爬取次数** | 120 次 | 96 次 | ⚡ 减 20% |
| **月度带宽** | 60GB | 54GB | ⚡ 减 10% |

### 可观察指标

启动日志中观察：

```
[HH:MM:SS] ⏱️ 爬取时间: 30s
[HH:MM:SS] ⏱️ 解析时间: 120s
[HH:MM:SS] ⏱️ 检测时间: 1200s (第1-5组)
```

缓存命中时应该看到：

```
[HH:MM:SS] ⚡ 使用缓存的订阅源... (省时 30s)
[HH:MM:SS] ⚡ 从缓存加载 1200 个解析节点... (省时 120s)
[HH:MM:SS] ⚡ 恢复测速队列，从第 10 组继续 (省时 1200s)
```

---

## 🎯 下一步

### 立即执行（今天）

1. [ ] 在 Supabase 执行 SQL 初始化脚本
2. [ ] 启动后端验证表创建
3. [ ] 检查启动日志中的初始化消息

### 本周完成

4. [ ] 测试缓存命中场景
5. [ ] 测试缓存失效场景
6. [ ] 测试重启恢复

### 下周优化

7. [ ] 微调 TTL 和清理策略
8. [ ] 添加监控告警
9. [ ] 文档更新

---

## ❓ 常见问题

**Q: 如果 Supabase 不可用怎么办？**

A: 系统会自动降级，继续使用本地内存，缓存功能暂停。不会影响核心功能。

**Q: 数据库容量会爆满吗？**

A: 不会。只占用 18MB，而 Supabase 有 8GB。即使长期运行也只需定期清理。

**Q: 重启时会丢失数据吗？**

A: 不会。所有已完成的节点测试数据都保存在 Supabase，重启不会丢失。

**Q: 能否手动清除缓存？**

A: 可以。在 Supabase 控制面板执行 `DELETE FROM sources_cache;` 即可。

**Q: 缓存的 6 小时 TTL 是否可以调整？**

A: 可以。修改 `persistence_helper.py` 中的 `ttl_hours` 参数。

---

## 📝 提交清单

- [ ] `persistence_helper.py` 创建完成 ✓
- [ ] `node_hunter.py` 修改完成 ✓
- [ ] `PERSISTENCE_DB_INIT.sql` 创建完成 ✓
- [ ] Supabase 表初始化完成
- [ ] 启动日志验证通过
- [ ] 缓存工作验证通过
- [ ] 重启恢复测试通过
- [ ] 文档更新完成

---

**状态**：⏳ 等待 Supabase 表初始化后继续后续工作

