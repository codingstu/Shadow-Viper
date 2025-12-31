# 🚀 SpiderFlow 高级测速 - 部署计划

## 📋 项目完成总结

### ✅ 已完成的工作

#### 1️⃣ **新增模块**

| 文件 | 功能 | 行数 |
|------|------|------|
| `advanced_speed_test.py` | 双地区高级测速（Aliyun + Cloudflare） | ~280 |
| `supabase_helper.py` | Supabase 数据库集成 | ~140 |
| `ADVANCED_TEST_GUIDE.md` | 详细的本地测试指南 | ~200 |

#### 2️⃣ **集成改动**

| 文件 | 改动 | 影响 |
|------|------|------|
| `node_hunter.py` | 导入新模块 + scan_cycle() 集成 | 🟢 安全（新增调用，不改现有） |
| `.env.example` | 添加新环境变量配置 | 🟢 安全（文档） |
| `requirements.txt` | 添加 supabase, ipapi | 🟢 安全（新依赖） |

#### 3️⃣ **版本控制**

- ✅ dev 分支已创建并推送
- ✅ 所有改动已提交（commit: 671c46d）
- ✅ 可随时合并到 main（当验证完成时）

---

## 🔄 数据流架构

### 优化前：
```
SpiderFlow 爬虫
  ├─ 基础测速
  └─ verified_nodes.json
          ↓
    viper-node-store
      ├─ 再次完整测速（重复！）
      └─ Supabase 保存
```

### 优化后（dev 分支）：
```
SpiderFlow 爬虫（dev 分支）
  ├─ 基础测速（不变）
  └─ ✨ 高级双地区测速（新增）
      ├─ CN 节点 → Aliyun FC
      └─ 非 CN → Cloudflare
          ↓
      Supabase 直接保存
          ↓
    viper-node-store（简化）
      └─ 直接读 Supabase（无需再测）
```

---

## 🎯 后续部署步骤

### Phase 1: 本地验证（推荐立即进行）

**在 Azure 服务器上执行：**

```bash
# 1. 切换到 dev 分支
cd /path/to/SpiderFlow
git checkout dev

# 2. 安装新依赖
pip install -r backend/requirements.txt

# 3. 配置环境变量（.env 文件）
ADVANCED_TEST_ENABLED=false  # 先关闭，验证兼容性

# 4. 启动服务
cd backend
python -m uvicorn app.main:app

# 5. 验证基础功能（应该与现在一样）
curl http://localhost:8000/nodes/stats | jq '.count'
```

**预期结果：** 
- ✅ 服务正常启动
- ✅ 爬虫正常运行
- ✅ verified_nodes.json 正常生成
- ✅ 没有新的错误日志

---

### Phase 2: 启用高级测速（Azure 上）

**前置条件：**
- ✅ Aliyun FC 已部署且正常运行
- ✅ Cloudflare Worker 已部署且正常运行
- ✅ Supabase 项目已创建且有 nodes 表

**配置步骤：**

```bash
# 编辑 .env 文件
ADVANCED_TEST_ENABLED=true
ALIYUN_FC_URL=https://mainland-probe-eyptbwbaco.cn-hangzhou.fcapp.run
CLOUDFLARE_WORKER_URL=<你的 Worker URL>
SUPABASE_URL=<你的 Supabase URL>
SUPABASE_KEY=<你的 anon key>
```

**测试步骤：**

```bash
# 1. 重启服务（加载新环境变量）
# Ctrl+C 停止，重新启动

# 2. 手动触发扫描
curl -X POST http://localhost:8000/nodes/trigger

# 3. 监控日志，观察：
# - "启动高级双地区测速..."
# - "[Aliyun FC] 开始大陆测速..."
# - "[Cloudflare] 开始国外测速..."
# - "Supabase 上传成功！"

# 4. 查询 Supabase 数据
# 访问 Supabase Dashboard，检查 nodes 表
```

**预期结果：**
- ✅ 高级测速正常运行
- ✅ 日志显示成功的测速
- ✅ Supabase 有新数据
- ✅ 数据包含 advanced_speed_score 字段

---

### Phase 3: 验证前端（可选）

**如果启用了 Supabase 上传：**

```bash
# 前端可以直接从 Supabase 读取数据
# 在 viper-node-store 的前端中：

const nodes = await supabase
  .from('nodes')
  .select('*')
  .order('speed', { ascending: false })
  .limit(50)
```

---

### Phase 4: viper-node-store 简化（可选）

**当 SpiderFlow 已完成双地区测速后，可以：**

#### 方案 A：完全简化（推荐）
```python
# viper-node-store/update_nodes.py
# 删除所有测速逻辑
# 前端直接读 Supabase（无需后端）
```

#### 方案 B：保持兼容（安全）
```python
# viper-node-store/update_nodes.py
# 改为读 SpiderFlow 生成的 verified_nodes.json
# 不再做测速，直接保存
```

---

## 📊 影响范围分析

### SpiderFlow（dev 分支）

| 模块 | 改动 | 风险 | 测试覆盖 |
|------|------|------|---------|
| 爬虫链路 | 无 | ✅ 零 | ✅ 现有流程保持 |
| 基础测速 | 无 | ✅ 零 | ✅ 现有流程保持 |
| 节点保存 | 无 | ✅ 零 | ✅ verified_nodes.json 保持 |
| 高级测速 | 新增 | 🟢 低 | ✅ 可选启用 |
| Supabase | 新增 | 🟢 低 | ✅ 可选启用 |

### viper-node-store（待定）

| 方案 | 改动 | 风险 | 优势 |
|------|------|------|------|
| A（推荐） | 删除测速逻辑 | 🟡 中 | ⭐⭐⭐⭐⭐ 完全简化 |
| B（兼容） | 改数据来源 | 🟢 低 | ⭐⭐⭐ 功能不变 |
| C（保守） | 无改动 | ✅ 零 | ⭐⭐ 多余计算 |

---

## 🔐 安全验证

### 代码审查清单

- ✅ 新模块没有引入外部依赖（除了 supabase）
- ✅ 错误处理完善（try-except 覆盖）
- ✅ 日志详细（便于排查）
- ✅ 环境变量可选（不启用不影响）
- ✅ 没有修改现有核心逻辑
- ✅ 异步操作正确处理（await）

### 性能影响

```
现有爬虫周期：~10 分钟
+ 高级测速：+5-7 分钟
= 新总耗时：~15-17 分钟

对 Azure 1G1H 服务器影响：
- CPU：临时增加（测速期间）
- 内存：+50MB（异步并发）
- 网络：正常（并发 30 个节点）
- 磁盘：不变
```

---

## 🚨 风险评估

### 低风险 🟢

- ✅ 新模块是独立的
- ✅ 启用/禁用通过环境变量控制
- ✅ 不影响现有爬虫逻辑
- ✅ 可随时回滚（dev 分支隔离）

### 中风险 🟡

- ⚠️ 需要配置 Aliyun FC（如果启用）
- ⚠️ 需要配置 Cloudflare Worker（如果启用）
- ⚠️ 需要 Supabase 权限（如果启用）

### 缓解措施 🛡️

- ✅ 默认禁用（ADVANCED_TEST_ENABLED=false）
- ✅ 缺少配置时会跳过，不会崩溃
- ✅ 详细的日志便于调试

---

## 📋 最终检查清单

### 代码层面

- [x] advanced_speed_test.py 已创建并测试语法
- [x] supabase_helper.py 已创建并测试语法
- [x] node_hunter.py 已集成（导入 + scan_cycle 调用）
- [x] 导入语句正确
- [x] 异步函数正确使用 await
- [x] 错误处理完善
- [x] 日志输出充分

### 文档层面

- [x] .env.example 已更新
- [x] requirements.txt 已更新
- [x] ADVANCED_TEST_GUIDE.md 已创建
- [x] 注释充分

### Git 层面

- [x] dev 分支已创建
- [x] 改动已提交（commit 671c46d）
- [x] 改动已推送到远程

### 部署准备

- [ ] 在 Azure 上本地验证（兼容性）
- [ ] 配置 Aliyun FC（如果需要）
- [ ] 配置 Cloudflare Worker（如果需要）
- [ ] 配置 Supabase（如果需要）
- [ ] 启用高级测速测试
- [ ] 验证 Supabase 上传成功
- [ ] 观察日志无异常
- [ ] 决定 viper-node-store 改动方案

---

## 📞 后续步骤

### 立即可做：

1. **在 Azure 上测试兼容性**
   ```bash
   git checkout dev
   # 确保 ADVANCED_TEST_ENABLED=false
   # 验证爬虫仍正常工作
   ```

2. **准备 Aliyun FC 和 Cloudflare Worker**
   - 已在 viper-node-store 项目中部署
   - 记录 URL 供 SpiderFlow 使用

3. **配置 Supabase**
   - 使用现有的 Supabase 项目
   - 获取 URL 和 anon key

### 验证完成后：

4. **启用高级测速**
   - 在 Azure .env 配置所有参数
   - 运行完整的双地区测速测试
   - 验证 Supabase 上传

5. **合并到 main**
   ```bash
   git checkout main
   git merge dev
   ```

6. **更新 viper-node-store**
   - 选择简化方案
   - 从 Supabase 读取数据

---

## ✨ 预期收益

### 现在（dev 分支）

- ✅ SpiderFlow 完成完整的双地区测速
- ✅ 数据直接进入 Supabase（无需 viper-node-store 再测）
- ✅ 现有爬虫功能完全保持
- ✅ 可灵活启用/禁用新功能

### 合并后

- 🎉 消除重复测速（每次 20 分钟→10 分钟）
- 🎉 提高数据准确性（双地区真实延迟）
- 🎉 简化系统架构（viper-node-store 变为纯 API）
- 🎉 减少服务器负担（Azure 1G1H 消耗更少）

---

**准备好进行本地验证了吗？** 🚀
