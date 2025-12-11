# 账号密码登录功能说明

## 功能概述

新增了通过 Windsurf 账号密码登录并自动获取 API Key 的功能。系统会自动模拟登录流程，通过 Firebase 认证和 Windsurf API 获取账号的 API Key。

## 技术实现

基于 `windsurf-api全方位逆向` 项目的逆向分析结果，实现了以下登录流程：

1. **Firebase 认证**：使用邮箱密码通过 Firebase API 登录
2. **获取 Auth Token**：使用 Firebase Token 获取 Windsurf Auth Token
3. **注册/获取 API Key**：通过 RegisterUser 接口获取 API Key
4. **备用方案**：如果 RegisterUser 失败，使用 CreateTeamApiSecret 创建新的 API Key

## API 接口

### POST `/api/client/login`

通过账号密码登录并获取 API Key。

**请求体：**
```json
{
  "email": "your_email@example.com",
  "password": "your_password"
}
```

**成功响应：**
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

**失败响应：**
```json
{
  "success": false,
  "message": "登录失败: 密码错误",
  "data": null
}
```

## 使用示例

### cURL 示例

```bash
curl -X POST "http://localhost:8000/api/client/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

### Python 示例

```python
import requests

response = requests.post(
    "http://localhost:8000/api/client/login",
    json={
        "email": "your_email@example.com",
        "password": "your_password"
    }
)

result = response.json()
if result["success"]:
    print(f"登录成功！")
    print(f"API Key: {result['data']['api_key']}")
    print(f"用户名: {result['data']['name']}")
else:
    print(f"登录失败: {result['message']}")
```

### JavaScript 示例

```javascript
fetch('http://localhost:8000/api/client/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'your_email@example.com',
    password: 'your_password'
  })
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    console.log('登录成功！');
    console.log('API Key:', data.data.api_key);
    console.log('用户名:', data.data.name);
  } else {
    console.log('登录失败:', data.message);
  }
});
```

## 配置说明

### 环境变量

在 `.env` 文件中可以配置 Firebase API Key（可选）：

```env
# Firebase API Key（可选）
# 如果不设置，系统会自动从 Windsurf 网页获取
FIREBASE_API_KEY=your_firebase_api_key_here
```

### 获取 Firebase API Key（可选）

如果自动获取失败，可以手动获取：

1. 访问 https://codeium.com/windsurf
2. 打开浏览器开发者工具（F12）
3. 切换到 Sources 标签
4. 搜索 `apiKey` 或 `firebase`
5. 找到类似 `AIzaSy...` 的字符串
6. 将其配置到 `.env` 文件中

## 功能特性

### 1. 自动获取 Firebase API Key

系统会自动扫描 Windsurf 网页和 JS 文件，提取 Firebase API Key，无需手动配置。

### 2. 账号去重

如果数据库中已存在相同邮箱的账号，会直接返回现有账号信息，不会重复创建。

### 3. 错误处理

- **密码错误**：返回明确的错误提示
- **邮箱未注册**：返回邮箱未注册提示
- **网络错误**：返回网络请求失败提示
- **API Key 获取失败**：尝试备用方案

### 4. 异步处理

使用 `httpx.AsyncClient` 进行异步 HTTP 请求，不会阻塞服务器。

## 文件结构

```
app/
├── windsurf_login.py          # 登录服务模块
├── schemas.py                 # 新增 LoginRequest 和 LoginResponse
└── routers/
    └── client.py              # 新增 /api/client/login 接口
```

## 核心模块说明

### `app/windsurf_login.py`

登录服务核心模块，提供以下功能：

- `WindsurfLoginService`: 登录服务类
  - `get_firebase_api_key()`: 自动获取 Firebase API Key
  - `login_with_firebase()`: Firebase 登录
  - `register_user()`: 注册用户并获取 API Key
  - `get_windsurf_auth_token()`: 获取 Auth Token（备用）
  - `create_api_key()`: 创建新的 API Key（备用）
  - `login_and_get_api_key()`: 完整登录流程

- `windsurf_login()`: 便捷函数，快速登录并获取 API Key

## 安全建议

1. **HTTPS**：生产环境建议使用 HTTPS 保护密码传输
2. **速率限制**：建议对登录接口添加速率限制，防止暴力破解
3. **日志记录**：记录登录尝试，便于安全审计
4. **密码存储**：数据库中的密码建议加密存储

## 故障排查

### 问题：自动获取 Firebase API Key 失败

**解决方案：**
1. 检查网络连接
2. 手动获取 Firebase API Key 并配置到 `.env`
3. 检查 Windsurf 网站是否可访问

### 问题：登录失败，提示密码错误

**解决方案：**
1. 确认邮箱和密码正确
2. 尝试在 Windsurf 官网登录验证
3. 检查账号是否被锁定

### 问题：获取 API Key 失败

**解决方案：**
1. 检查 Windsurf API 是否正常
2. 查看服务器日志获取详细错误信息
3. 尝试重新登录

## 依赖项

新增依赖：
- `httpx>=0.24.0`: 异步 HTTP 客户端

安装依赖：
```bash
pip install -r requirements.txt
```

## 测试

### 测试登录接口

```bash
# 测试成功登录
curl -X POST "http://localhost:8000/api/client/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test_password"
  }'

# 测试错误密码
curl -X POST "http://localhost:8000/api/client/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "wrong_password"
  }'
```

## 更新日志

### v1.1.0 (2024-01-01)

- ✨ 新增账号密码登录功能
- ✨ 自动获取 Firebase API Key
- ✨ 支持通过模拟登录获取 API Key
- ✨ 账号自动去重
- ✨ 完善的错误处理机制

## 参考资料

- 基于项目：`windsurf-api全方位逆向`
- Firebase Authentication API
- Windsurf Web Backend API
