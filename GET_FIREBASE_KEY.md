# 如何获取 Firebase API Key

## 问题

后备的 Firebase API Key 已失效，错误信息：
```
Exception: 登录失败: API key not valid. Please pass a valid API key.
```

## 解决方案：手动获取 Firebase API Key

### 方法 1：从浏览器开发者工具获取（推荐）

#### 步骤 1：打开 Windsurf 网站

访问：https://windsurf.com 或 https://codeium.com

#### 步骤 2：打开开发者工具

- **Chrome/Edge**: 按 `F12` 或右键 → 检查
- **Firefox**: 按 `F12` 或右键 → 检查元素

#### 步骤 3：查看网络请求

1. 切换到 **Network** (网络) 标签
2. 刷新页面 (`F5`)
3. 在过滤框中搜索 `firebase` 或 `identitytoolkit`

#### 步骤 4：查找 API Key

在网络请求中找到类似这样的 URL：
```
https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSy...
```

`key=` 后面的字符串就是 Firebase API Key。

#### 步骤 5：复制 API Key

API Key 格式：`AIza` 开头，共 39 个字符
```
AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### 方法 2：从网页源代码获取

#### 步骤 1：查看网页源代码

- 访问 https://windsurf.com
- 右键 → 查看网页源代码 (或按 `Ctrl+U`)

#### 步骤 2：搜索 API Key

在源代码中搜索（`Ctrl+F`）：
- `AIza`
- `firebaseConfig`
- `apiKey`

#### 步骤 3：提取 API Key

找到类似这样的代码：
```javascript
firebaseConfig = {
  apiKey: "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  ...
}
```

### 方法 3：从 JavaScript 文件获取

#### 步骤 1：打开开发者工具

按 `F12` → 切换到 **Sources** (源代码) 标签

#### 步骤 2：搜索 JavaScript 文件

在左侧文件列表中找到：
- `main.js`
- `app.js`
- `chunk-*.js`

#### 步骤 3：搜索 API Key

在文件中搜索 `AIza`，找到 Firebase API Key。

## 配置 Firebase API Key

### 方法 1：通过环境变量（推荐）

#### Docker 部署

编辑 `.env` 文件：
```bash
# ================== Firebase API Key ==================
FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

重启服务：
```bash
docker-compose down
docker-compose up -d
```

#### 本地开发

创建或编辑 `.env` 文件：
```bash
FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

重启服务：
```bash
# 停止服务 (Ctrl+C)
# 重新启动
python run_local.py
```

### 方法 2：直接修改代码（不推荐）

编辑 `app/windsurf_login.py`：

```python
# 已知的 Firebase API Key（后备方案）
FALLBACK_FIREBASE_KEY = 'AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'  # 替换为新的 Key
```

**注意**：这种方法不推荐，因为：
- 需要修改代码
- 更新代码时可能丢失配置
- 不便于管理

## 验证配置

### 测试获取账号

```bash
curl -X POST "http://localhost:8010/api/client/account/get" \
  -H "X-API-Key: your_key_code"
```

### 检查日志

查看服务日志，确认：
```
✅ Firebase 登录成功
✅ 获取到 API Key
```

如果看到错误：
```
❌ 登录失败: API key not valid
```

说明 Firebase API Key 仍然无效，需要重新获取。

## 常见问题

### Q1: Firebase API Key 是什么？

**A**: Firebase API Key 是 Google Firebase 服务的公开密钥，用于：
- 客户端身份验证
- Firebase Authentication 服务
- 用户登录和注册

### Q2: Firebase API Key 是敏感信息吗？

**A**: 不是。Firebase API Key 是设计为公开的：
- 可以在客户端代码中看到
- 可以在浏览器开发者工具中看到
- 不需要保密
- 安全性由 Firebase 的安全规则保护

### Q3: Firebase API Key 会过期吗？

**A**: 一般不会过期，但可能会：
- 被服务提供商更换
- 被禁用或限制
- 需要定期更新

### Q4: 如何知道 API Key 是否有效？

**A**: 测试方法：
```bash
curl -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword",
    "returnSecureToken": true
  }'
```

如果返回错误 `API key not valid`，说明 Key 无效。

### Q5: 能否使用自己的 Firebase 项目？

**A**: 理论上可以，但不推荐：
- 需要配置 Firebase 项目
- 需要设置认证规则
- 需要与 Windsurf 后端兼容
- 可能导致功能异常

## 最新的 Firebase API Key

**重要提示**：以下 Key 可能已过期，请按照上述方法获取最新的 Key。

### 已知的历史 Key（可能已失效）

```
AIzaSyBSJhvHLwiEeIRuKW7hcJJGUeMUwVHUTQQ  # 已失效 (2024-12-09)
```

### 获取最新 Key

请访问 https://windsurf.com 并按照上述方法获取最新的 Firebase API Key。

## 自动化脚本

### 使用 curl 获取

```bash
#!/bin/bash
# 从 Windsurf 网站获取 Firebase API Key

echo "正在获取 Firebase API Key..."

# 下载首页
HTML=$(curl -s https://windsurf.com)

# 提取 API Key
API_KEY=$(echo "$HTML" | grep -oP 'AIza[0-9A-Za-z_-]{35}' | head -1)

if [ -n "$API_KEY" ]; then
    echo "找到 Firebase API Key: $API_KEY"
    echo "请将此 Key 添加到 .env 文件中："
    echo "FIREBASE_API_KEY=$API_KEY"
else
    echo "未找到 Firebase API Key，请手动查找"
fi
```

### 使用 Python 获取

```python
import re
import requests

def get_firebase_key():
    """从 Windsurf 网站获取 Firebase API Key"""
    urls = [
        'https://windsurf.com',
        'https://codeium.com'
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            html = response.text
            
            # 搜索 API Key
            match = re.search(r'AIza[0-9A-Za-z_-]{35}', html)
            if match:
                return match.group(0)
        except Exception as e:
            print(f"获取失败 ({url}): {e}")
            continue
    
    return None

if __name__ == '__main__':
    api_key = get_firebase_key()
    if api_key:
        print(f"找到 Firebase API Key: {api_key}")
        print(f"\n请将此 Key 添加到 .env 文件中：")
        print(f"FIREBASE_API_KEY={api_key}")
    else:
        print("未找到 Firebase API Key，请手动查找")
```

## 总结

1. **获取 Firebase API Key**：从浏览器开发者工具或网页源代码中获取
2. **配置环境变量**：将 Key 添加到 `.env` 文件中
3. **重启服务**：使配置生效
4. **验证功能**：测试账号获取功能

---

**更新日期**: 2024-12-09  
**状态**: 需要手动获取最新的 Firebase API Key
