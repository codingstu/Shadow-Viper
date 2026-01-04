# SpiderFlow 文档总览

**更新时间**：2026-01-05  
**文档状态**：✅ 完全重构，现仅保留两个核心文档

---

## 📚 核心文档

### 1️⃣ [项目结构与学习记录](01_PROJECT_STRUCTURE_AND_LEARNING.md)

**用途**：了解项目全貌、技术栈、架构设计

**内容**：
- 📐 整体架构图与文件树
- 🔴 核心模块详解（Node Hunter）
- 🛠️ 技术栈与学习内容
- 🚀 部署架构演变历程
- 📊 关键学习总结

**适合**：
- 新人快速上手
- 理解项目设计思想
- 学习最佳实践

---

### 2️⃣ [修复与优化完整记录](02_FIXES_AND_OPTIMIZATION_LOG.md)

**用途**：查阅所有修复和优化的详细过程

**内容**：
- 🐛 2026-01-05：httpx 代理参数修复
- 🔧 2026-01-04：Supabase 同步优化
- 🚀 2026-01-01：双地区测速迁移
- 📈 2025-12：三层级检测框架
- 📋 问题排查流程与清单
- 🧠 关键经验与学习

**适合**：
- 遇到问题时查阅
- 了解修复历程
- 防止重复踩坑

---

## 🔗 文档导航

```
SpiderFlow/docs/
├── 📘 01_PROJECT_STRUCTURE_AND_LEARNING.md    ← 开发人员必读
├── 📗 02_FIXES_AND_OPTIMIZATION_LOG.md        ← 遇到问题时查阅
└── 📄 DOCUMENTATION_INDEX.md                   ← 本文档
```

---

## 💡 快速查找

### 我想...

**了解项目整体架构**
→ 阅读 [01_PROJECT_STRUCTURE_AND_LEARNING.md](01_PROJECT_STRUCTURE_AND_LEARNING.md) 的"整体架构"部分

**学习异步编程**
→ 阅读 [01_PROJECT_STRUCTURE_AND_LEARNING.md](01_PROJECT_STRUCTURE_AND_LEARNING.md) 的"技术栈与学习内容"

**查看所有修复**
→ 阅读 [02_FIXES_AND_OPTIMIZATION_LOG.md](02_FIXES_AND_OPTIMIZATION_LOG.md)

**解决 AsyncClient 错误**
→ 查阅 [02_FIXES_AND_OPTIMIZATION_LOG.md](02_FIXES_AND_OPTIMIZATION_LOG.md) 的"2026-01-05"部分

**部署到生产环境**
→ 查看 [02_FIXES_AND_OPTIMIZATION_LOG.md](02_FIXES_AND_OPTIMIZATION_LOG.md) 的"部署检查清单"

**了解 Supabase 问题**
→ 查阅 [02_FIXES_AND_OPTIMIZATION_LOG.md](02_FIXES_AND_OPTIMIZATION_LOG.md) 的"2026-01-04"部分

**学习云平台选择**
→ 阅读 [01_PROJECT_STRUCTURE_AND_LEARNING.md](01_PROJECT_STRUCTURE_AND_LEARNING.md) 的"部署架构演变"

---

## 📝 文档编写规范

为了保持文档质量，新的修复应按以下格式记录到 `02_FIXES_AND_OPTIMIZATION_LOG.md`：

```markdown
## YYYY-MM-DD: 简短标题

### 🐛 问题描述

**症状**：用户看到的现象
**根本原因**：深层原因分析

### 修复方案

代码对比或解决步骤

### 修改的文件

| 文件 | 改动 | 原因 |
|------|------|------|

### 提交记录

```
Commit: xxxxx
Message: ...
```

### 测试验证

✅ 验证内容

### 关键学习

1. 学到的第一点
2. 学到的第二点
```

---

## 🗑️ 过时文档（已归档）

以下文档已合并到核心文档中，不再单独维护：

- CHANGELOG.md → 02_FIXES_AND_OPTIMIZATION_LOG.md
- PROJECT_ARCHITECTURE.md → 01_PROJECT_STRUCTURE_AND_LEARNING.md
- QUICK_REFERENCE.md → 合并到核心文档
- DEPLOYMENT_PLAN.md → 02_FIXES_AND_OPTIMIZATION_LOG.md#部署检查清单
- 其他诊断/报告文档 → 02_FIXES_AND_OPTIMIZATION_LOG.md#问题排查流程

**归档说明**：
- 保留的原因：保持Git历史完整
- 使用建议：不必阅读这些文档，查阅核心文档即可
- 清理时机：项目长期稳定后可考虑删除

---

## 📊 文档统计

| 指标 | 值 |
|------|-----|
| 核心文档 | 2个 |
| 核心文档行数 | ~1500行 |
| 代码示例 | 30+个 |
| 修复记录 | 4个 |
| 学习点 | 15+个 |
| 问题排查流程 | 4个 |
| 配置清单 | 2个 |

---

## ✅ 质量保证

- ✅ 所有修复都有提交记录可追踪
- ✅ 每个修复都有测试验证
- ✅ 关键学习点已整理
- ✅ 问题排查流程完整
- ✅ 部署清单可用
- ✅ 无重复或遗漏内容

---

**下次修复/优化时**，请及时更新 `02_FIXES_AND_OPTIMIZATION_LOG.md`，保持文档最新！
