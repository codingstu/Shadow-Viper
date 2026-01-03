# Supabase 数据库同步修复记录 - 2026年1月4日

## 问题概述

**现象**：本地运行可以正常同步 Supabase，部署到线上（Azure + Vercel）后同步失败。

**错误日志**：
```
[18:10:53] ⚠️ Supabase 同步失败或未启用
```

---

## 根本原因分析

### 问题1：`/api/sync` 端点硬编码本地路径

**文件**：`backend/app/main.py`

**原代码**：
```python
viper_store_path = "/Users/ikun/study/Learning/viper-node-store"
script_path = os.path.join(viper_store_path, "sync_nodes_local.py")
```

**问题**：这个路径在 Azure 服务器上不存在，导致同步必定失败。

### 问题2：环境变量配置

`.env` 文件在 `.gitignore` 中，不会推送到 Azure。需要在 Azure App Service 中手动配置环境变量。

### 问题3：supabase 库未安装

Azure 部署时可能未正确安装 `supabase` 依赖包。

### 问题4：启动时从本地 JSON 文件加载节点

原逻辑从 `verified_nodes.json` 加载缓存节点，这在云端部署时不合理。

### 问题5：异步加载 Supabase 数据的 Bug

**原代码**：
```python
if loop.is_running():
    asyncio.create_task(self._load_nodes_from_supabase())
    return  # ← 直接 return，没等任务完成！
```

**问题**：`create_task()` 只是创建任务但不等待完成，导致实际上还是从本地文件加载。

---

## 修复方案

### 修复1：重写 `/api/sync` 端点

**文件**：`backend/app/main.py`

**修改**：改为直接调用 `supabase_helper.upload_to_supabase()` 函数，不再依赖外部脚本。

```python
@app.post("/api/sync")
async def sync_data_to_supabase():
    from .modules.node_hunter.supabase_helper import upload_to_supabase, get_supabase_credentials
    
    # 1. 检查凭证
    url, key = get_supabase_credentials()
    if not url or not key:
        return {"success": False, "message": "Supabase 凭证未配置"}
    
    # 2. 获取活跃节点
    alive_nodes = node_hunter.get_alive_nodes()
    
    # 3. 去重并上传
    result = await upload_to_supabase(unique_nodes)
    
    # 4. 返回详细结果
    if isinstance(result, tuple):
        success, detail = result
    return {"success": success, "message": detail}
```

### 修复2：增强错误信息显示

**文件**：`backend/app/modules/node_hunter/supabase_helper.py`

**修改**：`upload_to_supabase()` 返回 `tuple(bool, str)` 而非单纯 `bool`，包含详细错误信息。

```python
async def upload_to_supabase(nodes: List[Dict]) -> tuple:
    """返回：(是否成功, 错误消息或成功数量)"""
    # ...
    return False, "具体错误信息"  # 失败
    return True, total_uploaded    # 成功
```

**文件**：`backend/app/modules/node_hunter/node_hunter.py`

**修改**：在前端终端显示具体错误原因。

```python
result = await upload_to_supabase(unique_nodes)
if isinstance(result, tuple):
    success, detail = result
if success:
    self.add_log(f"✅ Supabase 同步完成！{detail} 个节点已写入数据库", "SUCCESS")
else:
    self.add_log(f"⚠️ Supabase 同步失败: {detail}", "WARNING")
```

### 修复3：添加诊断端点

**文件**：`backend/app/main.py`

**新增**：`/api/debug/supabase` 端点，用于检查环境变量配置状态。

```python
@app.get("/api/debug/supabase")
async def debug_supabase_config():
    return {
        "environment": "Azure" if is_azure else "Local",
        "supabase_url": {"configured": bool(url)},
        "supabase_key": {"configured": bool(key), "length": len(key)},
        "recommendation": "OK" if configured else "请配置环境变量"
    }
```

### 修复4：添加前端同步按钮

**文件**：`frontend/src/components/NodeHunter/NodeHunter.vue`

**新增**：手动触发同步的按钮，方便测试。

```vue
<n-button type="success" size="tiny" @click="syncToSupabase" :loading="syncing">
  <template #icon>☁️</template> {{ syncing ? '同步中' : '同步DB' }}
</n-button>
```

```javascript
async function syncToSupabase() {
  syncing.value = true;
  addLog('☁️ 正在同步数据到 Supabase...');
  try {
    const { data } = await api.post('/api/sync');
    if (data.success) {
      addLog(`✅ ${data.message}`);
    } else {
      addLog(`⚠️ 同步失败: ${data.message}`);
    }
  } catch (error) {
    addLog(`❌ 同步出错: ${error.message}`);
  } finally {
    syncing.value = false;
  }
}
```

### 修复5：启动时后台加载 Supabase 节点（核心修复）

**文件**：`backend/app/modules/node_hunter/node_hunter.py`

**问题**：原代码 `asyncio.create_task()` 后直接 `return`，导致实际上没有从 Supabase 加载数据。

**修复策略**：
1. 先从本地文件快速加载（保证启动速度）
2. 5 秒后后台从 Supabase 加载并**合并**到内存

```python
def _load_nodes_from_file(self):
    """启动时先从本地缓存快速加载，然后在后台从 Supabase 更新"""
    # 先从本地文件快速加载（保证启动速度）
    self._load_nodes_from_local_file()
    
    # 然后安排一个后台任务从 Supabase 更新
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self._load_and_merge_from_supabase())
    except Exception as e:
        self.add_log(f"⚠️ 设置 Supabase 加载任务失败: {e}", "WARNING")

async def _load_and_merge_from_supabase(self):
    """后台从 Supabase 加载节点并合并到内存"""
    await asyncio.sleep(5)  # 等待 5 秒，让系统完全启动
    
    # 查询数据库
    response = supabase.table("nodes").select("*").order("speed", desc=True).limit(200).execute()
    
    # 合并策略：数据库节点优先，本地独有的也保留
    # 按 host:port 去重
    for node in loaded_nodes:
        key = f"{node.get('host')}:{node.get('port')}"
        if key not in db_keys:
            db_keys.add(key)
            merged_nodes.append(node)
    
    self.add_log(f"☁️ 从 Supabase 加载了 {len(loaded_nodes)} 个节点，合并后共 {len(self.nodes)} 个", "SUCCESS")
```

**启动日志效果**：
```
[18:42:20] 📥 从本地缓存加载了 73 个节点
[18:42:25] ☁️ 正在从 Supabase 数据库加载节点...
[18:42:26] ☁️ 从 Supabase 加载了 103 个节点，合并后共 108 个 (原 73 个)
```

---

## Supabase 数据库结构

### nodes 表结构

```sql
create table public.nodes (
  id text not null,                              -- 主键：host:port
  content jsonb null,                            -- 完整节点数据
  is_free boolean null default false,
  speed integer null,                            -- 综合评分
  updated_at timestamp with time zone null default now(),
  latency bigint null,                           -- 延迟 (ms)
  mainland_score integer null default 0,         -- 大陆评分
  mainland_latency integer null default 0,       -- 大陆延迟
  overseas_score integer null default 0,         -- 海外评分
  overseas_latency integer null default 0,       -- 海外延迟
  link text null default ''::text,               -- 节点分享链接
  constraint nodes_pkey primary key (id)         -- 主键约束
);

create index idx_nodes_link on public.nodes using btree (link);
```

### Upsert 策略

代码使用 `upsert` 而非 `insert`：
```python
response = supabase.table("nodes").upsert(batch).execute()
```

**效果**：
- 如果 `id` 不存在 → 插入新记录
- 如果 `id` 已存在 → 用新数据**更新**旧记录

这保证了：
1. 数据库中不会有重复的 `host:port`
2. 每次同步都会刷新 `speed`, `latency`, `updated_at` 等字段为最新值

---

## Azure 配置清单

### 必须配置的环境变量

在 **Azure Portal → App Service → 配置 → 应用程序设置** 中添加：

| 变量名 | 说明 |
|--------|------|
| `SUPABASE_URL` | Supabase 项目 URL，如 `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | （推荐）service_role key，可绕过 RLS |

⚠️ **注意**：环境变量名**区分大小写**！

### 确保依赖安装

`requirements.txt` 中必须包含：
```
supabase==2.3.5
```

---

## 验证步骤

### 1. 检查环境变量配置

访问：`https://你的域名/api/debug/supabase`

期望返回：
```json
{
  "supabase_url": {"configured": true},
  "supabase_key": {"configured": true, "length": 200+}
}
```

### 2. 手动触发同步

点击前端 **"同步DB"** 按钮，观察终端日志：

- ✅ 成功：`✅ Supabase 同步完成！73 个节点已写入数据库`
- ❌ 失败：`⚠️ Supabase 同步失败: 具体错误信息`

### 3. 验证启动加载

重启后端，观察日志（约 5 秒后）：

```
[18:42:20] 📥 从本地缓存加载了 73 个节点
[18:42:25] ☁️ 正在从 Supabase 数据库加载节点...
[18:42:26] ☁️ 从 Supabase 加载了 103 个节点，合并后共 108 个 (原 73 个)
```

### 4. 检查数据库数据

访问 Supabase Dashboard → Table Editor → nodes：
- 确认数据存在
- 检查 `updated_at` 是否为最新时间

---

## 修改的文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/app/main.py` | 重写 `/api/sync`，添加 `/api/debug/supabase` |
| `backend/app/modules/node_hunter/supabase_helper.py` | 增强错误返回，添加详细日志 |
| `backend/app/modules/node_hunter/node_hunter.py` | 修复异步加载 Bug，实现后台合并策略 |
| `frontend/src/components/NodeHunter/NodeHunter.vue` | 添加同步按钮 |

---

## 数据流架构

```
┌─────────────────────────────────────────────────────────────┐
│                    SpiderFlow 后端                          │
│                                                             │
│  启动时:                                                    │
│  ├── 1. 立即从 verified_nodes.json 加载 (快速)             │
│  └── 2. 5秒后后台从 Supabase 加载并合并                    │
│                                                             │
│  定时任务 (每3分钟):                                        │
│  └── 自动同步活跃节点到 Supabase                           │
│                                                             │
│  手动同步:                                                  │
│  └── 前端点击 "同步DB" → POST /api/sync                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Supabase 数据库                          │
│                                                             │
│  nodes 表:                                                  │
│  ├── id (主键): host:port                                  │
│  ├── content: 完整节点 JSON                                │
│  ├── speed/latency: 评分数据                               │
│  ├── mainland_score/overseas_score: 双区域评分             │
│  └── updated_at: 最后更新时间                              │
│                                                             │
│  upsert 策略: 存在则更新，不存在则插入                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 viper-node-store 前端                       │
│                                                             │
│  从 Supabase 读取节点数据并展示                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 相关文档

- [部署修复总结](./DEPLOYMENT_FIXES_2026-01-02.md)
- [HTTP 502 错误分析](./HTTP_502_DEEP_ANALYSIS.md)
- [项目架构](./PROJECT_ARCHITECTURE.md)

---

**文档更新时间**：2026-01-04  
**状态**：✅ 已修复并验证
