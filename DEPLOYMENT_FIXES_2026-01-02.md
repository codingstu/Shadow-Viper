# SpiderFlow 部署修复总结 - 2026年1月2日

## 核心修复：前端硬编码地址移除

### 1. 修复内容

#### SyncButton.vue - 同步功能修复
**文件：** `frontend/src/components/SyncButton.vue`

**问题：** 第 45 行硬编码 localhost:8001
```javascript
// ❌ 原代码（导致生产部署失败）
const response = await fetch('http://localhost:8001/api/sync', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
})
```

**修复：** 改为相对路径
```javascript
// ✅ 修复后（支持任何部署域名）
const response = await fetch('/api/sync', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
})
```

**原理：**
- 浏览器会根据当前页面域名解析 `/api/sync`
- Vite/Vercel 的路由规则将 `/api/*` 转发到后端
- 不再受限于 localhost

---

### 2. 部署架构

```
┌─────────────────────────────────────────────────┐
│         SpiderFlow Frontend (Deployed)          │
│    https://spiderflow-frontend.vercel.app       │
└────────────────────┬────────────────────────────┘
                     │
          ✅ 使用相对路径 /api/sync
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│   Vercel/后端 路由层（vercel.json）             │
│   /api/* → FastAPI 后端                        │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│    SpiderFlow Backend API                       │
│    app/modules/node_hunter/node_hunter.py       │
│    POST /api/sync → 同步数据到 Supabase         │
└─────────────────────────────────────────────────┘
```

---

### 3. 本地开发配置

确保 `frontend/vite.config.js` 包含代理配置：

```javascript
export default {
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8001',  // SpiderFlow 后端
        changeOrigin: true,
        rewrite: (path) => path
      }
    }
  }
  // ... 其他配置
}
```

**说明：**
- 本地开发：`npm run dev` → Vite proxy 转发到 localhost:8001
- 生产部署：Vercel 路由规则转发到后端
- 两种情况都使用相同的相对路径 `/api/sync`

---

### 4. 环境变量检查

**文件：** `backend/.env`

```bash
# ✅ 已验证的配置
SUPABASE_URL=https://hnlkwtkxbqiakeyienok.supabase.co
SUPABASE_KEY=eyJhbGc...

# 其他必要配置
SPIDERFLOW_API_URL=http://localhost:8001  # 本地开发用
```

---

### 5. Git 提交记录

```
commit 1d209ec
Author: ...
Date: 2026-01-02

fix: remove hardcoded localhost in SyncButton component

- SyncButton.vue: changed fetch('http://localhost:8001/api/sync') 
  to relative path '/api/sync'
- This allows the deployed frontend to communicate with its backend 
  via proper routing
```

---

## 6. 验证步骤

### 本地测试
```bash
# 1. 启动后端
cd backend
python -m app.main

# 2. 启动前端（新终端）
cd frontend
npm install
npm run dev

# 3. 在浏览器打开 http://localhost:5173
# 4. 点击同步按钮测试 /api/sync 接口
```

### 生产验证
```bash
# 1. 查看浏览器网络请求
# DevTools → Network → 找 /api/sync 请求
# 应该看到：
#   Request URL: https://spiderflow-xxx.vercel.app/api/sync
#   Status: 200 或相应的状态码

# 2. 检查响应
# 应该返回 {"success": true, ...} 或类似的 JSON
```

---

## 7. 常见问题排查

### Q: 同步按钮点击后显示"Failed to fetch"
**原因：**
- Vercel 部署还未更新代码
- 后端 `/api/sync` 接口不存在或不可达
- CORS 配置问题

**解决：**
```bash
# 1. 确认代码已推送
git push origin dev

# 2. 等待 Vercel 自动部署完成（约 2-5 分钟）

# 3. 手动清除 Vercel 缓存
# 访问 Vercel 仪表板 → 项目 → Settings → Git → Clear Cache

# 4. 检查后端是否运行
curl http://localhost:8001/api/status
```

### Q: 本地开发时 /api/sync 返回 404
**原因：**
- Vite proxy 配置不正确
- 后端未启动
- 后端路由不存在

**解决：**
```bash
# 1. 检查后端启动
ps aux | grep "python.*app"

# 2. 测试后端直接访问
curl http://localhost:8001/api/sync -X POST

# 3. 检查 vite.config.js proxy 配置
cat frontend/vite.config.js | grep -A 5 "proxy:"
```

---

## 8. 数据流验证

### 同步流程检查清单
- [ ] SpiderFlow 后端启动并运行
- [ ] Supabase 连接正常（检查日志中是否有连接错误）
- [ ] 前端可访问（http://localhost:5173 本地，或 Vercel URL）
- [ ] 点击同步按钮，观察网络请求
- [ ] Supabase 数据库中新数据出现
- [ ] viper-node-store 读取到新数据

---

## 9. 相关文件速查表

| 文件 | 修改内容 | 优先级 |
|------|--------|-------|
| `frontend/src/components/SyncButton.vue` | ✅ 修复硬编码地址 | 🔴 高 |
| `frontend/vite.config.js` | ✅ proxy 配置 | 🔴 高 |
| `backend/.env` | ✅ Supabase 凭证 | 🟡 中 |
| `app/modules/node_hunter/node_hunter.py` | - | 🟢 低 |
| `app/modules/node_hunter/supabase_helper.py` | - | 🟢 低 |

---

## 10. 与 viper-node-store 的集成

### 数据同步路径
```
SpiderFlow (测速)
    ↓
Supabase (存储)
    ↓
viper-node-store (读取和展示)
```

### 关键配置
- SpiderFlow 上传到 Supabase 的节点数据
- viper-node-store 从 Supabase 读取节点
- 两个系统共享同一个 Supabase 数据库

### 环境变量对齐
```bash
# SpiderFlow backend/.env
SUPABASE_URL=...
SUPABASE_KEY=...

# viper-node-store backend 同样需要这些凭证
# 配置在 .env 或 Vercel 环境变量中
```

---

## 11. 部署清单

### 部署前检查
- [ ] 所有 localhost 硬编码已移除
- [ ] vite.config.js proxy 配置正确
- [ ] .env 文件配置完整
- [ ] 本地测试成功
- [ ] git commit 已推送

### 部署过程
```bash
# 1. 推送代码
cd /Users/ikun/study/Learning/SpiderFlow
git push origin dev

# 2. Vercel 自动部署（无需手动操作）
# 检查部署状态：https://vercel.com/dashboard

# 3. 部署完成后测试
# 访问前端 URL，点击同步按钮
```

### 部署后验证
- [ ] 前端可访问
- [ ] 同步按钮可点击
- [ ] 网络请求显示 /api/sync
- [ ] Supabase 接收新数据
- [ ] viper-node-store 显示最新节点

---

## 12. 性能优化建议

- [ ] 添加请求超时处理
- [ ] 实现同步进度显示
- [ ] 添加错误重试机制
- [ ] 优化批量上传性能
- [ ] 监控同步失败率

---

**文档更新时间：** 2026-01-02  
**相关项目：** viper-node-store  
**维护人：** ikun  
**状态：** ✅ 完成

**相关文档：**
- [viper-node-store 部署修复](../viper-node-store/DEPLOYMENT_FIXES_2026-01-02.md)
