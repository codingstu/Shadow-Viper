# SpiderFlow 高级双地区测速模块 - 测试指南

## 📋 概览

这个文档描述如何在本地环境中测试新的高级双地区测速模块。

## 🚀 启动步骤

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

创建或编辑 `.env` 文件（基于 `.env.example`）：

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env，添加以下内容
ADVANCED_TEST_ENABLED=true
ALIYUN_FC_URL=https://mainland-probe-eyptbwbaco.cn-hangzhou.fcapp.run
CLOUDFLARE_WORKER_URL=<你的 Cloudflare Worker URL>
SUPABASE_URL=<你的 Supabase URL>
SUPABASE_KEY=<你的 Supabase anon key>
```

### 3. 启动后端服务

```bash
python -m uvicorn app.main:app --reload
```

访问：http://localhost:8000/docs (Swagger UI)

## 🧪 测试场景

### 场景 1：不启用高级测速（保持原有功能）

**配置：**
```bash
ADVANCED_TEST_ENABLED=false
```

**预期：**
- 爬虫正常运行基础测速
- 节点保存到 verified_nodes.json
- Supabase 不上传（跳过）

**验证：**
```bash
curl http://localhost:8000/nodes/stats | jq '.count'
```

---

### 场景 2：启用高级测速（完整流程）

**配置：**
```bash
ADVANCED_TEST_ENABLED=true
ALIYUN_FC_URL=https://mainland-probe-eyptbwbaco.cn-hangzhou.fcapp.run
CLOUDFLARE_WORKER_URL=https://mainland-node-overseas-probe.your-account.workers.dev
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your-key
```

**预期：**
1. 爬虫获取节点 → 基础测速 ✅
2. 启动高级测速 ✅
   - CN 节点 → Aliyun FC 测速
   - 非 CN 节点 → Cloudflare 测速
3. 上传到 Supabase ✅

**验证步骤：**

#### 2.1 触发爬虫扫描

```bash
curl -X POST http://localhost:8000/nodes/trigger
```

#### 2.2 监控日志

在终端中观察日志输出：

```
🚀 开始全网节点嗅探...
🔍 解析成功 150 个唯一节点
🧪 开始测试 150 个节点...
🎉 测试完成！有效节点: 120/150
🚀 启动高级双地区测速...
📊 节点分类: 🇨🇳 CN=80, 🌍 其他=40
   🚀 [Aliyun FC] 开始大陆测速 (80 个 CN 节点)...
   📤 [Aliyun] 批次 1 (15 个节点)...
   ✅ [Aliyun] 测速完成: 75 / 80 节点可用
   🚀 [Cloudflare] 开始国外测速 (40 个非 CN 节点)...
   ✅ [Cloudflare] 测速完成: 38 / 40 节点可用
📤 准备上传 113 个节点到 Supabase...
✅ Supabase 上传成功！
```

#### 2.3 检查 Supabase 数据

打开 Supabase Dashboard：
- 访问 https://app.supabase.com
- 进入你的项目
- 查看 `nodes` 表
- 确认有新数据，且包含 `advanced_speed_score` 和 `latency` 字段

#### 2.4 验证数据格式

```bash
curl http://localhost:8000/nodes/stats | jq '.nodes[0].nodes[0]'

# 应该看到包含以下字段的节点：
# - advanced_speed_score: 50
# - advanced_latency_mainland: 45
# - tested_via: "aliyun"
# - test_time: "2025-01-XX..."
```

---

### 场景 3：部分配置缺失

**配置：**
```bash
ADVANCED_TEST_ENABLED=true
ALIYUN_FC_URL=https://mainland-probe-eyptbwbaco.cn-hangzhou.fcapp.run
# CLOUDFLARE_WORKER_URL 未配置
# SUPABASE_URL 未配置
```

**预期：**
- 爬虫正常运行 ✅
- 高级测速启动 ✅
- CN 节点通过 Aliyun FC 测速 ✅
- 非 CN 节点跳过（因为 Cloudflare 未配置）⏭️
- Supabase 上传跳过 ⏭️

**验证：**
日志中应该看到：
```
⚠️ CLOUDFLARE_WORKER_URL not configured, skipping overseas test
⚠️ Supabase 凭证未配置，跳过上传
```

---

## 🐛 常见问题和调试

### Q1: 高级测速一直没运行

**检查：**
```bash
# 1. 确认环境变量设置
echo $ADVANCED_TEST_ENABLED  # 应该输出 true

# 2. 查看日志是否出现
# "启动高级双地区测速..." 日志

# 3. 检查是否有错误日志
# "高级测速未启用，跳过" 说明配置问题
```

### Q2: Aliyun FC 测速失败

**检查：**
```bash
# 1. 测试 Aliyun FC 连接
curl https://mainland-probe-eyptbwbaco.cn-hangzhou.fcapp.run \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"nodes": [{"id": "test", "host": "1.1.1.1", "port": 443}]}'

# 2. 查看完整错误日志
# 日志中应该有详细的异常信息
```

### Q3: Supabase 上传失败

**检查：**
```bash
# 1. 测试 Supabase 连接
python -c "
from supabase import create_client
supabase = create_client('YOUR_URL', 'YOUR_KEY')
response = supabase.table('nodes').select('count', count='exact').execute()
print(response.count)
"

# 2. 确认表结构
# Supabase Dashboard → SQL Editor
# 运行: SELECT * FROM nodes LIMIT 1;
```

### Q4: 节点数据格式不对

**检查：**
```bash
# 查看实际保存的数据结构
curl http://localhost:8000/nodes/stats | jq '.nodes[0].nodes[0] | keys'

# 应该包含以下字段：
# - id
# - name
# - host
# - port
# - country
# - advanced_speed_score (新增)
# - advanced_latency_mainland 或 advanced_latency_overseas (新增)
# - tested_via (新增)
# - test_time (新增)
```

---

## 📊 性能基准

**单次完整扫描：**
- 基础测速：~2-3 分钟（150 个节点）
- 高级测速：+2-3 分钟
  - Aliyun FC：~1-2 分钟（CN 节点）
  - Cloudflare：~1-2 分钟（非 CN 节点，并发）
- Supabase 上传：~1 分钟
- **总计：~5-7 分钟**

---

## 📝 本地测试检查清单

- [ ] SpiderFlow 后端正常启动
- [ ] `/nodes/stats` API 返回数据
- [ ] 环境变量正确配置
- [ ] 手动触发 `/nodes/trigger` 扫描
- [ ] 观察日志确认高级测速运行
- [ ] 检查 Supabase 是否有新数据
- [ ] 验证节点数据格式正确
- [ ] 测试数据库查询性能
- [ ] 检查没有异常堆栈跟踪
- [ ] 验证 verified_nodes.json 仍然生成

---

## ✅ 部署前清单

在合并到 main 分支之前：

- [ ] 本地所有测试场景都通过
- [ ] Supabase 连接正常（可选）
- [ ] Aliyun FC 和 Cloudflare 连接正常（可选）
- [ ] 没有新增的依赖冲突
- [ ] requirements.txt 已更新
- [ ] .env.example 已更新
- [ ] 日志输出清晰有用
- [ ] 错误处理完善（不会导致爬虫崩溃）

---

**准备好进行部署了？** 🚀
