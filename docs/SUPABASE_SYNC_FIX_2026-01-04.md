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

### 修复5：启动时优先从 Supabase 加载节点

**文件**：`backend/app/modules/node_hunter/node_hunter.py`

**修改**：新增 `_load_nodes_from_supabase()` 方法，启动时优先从数据库加载。

```python
def _load_nodes_from_file(self):
    """优先从 Supabase 加载，失败时从本地缓存加载"""
    try:
        await self._load_nodes_from_supabase()
        if self.nodes:
            return  # 成功
    except:
        pass
    # 失败，从本地文件加载
    self._load_nodes_from_local_file()

async def _load_nodes_from_supabase(self):
    """从 Supabase 加载最新的 200 个高评分节点"""
    response = supabase.table("nodes").select("*").order("speed", desc=True).limit(200).execute()
    # ...
    self.add_log(f"☁️ 从 Supabase 加载了 {len(loaded_nodes)} 个节点", "SUCCESS")
```

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

重启后端，观察日志：

- ☁️ `从 Supabase 加载了 XX 个节点` - 成功从数据库加载
- 📥 `从本地缓存加载了 XX 个节点` - 使用本地备用

---

## 修改的文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/app/main.py` | 重写 `/api/sync`，添加 `/api/debug/supabase` |
| `backend/app/modules/node_hunter/supabase_helper.py` | 增强错误返回，添加详细日志 |
| `backend/app/modules/node_hunter/node_hunter.py` | 显示详细错误，从 Supabase 加载节点 |
| `frontend/src/components/NodeHunter/NodeHunter.vue` | 添加同步按钮 |

---

## 相关文档

- [部署修复总结](./DEPLOYMENT_FIXES_2026-01-02.md)
- [HTTP 502 错误分析](./HTTP_502_DEEP_ANALYSIS.md)
- [项目架构](./PROJECT_ARCHITECTURE.md)

---

**文档更新时间**：2026-01-04  
**状态**：✅ 已修复并验证
