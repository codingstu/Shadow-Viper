# 环境变量配置指南

## 📝 Supabase 环境变量

本项目需要以下环境变量来连接 Supabase 数据库：

| 变量名 | 说明 | 获取方法 |
|--------|------|--------|
| `SUPABASE_URL` | Supabase 项目 URL | [Supabase Dashboard](https://supabase.co) → 项目设置 → API → Project URL |
| `SUPABASE_KEY` | Supabase anon public key | Supabase Dashboard → 项目设置 → API → anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | (可选) Service Role Key | Supabase Dashboard → 项目设置 → API → service_role secret |

## 🔒 安全说明

**⚠️ 重要：不要在代码中硬编码这些凭证！**

- `SUPABASE_KEY` 是 public 的，可以在代码中使用
- `SUPABASE_SERVICE_ROLE_KEY` 是 secret 的，**永远不要提交到版本控制**
- 所有凭证都应该通过环境变量传入

## 🚀 配置方式

### 方式1：本地开发（推荐）

1. 复制 `.env.example` 为 `.env`：
```bash
cp .env.example .env
```

2. 编辑 `.env`，填入你的 Supabase 凭证：
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_public_key
```

3. 安装依赖读取 .env（可选）：
```bash
pip install python-dotenv
```

4. 运行脚本：
```bash
python trigger_supabase_sync.py
```

### 方式2：一行命令

直接在命令行设置环境变量并运行：

```bash
SUPABASE_URL="https://your-project.supabase.co" \
SUPABASE_KEY="your_anon_public_key" \
python trigger_supabase_sync.py
```

### 方式3：导出环境变量

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your_anon_public_key"
python trigger_supabase_sync.py
```

### 方式4：GitHub Actions（CI/CD）

在 GitHub 仓库中配置：

1. 进入 **Settings** → **Secrets and variables** → **Actions**
2. 添加以下 secrets：
   - `SUPABASE_URL` - 你的 Supabase URL
   - `SUPABASE_KEY` - 你的 Supabase Key
   - `SUPABASE_SERVICE_ROLE_KEY` - (可选) Service Role Key

3. 在 GitHub Actions workflow 中使用：
```yaml
- name: Sync to Supabase
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: python trigger_supabase_sync.py
```

### 方式5：Docker

```bash
docker run \
  -e SUPABASE_URL="https://your-project.supabase.co" \
  -e SUPABASE_KEY="your_anon_public_key" \
  your-image-name
```

### 方式6：Vercel / 云部署

在部署平台的环境变量设置中添加：
- `SUPABASE_URL`
- `SUPABASE_KEY`

## ✅ 验证配置

运行脚本，如果看到以下输出说明配置正确：

```
✅ Supabase 环境变量已配置
   URL: https://your-project.supabase.co...
   Key: your_anon_public_key[:30]...
```

## 🛠️ 常见问题

**Q: 脚本提示 "Supabase 环境变量未配置"**
- A: 确保在运行脚本前设置了 `SUPABASE_URL` 和 `SUPABASE_KEY` 环境变量

**Q: 我在本地设置了 .env，但脚本还是不读取**
- A: 脚本不会自动加载 .env，你需要：
  1. 安装 `python-dotenv`: `pip install python-dotenv`
  2. 在脚本开始处添加：
  ```python
  from dotenv import load_dotenv
  load_dotenv()
  ```

**Q: Supabase 上传返回 RLS 错误**
- A: 需要使用 `SUPABASE_SERVICE_ROLE_KEY` 来绕过 RLS 策略，参考上面的方式配置

**Q: 如何同时配置多个环境？**
- A: 为不同环境创建不同的 .env 文件：
  ```bash
  .env.development
  .env.production
  ```
  然后在脚本中指定使用哪个文件

## 📚 参考

- [Supabase 文档](https://supabase.com/docs)
- [Python 环境变量最佳实践](https://12factor.net/config)
