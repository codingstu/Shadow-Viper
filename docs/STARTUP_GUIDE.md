# SpiderFlow 启动脚本使用指南

## 📋 脚本文件说明

SpiderFlow 项目提供了完整的启动脚本套件，可以快速启动前后端服务。

| 脚本文件 | 说明 | 用途 |
|---------|------|------|
| `start-backend.sh` | 启动后端服务 | 启动 FastAPI 后端 (端口 8000) |
| `start-frontend.sh` | 启动前端服务 | 启动 Vite 前端 (端口 5173) |
| `start-all.sh` | 一键启动所有服务 | 方便快速启动 |
| `stop-all.sh` | 停止所有服务 | 优雅停止所有进程 |

## 🚀 快速开始

### 一键启动（推荐）

```bash
# 进入 SpiderFlow 项目目录后
bash start-all.sh
```

这个命令会：
1. ✅ 自动清理旧进程
2. ✅ 启动后端服务 (FastAPI on port 8000)
3. ✅ 显示前端启动说明

### 单独启动后端

```bash
bash start-backend.sh
```

**功能：**
- 检测并清理已有的 uvicorn 进程
- 启动 FastAPI 后端服务
- 自动验证服务是否启动成功
- 日志输出到 `backend.log`

**输出示例：**
```
🚀 启动 SpiderFlow 后端服务...
✅ 旧进程已清理
✅ 后端服务已启动！
📍 API 地址: http://localhost:8000
📍 API 文档: http://localhost:8000/docs
```

### 单独启动前端

在新终端中运行：

```bash
bash start-frontend.sh
```

或者直接使用 npm：

```bash
npm --prefix ./frontend run dev
```

**功能：**
- 自动检查并安装依赖
- 启动 Vite 开发服务器 (Hot Module Replacement 启用)
- 支持热更新

## 🛑 停止服务

```bash
bash stop-all.sh
```

这个命令会：
- 停止所有后端进程 (uvicorn)
- 停止所有前端进程 (Vite/npm)

## 📍 访问地址

启动成功后，访问：

| 服务 | 地址 |
|------|------|
| **前端应用** | http://localhost:5173/ |
| **API 文档** | http://localhost:8000/docs |
| **API 地址** | http://localhost:8000/api/nodes |

## 📝 查看日志

### 查看后端日志

```bash
# 实时查看
tail -f backend.log

# 查看最后50行
tail -50 backend.log
```

### 查看前端日志

前端会直接输出到终端，无单独日志文件。

## ⚙️ 配置说明

### 后端配置

- **服务端口**：8000
- **绑定地址**：0.0.0.0
- **日志级别**：INFO
- **自动扫描周期**：10分钟

### 前端配置

- **服务端口**：5173
- **开发模式**：启用热更新 (HMR)
- **框架**：Vue 3 + Vite

## 🔧 常见问题

### Q: 启动后报错 "address already in use"？

**A:** 说明已有进程占用端口，脚本会自动清理：

```bash
# 手动清理
pkill -9 -f "uvicorn\|vite"

# 然后重新启动
bash start-all.sh
```

### Q: 前端启动失败？

**A:** 检查依赖是否安装：

```bash
cd frontend
npm install
npm run dev
```

### Q: API 文档无法访问？

**A:** 确认后端已启动：

```bash
curl http://localhost:8000/docs
```

### Q: 需要查看详细启动日志？

**A:** 查看日志文件：

```bash
# 后端日志
cat backend.log

# 实时监控
tail -f backend.log
```

## 💡 技巧

### 后台启动并查看日志

```bash
bash start-backend.sh && tail -f backend.log
```

### 后台启动所有服务

```bash
bash start-all.sh &
```

### 定期自动扫描

后端已配置每10分钟自动扫描一次节点，无需手动干预。

## 📦 依赖要求

- **Python** 3.8+
- **Node.js** 16+
- **npm** 8+

## 🎯 工作流

```
1. bash start-all.sh  (启动所有服务)
    ├─ 启动后端 (FastAPI on 8000)
    └─ 显示前端启动说明
    
2. 新终端: bash start-frontend.sh (启动前端)
    └─ 启动前端 (Vite on 5173)
    
3. 访问 http://localhost:5173
    └─ 查看界面和节点数据
    
4. 修改代码自动重载
    └─ 前端: Vite HMR
    └─ 后端: 修改需重启
    
5. bash stop-all.sh (停止服务)
    ├─ 关闭后端
    └─ 关闭前端
```

---

**更新时间**：2025年12月31日
