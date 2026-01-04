# SpiderFlow 重启持久化方案 - 可行性分析

**日期**：2026-01-05  
**分析人**：AI Assistant  
**状态**：📋 讨论中（待您反馈）

---

## 目录

1. [问题分析](#问题分析)
2. [当前架构](#当前架构)
3. [建议方案](#建议方案)
4. [可行性评估](#可行性评估)
5. [实现成本](#实现成本)
6. [性能影响](#性能影响)
7. [风险分析](#风险分析)
8. [替代方案](#替代方案)
9. [建议决策](#建议决策)

---

## 问题分析

### 您提出的问题

> 重启后，扫描节点状态变为重新开始获取所有数据源，然后解析节点，最后重新分组测速。
> 比如重启时检测到第10组的第15个节点，重启后会从第一组重新开始。
> 这样效率太低。

### 核心痛点

1. **数据重复获取**
   - 每次重启都要重新爬取所有订阅源
   - 订阅源数据已经过滤和去重，重复下载浪费带宽和时间
   - 代码：`_fetch_all_subscriptions()` 每次都完整执行

2. **节点重复解析**
   - 已经解析过的 50K+ 个节点，重启后再解析一遍
   - 格式转换、URL 解码、去重等都要重复
   - 时间成本：~3-5 分钟

3. **测速进度丢失**
   - 测速到第 10 组第 15 个时重启
   - 重启后完全忘记进度，从第 1 组重新开始
   - 20 组 × 50 个节点 = 1000 个，每个需要多次核验
   - **实际成本**：丢失 10×50 = 500 个已测节点的进度

4. **分布式测速的重复消耗**
   - Clash 检测：启动 mihomo 进程（~200ms）
   - Xray 检测：启动 xray 进程（~200ms）
   - 大陆/海外速度测试：网络 RTT 延迟

---

## 当前架构

### 数据流

```
启动时的流程 (当前)：
1️⃣ 启动后端进程
   ↓
2️⃣ _load_nodes_from_file() 加载本地缓存
   ├─ 从 verified_nodes.json 快速加载 ~150 个高质量节点
   └─ 启动后台任务从 Supabase 加载最近测试的节点 ~200 个
   ↓
3️⃣ _fetch_all_subscriptions() 执行
   ├─ 并发请求 20+ 个订阅源 (~30s)
   ├─ 解析所有格式 (VMess/VLESS/Trojan/Hysteria等)
   ├─ 去重 (按host:port)
   └─ 结果：5000-10000 个原始节点
   ↓
4️⃣ _test_nodes_with_new_system() 开始检测
   ├─ 第1层：云端过滤 (可选)
   ├─ 第2层：Clash 检测 (5 并发)
   ├─ 第3层：Xray 检测 (3 并发)
   ├─ 速度测试 (大陆+海外)
   └─ 分组显示 (第1组→第20组)
   ↓
5️⃣ 若此时重启 (比如在第 10 组)
   └─ 1-4 步完全重复 ❌ 效率低下

测速任务队列 (当前)：
┌─────────────────────────────────────────────────────────┐
│ 第1组  │ 第2组  │ 第3组  │...│ 第10组 │ 第11组 │...  │
│ 50个   │ 50个   │ 50个   │   │ 50个   │ 50个   │     │
│        │        │        │   │ ❌重启 │        │     │
└─────────────────────────────────────────────────────────┘
  ✅完成  ✅完成   ✅完成   ... ⚠️未完   ❌丢失   ❌丢失
  
重启后：从第1组重新开始，第1-10组浪费测试时间
```

### 现有缓存机制

| 缓存层级 | 位置 | 内容 | 重启后 |
|---------|------|------|--------|
| L1 | 内存 (self.nodes) | 所有解析的节点 | ❌ 清空 |
| L2 | verified_nodes.json | Top 150 高质量节点 | ✅ 保留 |
| L3 | Supabase | Top 200 最新测试节点 | ✅ 保留 |

**问题**：缓存只有 Top 节点，测速中的 2000+ 个普通节点没有保存

---

## 建议方案

### 方案 A：**完整持久化** (推荐)

在 Supabase 中新增两个表，记录：
1. **sources_cache** 表：存储已爬取的订阅源内容
2. **parsed_nodes** 表：存储已解析的所有节点
3. **testing_queue** 表：存储测速任务队列的进度

#### 表结构

**表1：sources_cache**
```sql
CREATE TABLE sources_cache (
  id BIGINT PRIMARY KEY,
  source_url VARCHAR(500) UNIQUE,
  content TEXT,                    -- base64编码的爬取内容
  node_count INT,                 -- 该源的节点数
  last_fetched_at TIMESTAMP,      -- 上次爬取时间
  ttl_hours INT DEFAULT 6,        -- 缓存有效期(6小时)
  created_at TIMESTAMP
)
```

**表2：parsed_nodes**
```sql
CREATE TABLE parsed_nodes (
  id BIGINT PRIMARY KEY,
  host VARCHAR(255),
  port INT,
  name VARCHAR(255),
  protocol VARCHAR(50),
  full_content TEXT,              -- 完整节点数据(JSON)
  source_url VARCHAR(500),        -- 来自哪个源
  parsed_at TIMESTAMP,
  created_at TIMESTAMP,
  UNIQUE(host, port)
)
```

**表3：testing_queue**
```sql
CREATE TABLE testing_queue (
  id BIGINT PRIMARY KEY,
  group_number INT,               -- 第几组 (1-20)
  group_position INT,             -- 组内第几个 (1-50)
  node_id BIGINT,
  status VARCHAR(20),             -- pending/testing/completed/failed
  attempted_count INT DEFAULT 0,  -- 尝试次数
  last_tested_at TIMESTAMP,
  created_at TIMESTAMP,
  FOREIGN KEY (node_id) REFERENCES parsed_nodes(id)
)
```

#### 流程改进

```
启动时的改进流程：
1️⃣ 启动后端进程
   ↓
2️⃣ _load_nodes_from_file() (同上)
   ↓
3️⃣ **检查 sources_cache 表**
   ├─ 如果缓存有效 (< 6小时)
   │  └─ 直接从缓存加载，跳过 API 请求 ✨ 省时 30s
   │
   └─ 如果缓存失效或不存在
      ├─ 执行 _fetch_all_subscriptions() (同上)
      └─ 结果保存到 sources_cache 表 💾
   ↓
4️⃣ **检查 parsed_nodes 表**
   ├─ 如果缓存有效
   │  └─ 直接加载到内存 (self.nodes) ✨ 省时 2-3 分钟
   │
   └─ 如果无缓存
      ├─ 执行解析逻辑 (同上)
      └─ 保存到 parsed_nodes 表 💾
   ↓
5️⃣ **检查 testing_queue 表**
   ├─ 查询未完成的任务 (status != 'completed')
   │  ├─ 如果有未完成的 → 从第一个未完成项继续
   │  │  └─ 比如：第 10 组第 15 个是第一个未完成
   │  │     直接跳到这个位置继续测试 ✨ 省时 ~30 分钟
   │  │
   │  └─ 如果全部完成 → 启动新一轮检测
   │
   └─ 没有队列记录 → 创建新队列
   ↓
6️⃣ _test_nodes_with_new_system() 开始检测
   └─ 从断点继续，而不是从头开始 ✅
```

#### 关键改进

| 环节 | 优化前 | 优化后 | 收益 |
|------|-------|--------|------|
| **爬取订阅源** | 每次 ~30s | 6h内直接加载 | ⚡ 节省 30s |
| **解析节点** | 每次 ~2-3min | 6h内直接加载 | ⚡ 节省 2-3min |
| **测速进度** | 从第1组重新开始 | 从断点继续 | ⚡ 节省 20-30min |
| **总耗时** | ~35-40 分钟 | ~5 分钟（首次）+继续（重启后） | ⚡ 节省 30+ 分钟 |

---

## 可行性评估

### ✅ 技术可行性：高

**优势**：

1. **Supabase 已集成**
   - 后端已经使用 Supabase (supabase_helper.py)
   - 异步驱动成熟 (AsyncClient)
   - 认证和连接已配置

2. **数据模型简单**
   - 三个表都是基础关系型数据
   - 没有复杂的 JOIN 逻辑
   - 可以直接 SQL 操作

3. **代码改动低风险**
   - 不涉及核心检测逻辑
   - 只需要在启动和存储环节加缓存
   - 可以增量实现 (先实现表1→2→3)

### ✅ 数据库容量：充足

**空间估算**：

```
sources_cache 表：
  - 20 个订阅源
  - 平均每个 ~50KB (gzip后)
  - 小计：~1MB

parsed_nodes 表：
  - 10000 个节点 × 1.5KB/节点
  - 小计：~15MB

testing_queue 表：
  - 10000 个节点的任务队列
  - 小计：~2MB

总计：~18MB （Supabase 免费版有 8GB，充足）
```

### ⚠️ 需要注意的问题

1. **缓存失效策略**
   - 订阅源可能更新，需要设置 TTL (建议 6 小时)
   - 过期缓存需要自动清理

2. **一致性问题**
   - 如果手动删除某个源，缓存也需要同步删除
   - 需要添加版本控制或时间戳校验

3. **重复测试风险**
   - 如果网络波动导致数据库写入失败，可能重复测试同一节点
   - 需要添加幂等性保证 (使用 node_id + timestamp 作为唯一键)

---

## 实现成本

### 开发工作量：4-6 小时

#### Phase 1：数据库表创建 (1 小时)

```python
# 新建文件：backend/app/modules/node_hunter/persistence_helper.py

async def init_persistence_tables():
    """初始化持久化表"""
    supabase = create_client(url, key)
    
    # 创建三个表
    # - sources_cache
    # - parsed_nodes
    # - testing_queue

# 在启动时调用一次
```

#### Phase 2：改造 _fetch_all_subscriptions() (1.5 小时)

```python
async def _fetch_all_subscriptions(self):
    """支持缓存的订阅源爬取"""
    
    # 1. 检查 sources_cache 是否有效
    cached_sources = await load_sources_from_cache()
    
    if cached_sources and is_cache_valid():
        self.add_log("⚡ 使用缓存的订阅源...", "INFO")
        return cached_sources
    
    # 2. 执行爬取 (原逻辑)
    all_nodes = await self._original_fetch_all_subscriptions()
    
    # 3. 存储到缓存
    await save_sources_to_cache(all_nodes)
    
    return all_nodes
```

#### Phase 3：改造节点解析 (1.5 小时)

```python
async def _parse_nodes(self, raw_contents):
    """支持缓存的节点解析"""
    
    # 1. 检查 parsed_nodes 缓存
    cached_nodes = await load_parsed_nodes()
    
    if cached_nodes and is_cache_valid():
        self.add_log("⚡ 使用缓存的解析节点...", "INFO")
        return cached_nodes
    
    # 2. 执行解析 (原逻辑)
    parsed = await self._original_parse_nodes(raw_contents)
    
    # 3. 存储到缓存
    await save_parsed_nodes(parsed)
    
    return parsed
```

#### Phase 4：实现测速队列持久化 (1.5 小时)

```python
async def _restore_testing_queue(self):
    """恢复未完成的测速队列"""
    
    # 1. 从 testing_queue 表查询未完成的任务
    pending = await query_pending_tasks()
    
    # 2. 重建内存队列
    if pending:
        self.current_group = pending[0]['group_number']
        self.testing_queue = pending  # 从断点继续
        self.add_log(f"⚡ 恢复测速队列，从第 {self.current_group} 组继续...", "INFO")
    else:
        # 创建新队列
        self.testing_queue = self._create_new_queue()

async def _test_nodes_with_new_system(self, nodes_to_test):
    """在原逻辑基础上，每个任务完成时更新 testing_queue 表"""
    
    # 原逻辑...
    
    # 每测完一个节点，更新队列状态
    for task in self.testing_queue:
        if task['node_id'] == tested_node['id']:
            await update_task_status(task['id'], 'completed')
```

### 成本总结

| 项目 | 工作量 | 难度 | 风险 |
|------|-------|------|------|
| 表设计+创建 | 1h | 低 | 低 |
| 缓存加载逻辑 | 1.5h | 低 | 低 |
| 队列持久化 | 1.5h | 中 | 中 |
| 测试+调试 | 1h | 中 | 中 |
| **总计** | **5h** | **低-中** | **低-中** |

---

## 性能影响

### 启动阶段性能

```
改进前：
1. 爬取订阅源：~30s
2. 解析节点：~2-3min
3. 初始化：~2-3min
总计：~35-40 min ❌ 很慢

改进后 (缓存命中)：
1. 加载缓存源：~2s
2. 加载缓存节点：~5s
3. 恢复队列：~1s
总计：~8s ✅ 快 5 倍
```

### 运行时性能

**内存占用**：几乎无增长
- 内存中仍然是相同的数据结构
- 只是添加了数据库持久化

**数据库查询**：轻量级
```sql
-- 启动时查询 (每次只查一次)
SELECT * FROM testing_queue WHERE status = 'pending' LIMIT 1
-- 执行时间：<10ms

-- 每测完一个节点更新 (异步，不阻塞主流程)
UPDATE testing_queue SET status = 'completed' WHERE id = ?
-- 执行时间：<5ms
```

### 网络开销

**增加的网络操作**：
- 启动时：3 个查询请求 (~20ms)
- 运行时：每测完 1 个节点 1 个更新请求 (~5ms)

**但节省的网络**：
- 不用重复爬取 20 个订阅源 (~30s)
- 不用重复测试已完成的节点 (~1-2 GB 流量)

**总体**：大幅降低网络负载 ✅

---

## 风险分析

### 风险 1️⃣：缓存不一致

**场景**：用户在前端删除了某个订阅源，但缓存仍然有效

**影响**：中等 - 会爬取已删除的源

**缓解方案**：
```python
# 每次更新用户源时，同时清空对应的缓存
async def remove_source(self, url: str):
    self.sources.remove(url)
    await clear_cache_for_source(url)  # 新增
```

### 风险 2️⃣：重复测试

**场景**：测试完一个节点，更新数据库失败，重启后又测一遍

**影响**：低 - 最多重复测一个节点

**缓解方案**：
```python
# 使用幂等性保证：(node_id + test_timestamp) 作为唯一键
# 如果已经测试过，就跳过

async def test_node(self, node_id):
    # 检查是否在最近 10 分钟内测试过
    recent = await get_recent_test(node_id, minutes=10)
    if recent:
        self.add_log("⏭️ 跳过最近测试过的节点", "INFO")
        return recent
    
    # 执行测试
    result = await _do_test(node_id)
    await save_test_result(node_id, result)
    return result
```

### 风险 3️⃣：Supabase 连接失败

**场景**：Supabase 不可用，无法读写队列

**影响**：中等 - 系统退化到原来的行为，但不会崩溃

**缓解方案**：
```python
# 优雅降级：缓存读写失败时，直接继续
async def update_queue_safe(self, task_id):
    try:
        await update_task_status(task_id, 'completed')
    except Exception as e:
        self.add_log(f"⚠️ 队列持久化失败: {e}，继续本地执行", "WARNING")
        # 本地内存中的队列状态仍然更新，只是不持久化
```

### 风险 4️⃣：表空间爆炸

**场景**：长期运行，parsed_nodes 表不断增长

**影响**：低 - 可能在 6 个月后达到 500MB

**缓解方案**：
```python
# 定期清理旧数据（周维护任务）
async def cleanup_old_data():
    # 删除 7 天前的 testing_queue 记录
    await supabase.table("testing_queue").delete()\
        .lt("created_at", date.today() - timedelta(days=7)).execute()
    
    # 删除过期的源缓存 (> 24小时)
    await supabase.table("sources_cache").delete()\
        .lt("last_fetched_at", datetime.now() - timedelta(hours=24)).execute()
```

---

## 替代方案

### 方案 B：**本地文件持久化** (简单但不够优雅)

将测速队列进度保存到本地 JSON 文件

**优点**：
- 实现简单（1-2 小时）
- 不需要数据库

**缺点**：
- ❌ 无法分布式同步（如果后端有多个副本）
- ❌ 文件系统可靠性不如数据库
- ❌ 数据量大时文件 I/O 慢

```python
# 简单实现
def save_progress(current_group, current_position):
    progress = {
        'group': current_group,
        'position': current_position,
        'timestamp': time.time()
    }
    with open('testing_progress.json', 'w') as f:
        json.dump(progress, f)

def restore_progress():
    if os.path.exists('testing_progress.json'):
        with open('testing_progress.json', 'r') as f:
            return json.load(f)
    return None
```

### 方案 C：**混合方案** (推荐备选)

- 本地文件：存储当前测速进度（快速）
- Supabase：存储历史测速结果（持久化）

**优点**：
- 既快又可靠
- 工作量介于 A 和 B 之间

**缺点**：
- 稍微复杂一点

---

## 建议决策

### 根据您的情况选择

**如果您选择 ✅ 实现方案 A**：

**理由**：
1. 完整的持久化能力
2. 支持未来的分布式部署 (多个后端副本)
3. 工作量可控 (5 小时)
4. 长期受益 (自动化任务更可靠)

**下一步**：
```
1. 确认 Supabase 表设计 ✓
2. 实现持久化助手模块 (persistence_helper.py)
3. 改造启动逻辑和测速循环
4. 测试缓存失效和恢复流程
5. 提交到 dev 分支
```

**如果您选择 ✅ 实现方案 C**：

**理由**：
1. 快速解决当前痛点
2. 工作量最少 (2-3 小时)
3. 逐步升级到方案 A

**下一步**：
```
1. 先用本地 JSON 存储队列进度
2. 稳定运行 1-2 周后
3. 升级为完整的数据库方案 A
```

**如果您选择 ❌ 暂不实现**：

**原因**：
1. 当前问题不是很紧急
2. 需要先验证其他优化效果
3. 等待更多需求

**建议**：
- 先用 `Ctrl+C` 暂停，然后 `python app.py` 恢复
- 手动记录进度，下次启动时指定起始位置

---

## 总结对比表

| 方案 | 工作量 | 完整性 | 可靠性 | 扩展性 | 推荐度 |
|------|--------|--------|--------|--------|---------|
| **A. 完整持久化** | 5h | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **B. 本地文件** | 2h | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **C. 混合方案** | 3h | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **D. 不实现** | 0h | ⭐ | ⭐ | ⭐ | ⭐ |

---

## 我的建议

### 🎯 推荐：**先实现方案 C (混合方案)，再升级到方案 A**

**理由**：
1. ⚡ **快速见效**：2 小时内就能缓解重启问题
2. 🎯 **阶段递进**：先用本地方案验证可行性，再升级
3. 💪 **风险最低**：如果出问题，本地文件很容易回滚
4. 🚀 **铺垫未来**：逐步建立数据库持久化体系

### 📅 建议时间规划

```
Week 1 (现在):
  - 实现方案 C (混合方案) [2-3h]
  - 测试重启恢复 [1h]
  - 提交到 dev [0.5h]

Week 2-3:
  - 运行观察，积累需求反馈
  - 如果工作稳定，考虑升级

Week 4+:
  - 实现方案 A (完整持久化) [5h]
  - 整合历史数据
  - 切换到完整方案
```

---

## 您的决定？

请告诉我您的选择：

- [ ] **选择方案 A**（完整持久化，现在就做）
- [ ] **选择方案 C**（混合方案，快速试验）
- [ ] **选择方案 B**（本地文件，最简单）
- [ ] **暂不实现**，继续观察
- [ ] **其他建议**？

我会根据您的选择立即开始实现！✨

