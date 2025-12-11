# Firebase API Key 自动获取失败修复

## 问题描述

客户端获取账号时报错：
```
Exception: 无法自动获取 Firebase API Key，请手动配置 FIREBASE_API_KEY 环境变量
```

## 原因分析

自动从 Codeium 网站获取 Firebase API Key 失败，可能的原因：
1. 网络连接问题
2. Codeium 网站结构变化
3. 请求超时
4. 防火墙或代理拦截

## 解决方案

### 方案 1：使用后备 API Key（已实现）✅

在代码中添加了一个已知的 Firebase API Key 作为后备方案。当自动获取失败时，会自动使用后备 Key。

**修改文件**：`app/windsurf_login.py`

**主要变更**：

```python
async def get_firebase_api_key(self) -> str:
    # 已知的 Firebase API Key（后备方案）
    FALLBACK_FIREBASE_KEY = 'AIzaSyBSJhvHLwiEeIRuKW7hcJJGUeMUwVHUTQQ'
    
    # 尝试自动获取...
    for url in urls:
        try:
            # 自动获取逻辑
            ...
        except Exception as e:
            print(f"获取 Firebase API Key 失败 ({url}): {str(e)}")
            continue
    
    # 如果自动获取失败，使用后备 API Key
    print(f"⚠️ 自动获取 Firebase API Key 失败，使用后备 API Key")
    return FALLBACK_FIREBASE_KEY
```

**优点**：
- ✅ 无需手动配置
- ✅ 自动降级到后备方案
- ✅ 提高系统稳定性
- ✅ 增加错误日志

**改进**：
- 添加超时控制（10秒主页面，5秒JS文件）
- 限制扫描JS文件数量（最多10个）
- 添加详细的错误日志
- 使用后备API Key确保服务可用

### 方案 2：手动配置环境变量

如果后备 API Key 失效，可以手动配置。

#### 步骤 1：获取 Firebase API Key

访问 https://codeium.com 并查看网页源代码，搜索 `AIza` 开头的字符串。

或者使用浏览器开发者工具：
1. 打开 https://codeium.com
2. 按 F12 打开开发者工具
3. 切换到 Network 标签
4. 刷新页面
5. 搜索包含 `firebaseConfig` 或 `apiKey` 的请求
6. 找到类似 `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` 的字符串

#### 步骤 2：配置环境变量

**Docker 部署**：

编辑 `docker-compose.yml`：
```yaml
services:
  app:
    environment:
      - FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

或者编辑 `.env` 文件：
```bash
FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**本地开发**：

创建或编辑 `.env` 文件：
```bash
FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

#### 步骤 3：重启服务

```bash
# Docker 部署
docker-compose restart

# 本地开发
# 停止服务 (Ctrl+C)
# 重新启动
python run_local.py
```

## 验证修复

### 测试自动获取账号

```bash
curl -X POST "http://localhost:8000/api/client/account/get" \
  -H "X-API-Key: your_key_code"
```

**预期结果**：

成功返回账号信息，或者在日志中看到：
```
⚠️ 自动获取 Firebase API Key 失败，使用后备 API Key
```

### 检查日志

查看服务日志，确认：
- ✅ 没有 Firebase API Key 相关错误
- ✅ 账号登录成功
- ✅ API Key 获取成功

## 后备 API Key 说明

### 当前使用的后备 Key

```
AIzaSyBSJhvHLwiEeIRuKW7hcJJGUeMUwVHUTQQ
```

这是从 Codeium 官方网站提取的 Firebase API Key，用于：
- Firebase Authentication
- 用户登录验证
- 获取 ID Token

### 有效性

- ✅ 这是 Codeium 的公开 API Key
- ✅ 用于客户端认证，不是私密信息
- ✅ 可以在浏览器开发者工具中公开看到
- ⚠️ 如果 Codeium 更换 Key，需要更新

### 更新后备 Key

如果后备 Key 失效，需要：

1. 访问 https://codeium.com
2. 查看网页源代码或网络请求
3. 找到新的 Firebase API Key
4. 更新 `app/windsurf_login.py` 中的 `FALLBACK_FIREBASE_KEY`
5. 重新部署

## 监控建议

### 日志监控

监控以下日志：
- `获取 Firebase API Key 失败` - 自动获取失败
- `使用后备 API Key` - 降级到后备方案
- `Firebase 登录失败` - 后备 Key 可能失效

### 告警规则

建议设置告警：
- 连续多次使用后备 API Key
- Firebase 登录失败率超过阈值
- API Key 获取超时

## 常见问题

### Q1: 为什么要自动获取 Firebase API Key？

**A**: Firebase API Key 是公开的，用于客户端认证。自动获取可以：
- 减少手动配置
- 自动适应 Codeium 的更新
- 提高系统灵活性

### Q2: 后备 API Key 安全吗？

**A**: 是的，Firebase API Key 是设计为公开的：
- 它本身不是敏感信息
- 需要配合用户名密码使用
- 有 Firebase 的安全规则保护
- 可以在任何 Codeium 客户端中找到

### Q3: 如果后备 Key 失效怎么办？

**A**: 
1. 查看日志确认失效
2. 手动获取新的 API Key
3. 更新代码或环境变量
4. 重新部署服务

### Q4: 能否完全禁用自动获取？

**A**: 可以，直接在环境变量中配置：
```bash
FIREBASE_API_KEY=your_api_key_here
```

这样会跳过自动获取，直接使用配置的 Key。

## 相关文档

- [登录功能说明](LOGIN_FEATURE.md)
- [快速开始指南](QUICK_START_LOGIN.md)
- [环境变量配置](.env.example)

## 总结

通过添加后备 Firebase API Key，解决了自动获取失败的问题，提高了系统的稳定性和可用性。

---

**修复日期**: 2024-12-09  
**状态**: ✅ 已修复  
**影响文件**: `app/windsurf_login.py`
