# 更新日志

## [v1.2.0] - 2024-12-09

### 🎉 新增功能

#### API Key 可选功能
- ✨ 上传账号时 API Key 字段变为可选
- ✨ 客户端获取账号时自动登录获取 API Key
- ✨ 支持混合格式账号文件（部分有 API Key，部分没有）
- ✨ 智能检测：有 API Key 直接使用，没有则自动获取

#### 账号去重功能
- ✨ 同一密钥多次获取账号时自动排除之前获取过的账号
- ✨ 确保每次获取到的都是新的、不同的账号
- ✨ 用户切换账号时自动获取新账号
- ✨ 明确区分"无可用账号"和"无新账号"的错误提示

### 🔧 技术改进

#### 数据库结构更新
- 修改 `accounts.api_key` 字段为可空
- 修改 `accounts.name` 字段为可空
- 新增数据库迁移脚本 `migrate_api_key_optional.py`

#### 账号解析优化
- 更新 `parse_account_file()` 函数，API Key 变为可选字段
- 只需要邮箱、姓名、密码即可导入账号

#### 客户端接口增强
- `/api/client/account/get` 接口自动检测并获取 API Key
- 获取失败时返回明确的错误信息
- 自动更新账号信息到数据库
- 智能账号分配：自动排除该密钥之前获取过的账号
- 优化错误提示：区分不同的无账号情况

### 📚 文档更新

- ✅ 新增 `OPTIONAL_API_KEY.md`: API Key 可选功能详细说明
- ✅ 新增 `UNIQUE_ACCOUNT_FEATURE.md`: 账号去重功能详细说明
- ✅ 新增 `migrate_api_key_optional.py`: 数据库迁移脚本
- ✅ 更新 `CHANGELOG.md`: 添加 v1.2.0 更新日志

### 🔄 迁移指南

#### 升级步骤

1. **备份数据库**
```bash
# PostgreSQL
docker exec windsurf-db pg_dump -U your_user windsurf_pool > backup.sql

# SQLite
cp windsurf_pool.db windsurf_pool.db.backup
```

2. **运行迁移脚本**
```bash
python migrate_api_key_optional.py
```

3. **重启服务**
```bash
docker-compose restart  # Docker 部署
# 或重新运行本地服务
```

### 💡 使用场景

#### 场景 1：简化账号准备
```
# 旧方式：需要预先获取所有 API Key
Account 1:
  Email: user@example.com
  Name: User
  Password: pass123
  API Key: sk-ws-01-xxxxx

# 新方式：只需要邮箱和密码
Account 1:
  Email: user@example.com
  Name: User
  Password: pass123
```

#### 场景 2：按需获取
- 账号导入时不获取 API Key
- 客户端请求时才自动获取
- 避免提前获取导致的过期问题

### ⚠️ 注意事项

1. **首次使用延迟**：没有 API Key 的账号首次使用需要 2-5 秒获取
2. **密码正确性**：确保上传的密码正确，否则无法自动获取
3. **网络依赖**：需要访问 Firebase 和 Windsurf API
4. **数据库迁移**：升级前必须运行迁移脚本

---

## [v1.1.0] - 2024-12-09

### 🎉 新增功能

#### 账号密码登录功能
- ✨ 新增 `/api/client/login` 接口，支持通过 Windsurf 账号密码自动获取 API Key
- ✨ 自动模拟登录流程，无需手动上传账号文件
- ✨ 自动获取 Firebase API Key，无需手动配置
- ✨ 账号自动去重，避免重复创建
- ✨ 完善的错误处理和提示信息

### 📝 技术实现

#### 新增模块
- `app/windsurf_login.py`: Windsurf 登录服务核心模块
  - `WindsurfLoginService`: 登录服务类
  - `windsurf_login()`: 便捷登录函数
  - 支持 Firebase 认证
  - 支持 Windsurf API 集成
  - 自动获取和创建 API Key

#### 新增接口
- `POST /api/client/login`: 账号密码登录接口
  - 请求参数: `email`, `password`
  - 返回: `success`, `message`, `data` (包含 email, api_key, name 等)

#### 新增依赖
- `httpx>=0.24.0`: 异步 HTTP 客户端

#### 配置更新
- 新增环境变量 `FIREBASE_API_KEY` (可选)
- 更新 `.env.example` 添加 Firebase 配置说明

### 📚 文档更新

- ✅ 新增 `LOGIN_FEATURE.md`: 登录功能详细文档
- ✅ 新增 `test_login.py`: 登录功能测试脚本
- ✅ 更新 `README.md`: 添加登录功能说明
- ✅ 新增 `CHANGELOG.md`: 版本更新日志

### 🔧 技术特性

1. **自动化登录流程**
   - 自动扫描 Windsurf 网页获取 Firebase API Key
   - 通过 Firebase 进行身份认证
   - 调用 Windsurf API 获取或创建 API Key
   - 支持备用方案确保成功率

2. **智能账号管理**
   - 检查账号是否已存在
   - 自动去重避免重复创建
   - 保存完整账号信息到数据库

3. **错误处理**
   - 密码错误提示
   - 邮箱未注册提示
   - 网络错误处理
   - API 调用失败处理

4. **异步处理**
   - 使用 `httpx.AsyncClient` 异步请求
   - 不阻塞服务器主线程
   - 提高并发处理能力

### 📖 使用示例

#### cURL 请求
```bash
curl -X POST "http://localhost:8000/api/client/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

#### Python 测试
```bash
python test_login.py your_email@example.com your_password
```

### 🔗 参考项目

本功能基于 `windsurf-api全方位逆向` 项目的逆向分析结果实现，感谢原项目提供的 API 接口文档。

### ⚠️ 注意事项

1. **Firebase API Key**: 系统会自动获取，但如果失败可以手动配置
2. **账号安全**: 密码会存储在数据库中，请确保服务器安全
3. **速率限制**: 建议对登录接口添加速率限制防止滥用
4. **HTTPS**: 生产环境建议使用 HTTPS 保护密码传输

---

## [v1.0.0] - 2024-11-XX

### 初始版本

- ✅ 账号池管理系统
- ✅ 密钥管理功能
- ✅ 客户端 API 接口
- ✅ 管理后台界面
- ✅ Docker 容器化部署
- ✅ PostgreSQL 数据库支持
