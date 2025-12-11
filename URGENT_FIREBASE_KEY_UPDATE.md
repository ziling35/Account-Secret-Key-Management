# 🚨 紧急：Firebase API Key 需要更新

## 问题

当前后备的 Firebase API Key 已失效，导致账号获取功能报错：

```
Exception: 登录失败: API key not valid. Please pass a valid API key.
```

## 快速解决方案

### 方案 1：使用自动获取脚本（推荐）

```bash
# 运行自动获取脚本
python get_firebase_key.py
```

脚本会自动从 Windsurf 网站获取最新的 Firebase API Key，并提示你如何配置。

### 方案 2：手动获取并配置

#### 步骤 1：获取 Firebase API Key

**方法 A - 浏览器开发者工具（最简单）**

1. 访问 https://windsurf.com
2. 按 `F12` 打开开发者工具
3. 切换到 **Network** (网络) 标签
4. 刷新页面 (`F5`)
5. 在过滤框中搜索 `firebase` 或 `identitytoolkit`
6. 找到类似这样的请求：
   ```
   https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSy...
   ```
7. 复制 `key=` 后面的值（以 `AIza` 开头，共39个字符）

**方法 B - 查看网页源代码**

1. 访问 https://windsurf.com
2. 右键 → 查看网页源代码 (或按 `Ctrl+U`)
3. 按 `Ctrl+F` 搜索 `AIza`
4. 找到 Firebase API Key（格式：`AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`）

#### 步骤 2：配置环境变量

编辑 `.env` 文件，添加或更新：

```bash
# ================== Firebase API Key ==================
FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**重要**：将 `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` 替换为你获取到的实际 Key。

#### 步骤 3：重启服务

**Docker 部署：**
```bash
docker-compose down
docker-compose up -d
```

**本地开发：**
```bash
# 停止服务 (Ctrl+C)
# 重新启动
python run_local.py
```

#### 步骤 4：验证

测试账号获取功能：

```bash
curl -X POST "http://localhost:8010/api/client/account/get" \
  -H "X-API-Key: your_key_code"
```

应该返回账号信息，不再报错。

## 为什么会失效？

Firebase API Key 可能因以下原因失效：

1. **服务提供商更换了 Key** - Windsurf/Codeium 更新了他们的 Firebase 配置
2. **Key 被禁用** - 由于滥用或安全原因被禁用
3. **服务迁移** - 从 Codeium 迁移到 Windsurf 时更换了配置

## 长期解决方案

### 1. 定期更新

建议每月检查一次 Firebase API Key 是否仍然有效。

### 2. 监控告警

设置监控，当出现 `API key not valid` 错误时发送告警。

### 3. 多个后备 Key

在代码中配置多个后备 Key，自动尝试：

```python
FALLBACK_KEYS = [
    'AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',  # 主 Key
    'AIzaSyYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY',  # 备用 Key 1
    'AIzaSyZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ',  # 备用 Key 2
]
```

### 4. 自动更新脚本

设置定时任务，自动获取最新的 Firebase API Key：

```bash
# 添加到 crontab
0 0 * * * cd /path/to/project && python get_firebase_key.py >> firebase_key_update.log 2>&1
```

## 相关文档

- [详细获取指南](GET_FIREBASE_KEY.md) - 完整的获取和配置说明
- [Firebase API Key 修复](FIREBASE_API_KEY_FIX.md) - 技术细节和原理
- [环境变量配置](.env.example) - 所有环境变量说明

## 需要帮助？

如果遇到问题：

1. 查看日志：`docker-compose logs -f app`
2. 检查配置：确认 `.env` 文件中的 `FIREBASE_API_KEY` 已正确设置
3. 验证 Key：使用 curl 测试 Firebase API
4. 查看文档：阅读 `GET_FIREBASE_KEY.md`

## 检查清单

- [ ] 已获取最新的 Firebase API Key
- [ ] 已更新 `.env` 文件
- [ ] 已重启服务
- [ ] 已测试账号获取功能
- [ ] 日志中没有 API Key 相关错误

---

**更新日期**: 2024-12-09  
**优先级**: 🚨 紧急  
**状态**: ⚠️ 需要立即处理
