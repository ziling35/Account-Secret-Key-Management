# Windsurf 账号池管理系统

一个基于 FastAPI 的账号池管理和分发系统，用于管理 Windsurf 账号并通过 API 密钥分发给客户端。

## 系统截图

### 仪表盘
![仪表盘](images/dashboard.png)

### 密钥管理
![密钥管理](images/keys-management.png)

### 账号管理
![账号管理](images/accounts-management.png)

## 功能特性

### 管理端功能
- 📊 **数据统计仪表盘** - 实时查看账号和密钥统计信息
- 🔑 **密钥管理** - 批量创建、查询、监控密钥状态
- 👥 **账号管理** - 上传账号文件、查看账号列表和状态
- 📁 **文件解析** - 自动解析账号批量文件并导入数据库

### 客户端API
- 🔐 **密钥验证** - 使用API密钥进行身份验证
- 🔑 **账号密码登录** - 支持通过 Windsurf 账号密码自动获取 API Key
- ⏱️ **频率限制** - 每5分钟只能请求一次账号
- ⏰ **时效管理** - 密钥首次使用时激活，自动计算过期时间
- 📈 **请求统计** - 记录请求次数、IP和时间

## 技术栈

- **后端框架**: FastAPI + Uvicorn
- **数据库**: PostgreSQL + SQLAlchemy
- **前端**: Jinja2 模板 + Bootstrap 5
- **容器化**: Docker + Docker Compose
- **认证**: HTTP Basic Auth (管理端) + API Key (客户端)

## 快速开始

### 方式一：Docker 部署（推荐）

#### 1. 克隆项目
```bash
git clone https://github.com/ZH0531/Account-Secret-Key-Management.git
cd Account-Secret-Key-Management
```

#### 2. 配置环境变量
复制示例配置文件并修改：
```bash
cp .env.example .env
```

编辑 `.env` 文件，修改以下配置：
```env
# 数据库配置
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_strong_password

# 管理员账号（重要：请修改默认密码）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_admin_password

# 安全密钥（使用随机字符串）
SECRET_KEY=your-random-secret-key-here

# 内部上传令牌
INTERNAL_UPLOAD_TOKEN=your-internal-token
```

#### 3. 启动服务
```bash
# 构建并启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 4. 访问系统
- 管理后台: http://localhost:8000/admin
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

使用你在 `.env` 中配置的管理员账号登录。

### 方式二：本地开发运行

#### 1. 安装依赖
```bash
pip install -r requirements.txt
```

#### 2. 配置本地环境
```bash
cp .env.local.example .env.local
```

编辑 `.env.local` 修改配置（默认使用 SQLite）

#### 3. 运行开发服务器
```bash
python run_local.py
```

或使用 uvicorn：
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API使用说明

### 🆕 账号密码登录（新功能）

通过 Windsurf 账号密码自动获取 API Key，无需手动上传账号文件。

**请求示例**:
```bash
curl -X POST "http://localhost:8000/api/client/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "登录成功并创建新账号",
  "data": {
    "email": "your_email@example.com",
    "api_key": "sk-ws-...",
    "name": "用户名",
    "status": "unused",
    "created_at": "2024-01-01T00:00:00"
  }
}
```

> 📖 详细文档请查看 [LOGIN_FEATURE.md](LOGIN_FEATURE.md)

### 客户端获取账号

**请求示例**:
```bash
curl -X POST "http://localhost:8000/api/client/account/get" \
  -H "X-API-Key: your_key_code"
```

**响应示例**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "api_key": "sk-ws-01-xxxxx",
  "name": "John Doe"
}
```

### 查询密钥状态

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/client/key/status" \
  -H "X-API-Key: your_key_code"
```

**响应示例**:
```json
{
  "status": "active",
  "remaining_time": "29天23小时",
  "request_count": 5,
  "activated_at": "2025-11-11T10:00:00",
  "expires_at": "2025-12-11T10:00:00"
}
```

## 数据库设计

### accounts 表
- `id`: 主键
- `email`: 邮箱
- `password`: 密码
- `api_key`: API密钥
- `name`: 姓名
- `status`: 状态 (unused/used)
- `created_at`: 创建时间
- `assigned_at`: 分配时间
- `assigned_to_key`: 分配给的密钥

### keys 表
- `id`: 主键
- `key_code`: 密钥代码
- `duration_days`: 有效期（天）
- `status`: 状态 (inactive/active/expired)
- `created_at`: 创建时间
- `activated_at`: 激活时间
- `expires_at`: 过期时间
- `request_count`: 请求次数
- `last_request_at`: 最后请求时间
- `last_request_ip`: 最后请求IP
- `notes`: 备注

## 账号文件格式

上传的账号文件格式示例：
```
Account 1:
  Email: user1@example.com
  Name: John Doe
  Password: password123
  API Key: sk-ws-01-xxxxx

Account 2:
  Email: user2@example.com
  Name: Jane Smith
  Password: password456
  API Key: sk-ws-01-yyyyy
```

## 开发说明

### 项目结构
```
Account-Secret-Key-Management/
├── app/
│   ├── routers/          # 路由模块
│   │   ├── admin.py      # 管理端路由
│   │   └── client.py     # 客户端路由
│   ├── templates/        # HTML模板
│   ├── static/           # 静态文件
│   ├── database.py       # 数据库配置
│   ├── models.py         # 数据模型
│   ├── schemas.py        # Pydantic模型
│   ├── auth.py           # 认证模块
│   ├── utils.py          # 工具函数
│   ├── windsurf_login.py # 🆕 Windsurf 登录服务
│   └── main.py           # 主应用
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── test_login.py         # 🆕 登录功能测试脚本
├── LOGIN_FEATURE.md      # 🆕 登录功能详细文档
└── README.md
```

### 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `POSTGRES_DB` | PostgreSQL 数据库名 | `windsurf_pool` |
| `POSTGRES_USER` | PostgreSQL 用户名 | `your_db_user` |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | `your_db_password` |
| `DATABASE_URL` | 数据库连接字符串 | `postgresql://user:pass@db:5432/windsurf_pool` |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `your_secure_password` |
| `SECRET_KEY` | 应用密钥 | `random-secret-key` |
| `INTERNAL_UPLOAD_TOKEN` | 内部上传令牌 | `your-internal-token` |
| `ACCOUNT_EXPIRY_DAYS` | 未使用账号自动过期天数 | `6` |
| `FIREBASE_API_KEY` | 🆕 Firebase API Key（可选） | `AIzaSy...` |

## 管理功能说明

### 仪表盘
- 查看系统统计信息（账号总数、密钥总数等）
- 监控账号和密钥状态分布

### 密钥管理
- **创建密钥**：支持单个或批量创建
  - 设置有效期（天数）
  - 添加备注信息
- **密钥类型**：
  - `unlimited`：无限额度（仅限制5分钟请求一次）
  - `limited`：有限额度（可设置总请求次数）
- **多列排序**：支持按多个字段排序（按住 Shift 点击列标题）
- **密钥状态**：
  - `inactive`：未激活
  - `active`：使用中
  - `expired`：已过期

### 账号管理
- **上传账号**：批量导入账号文件
- **账号状态**：
  - `unused`：未使用（创建超过指定天数自动过期，默认6天，可通过 `ACCOUNT_EXPIRY_DAYS` 环境变量配置）
  - `used`：已分配
  - `expired`：已过期
- **查看详情**：查看账号分配记录

## 安全注意事项

1. **生产环境部署**
   - ⚠️ 必须修改 `.env` 中的所有默认密码
   - ⚠️ 使用强密码和随机密钥
   - ⚠️ 建议配置 HTTPS/SSL
   - ⚠️ 限制 8000 端口仅内网访问或配置反向代理

2. **数据安全**
   - 定期备份 PostgreSQL 数据库
   - 密钥一旦创建不可恢复，请妥善保管
   - 账号密码明文存储，注意服务器安全

3. **性能优化**
   - 请求频率限制使用内存缓存（重启会重置）
   - 生产环境建议使用 Redis 持久化缓存

## 常见问题

**Q: 如何重置管理员密码？**  
A: 修改 `.env` 文件中的 `ADMIN_PASSWORD`，然后重启服务：`docker-compose restart`

**Q: 数据库在哪里？**  
A: Docker 部署时数据存储在 `./db_data` 目录，本地开发存储在 `windsurf_pool.db` 文件

**Q: 如何备份数据？**  
A: Docker 部署：`docker exec windsurf-db pg_dump -U your_db_user windsurf_pool > backup.sql`  
本地开发：直接复制 `windsurf_pool.db` 文件

**Q: 客户端请求频率限制如何调整？**  
A: 修改 `app/routers/client.py` 中的 `RATE_LIMIT_SECONDS` 常量（默认 300 秒）

## License

MIT License
