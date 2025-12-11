# 账号密码登录功能 - 快速开始

## 5分钟快速上手

### 1️⃣ 安装依赖

如果是新安装，需要更新依赖：

```bash
pip install -r requirements.txt
```

或者只安装新增的依赖：

```bash
pip install httpx>=0.24.0
```

### 2️⃣ 启动服务

#### Docker 部署
```bash
docker-compose down
docker-compose up -d --build
```

#### 本地开发
```bash
python run_local.py
```

### 3️⃣ 测试登录

#### 方法一：使用测试脚本

```bash
python test_login.py your_email@example.com your_password
```

#### 方法二：使用 cURL

```bash
curl -X POST "http://localhost:8000/api/client/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

#### 方法三：使用 Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/client/login",
    json={
        "email": "your_email@example.com",
        "password": "your_password"
    }
)

print(response.json())
```

### 4️⃣ 查看结果

成功响应示例：

```json
{
  "success": true,
  "message": "登录成功并创建新账号",
  "data": {
    "email": "your_email@example.com",
    "api_key": "sk-ws-01-xxxxxxxxxx",
    "name": "用户名",
    "status": "unused",
    "created_at": "2024-12-09T10:00:00"
  }
}
```

## 常见场景

### 场景1：批量导入账号

创建一个 Python 脚本批量导入：

```python
import asyncio
import aiohttp

accounts = [
    {"email": "user1@example.com", "password": "pass1"},
    {"email": "user2@example.com", "password": "pass2"},
    {"email": "user3@example.com", "password": "pass3"},
]

async def login_account(session, account):
    async with session.post(
        "http://localhost:8000/api/client/login",
        json=account
    ) as response:
        result = await response.json()
        if result["success"]:
            print(f"✅ {account['email']}: {result['data']['api_key']}")
        else:
            print(f"❌ {account['email']}: {result['message']}")

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [login_account(session, acc) for acc in accounts]
        await asyncio.gather(*tasks)

asyncio.run(main())
```

### 场景2：集成到现有系统

```python
from app.windsurf_login import windsurf_login

async def add_account(email: str, password: str):
    """添加账号到系统"""
    try:
        result = await windsurf_login(email, password)
        print(f"账号添加成功: {result['email']}")
        print(f"API Key: {result['api_key']}")
        return result
    except Exception as e:
        print(f"添加失败: {str(e)}")
        return None
```

### 场景3：Web 表单集成

前端 HTML：

```html
<form id="loginForm">
  <input type="email" name="email" placeholder="邮箱" required>
  <input type="password" name="password" placeholder="密码" required>
  <button type="submit">登录</button>
</form>

<script>
document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData(e.target);
  const data = {
    email: formData.get('email'),
    password: formData.get('password')
  };
  
  const response = await fetch('/api/client/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  
  const result = await response.json();
  
  if (result.success) {
    alert('登录成功！API Key: ' + result.data.api_key);
  } else {
    alert('登录失败: ' + result.message);
  }
});
</script>
```

## 配置选项

### 可选：配置 Firebase API Key

如果自动获取失败，可以手动配置：

1. 编辑 `.env` 文件：
```env
FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

2. 重启服务：
```bash
docker-compose restart  # Docker 部署
# 或
# 重新运行 python run_local.py
```

### 获取 Firebase API Key

1. 访问 https://codeium.com/windsurf
2. 打开浏览器开发者工具（F12）
3. 切换到 **Sources** 标签
4. 按 `Ctrl+F` 搜索 `apiKey`
5. 找到类似 `AIzaSy...` 的字符串
6. 复制到 `.env` 文件

## 故障排查

### 问题：登录失败，提示"密码错误"

**解决方案：**
- 确认邮箱和密码正确
- 尝试在 Windsurf 官网登录验证
- 检查是否有特殊字符需要转义

### 问题：提示"无法自动获取 Firebase API Key"

**解决方案：**
- 检查网络连接
- 手动获取并配置 `FIREBASE_API_KEY`
- 检查 Windsurf 网站是否可访问

### 问题：账号已存在

**说明：**
- 这不是错误，系统会返回现有账号信息
- 避免重复创建账号
- 可以直接使用返回的 API Key

## API 文档

访问 http://localhost:8000/docs 查看完整的 API 文档，包括：

- 请求参数说明
- 响应格式说明
- 错误码说明
- 在线测试功能

## 下一步

1. ✅ 测试登录功能
2. ✅ 集成到你的应用
3. ✅ 配置生产环境
4. ✅ 添加速率限制
5. ✅ 启用 HTTPS

## 需要帮助？

- 📖 查看详细文档：[LOGIN_FEATURE.md](LOGIN_FEATURE.md)
- 📝 查看更新日志：[CHANGELOG.md](CHANGELOG.md)
- 🐛 遇到问题？提交 Issue
- 💡 有建议？欢迎 PR

## 性能建议

### 生产环境优化

1. **添加速率限制**
```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # 每分钟最多5次
async def login_with_account(request: Request, ...):
    ...
```

2. **启用缓存**
```python
# 缓存 Firebase API Key
import functools

@functools.lru_cache(maxsize=1)
async def get_cached_firebase_key():
    return await get_firebase_api_key()
```

3. **异步处理**
```python
# 后台任务处理
from fastapi import BackgroundTasks

@router.post("/login")
async def login_with_account(
    background_tasks: BackgroundTasks,
    ...
):
    # 主要逻辑
    result = await windsurf_login(...)
    
    # 后台任务：记录日志、发送通知等
    background_tasks.add_task(log_login_event, result)
    
    return result
```

## 安全建议

1. ✅ 使用 HTTPS 保护密码传输
2. ✅ 添加速率限制防止暴力破解
3. ✅ 记录登录日志用于审计
4. ✅ 定期备份数据库
5. ✅ 限制 API 访问来源

---

**祝你使用愉快！** 🎉
