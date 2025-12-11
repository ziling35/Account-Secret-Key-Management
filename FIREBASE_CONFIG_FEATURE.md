# Firebase API Key 后台配置功能

## 功能概述

现在可以在管理后台直接配置和测试 Firebase API Key，无需手动修改环境变量或代码。

## 功能特性

### 1. 可视化配置界面

在管理后台的 **系统设置** 页面，新增了 **Firebase API Key 配置** 卡片。

**访问路径**：
```
http://your-domain/admin/settings
```

### 2. 主要功能

#### ✅ 配置 Firebase API Key
- 输入框支持密码显示/隐藏
- 自动格式验证（必须以 AIza 开头，共39个字符）
- 保存到数据库，无需重启服务

#### ✅ 测试连接
- 点击"测试连接"按钮验证 API Key 是否有效
- 实时测试，无需保存即可验证
- 明确的成功/失败提示

#### ✅ 环境变量检测
- 自动检测是否配置了环境变量 `FIREBASE_API_KEY`
- 显示环境变量的值
- 提示优先级（环境变量 > 数据库配置）

#### ✅ 获取指南
- 内置详细的获取步骤说明
- 链接到 Windsurf 官网
- 格式示例和说明

## 使用方法

### 步骤 1：获取 Firebase API Key

**方法 A：浏览器开发者工具（推荐）**

1. 访问 https://windsurf.com
2. 按 `F12` 打开开发者工具
3. 切换到 **Network**（网络）标签
4. 刷新页面（`F5`）
5. 在过滤框中搜索 `firebase` 或 `identitytoolkit`
6. 找到类似这样的请求：
   ```
   https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSy...
   ```
7. 复制 `key=` 后面的值

**格式**：`AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`（39个字符）

### 步骤 2：在后台配置

1. 登录管理后台
2. 进入 **系统设置** 页面
3. 找到 **Firebase API Key 配置** 卡片
4. 在输入框中粘贴获取到的 API Key
5. 点击 **测试连接** 验证是否有效
6. 点击 **保存设置** 保存配置

### 步骤 3：验证配置

测试账号获取功能：

```bash
curl -X POST "http://localhost:8010/api/client/account/get" \
  -H "X-API-Key: your_key_code"
```

应该能正常返回账号信息，不再报 Firebase API Key 相关错误。

## 配置优先级

系统按以下优先级读取 Firebase API Key：

```
1. 环境变量 FIREBASE_API_KEY（最高优先级）
   ↓
2. 数据库配置（通过后台设置）
   ↓
3. 自动获取（从 Windsurf 网站）
   ↓
4. 后备 API Key（代码中硬编码）
```

### 说明

- **环境变量优先**：如果设置了环境变量，数据库配置将被忽略
- **数据库配置**：通过后台设置的值，无需重启服务即可生效
- **自动获取**：如果前两者都没有，尝试自动从网站获取
- **后备方案**：如果都失败，使用代码中的后备 Key

## API 接口

### 1. 获取 Firebase 配置

```http
GET /admin/api/settings/firebase
```

**响应示例**：
```json
{
  "success": true,
  "firebase_api_key": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "env_firebase_api_key": "",
  "using_env": false,
  "message": "使用数据库配置"
}
```

### 2. 保存 Firebase 配置

```http
POST /admin/api/settings/firebase
Content-Type: multipart/form-data

firebase_api_key=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**响应示例**：
```json
{
  "success": true,
  "message": "Firebase API Key 已更新",
  "warning": ""
}
```

### 3. 测试 Firebase API Key

```http
POST /admin/api/settings/firebase/test
Content-Type: multipart/form-data

firebase_api_key=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**响应示例**：
```json
{
  "success": true,
  "valid": true,
  "message": "Firebase API Key 有效"
}
```

## 技术实现

### 后端实现

**文件**：`app/routers/admin.py`

新增了三个 API 接口：
- `GET /admin/api/settings/firebase` - 获取配置
- `POST /admin/api/settings/firebase` - 保存配置
- `POST /admin/api/settings/firebase/test` - 测试 API Key

**文件**：`app/windsurf_login.py`

修改了 `WindsurfLoginService` 类：
- 添加 `db` 参数，支持从数据库读取配置
- 优先级：传入参数 > 环境变量 > 数据库配置

**文件**：`app/routers/client.py`

更新了调用 `windsurf_login` 的地方，传入数据库会话。

### 前端实现

**文件**：`app/templates/settings.html`

新增了 Firebase API Key 配置卡片：
- 输入框（支持密码显示/隐藏）
- 测试连接按钮
- 保存设置按钮
- 环境变量检测提示
- 获取指南和使用说明

## 常见问题

### Q1: 为什么配置了数据库但还是用环境变量的值？

**A**: 环境变量的优先级更高。如果设置了 `FIREBASE_API_KEY` 环境变量，系统会优先使用环境变量的值。

**解决方法**：
- 删除或注释掉 `.env` 文件中的 `FIREBASE_API_KEY`
- 重启服务使环境变量失效

### Q2: 修改配置后需要重启服务吗？

**A**: 不需要。数据库配置会在每次登录时动态读取，修改后立即生效。

但如果使用环境变量配置，修改后需要重启服务。

### Q3: 测试连接显示"无效"怎么办？

**A**: 可能的原因：
1. API Key 格式不正确（检查是否完整复制）
2. API Key 已过期（重新从 Windsurf 网站获取）
3. 网络问题（检查服务器网络连接）

### Q4: 如何知道当前使用的是哪个配置？

**A**: 在系统设置页面查看：
- 如果显示"环境变量配置优先"警告，说明使用环境变量
- 否则使用数据库配置

也可以查看日志：
```bash
docker-compose logs -f app | grep Firebase
```

### Q5: 可以同时配置多个 Firebase API Key 吗？

**A**: 目前不支持。系统只使用一个 Firebase API Key。

如果需要切换，直接在后台修改配置即可。

## 安全说明

### Firebase API Key 是公开的吗？

是的，Firebase API Key 是设计为公开的：
- 可以在客户端代码中看到
- 可以在浏览器开发者工具中看到
- 不需要保密
- 安全性由 Firebase 的安全规则保护

### 数据库存储安全吗？

- Firebase API Key 以明文存储在数据库中
- 这是安全的，因为 API Key 本身就是公开的
- 真正的安全性由 Firebase 的认证和授权机制保证

### 管理后台访问控制

- 只有登录的管理员才能访问系统设置
- 使用 Session 认证
- 建议设置强密码

## 更新日志

### v1.2.0 (2024-12-09)

**新增功能**：
- ✅ 后台可视化配置 Firebase API Key
- ✅ 测试连接功能
- ✅ 环境变量检测和提示
- ✅ 内置获取指南

**技术改进**：
- ✅ 支持从数据库读取配置
- ✅ 配置优先级机制
- ✅ 自动格式验证
- ✅ 实时生效，无需重启

## 相关文档

- [Firebase API Key 修复](FIREBASE_API_KEY_FIX.md) - 技术细节
- [获取 Firebase Key 指南](GET_FIREBASE_KEY.md) - 详细获取方法
- [紧急更新指南](URGENT_FIREBASE_KEY_UPDATE.md) - 快速解决方案

## 总结

通过后台配置功能，管理员可以：
1. 可视化配置 Firebase API Key
2. 实时测试验证
3. 无需重启服务
4. 无需修改代码或环境变量

大大简化了 Firebase API Key 的管理和维护工作。

---

**功能版本**: v1.2.0  
**更新日期**: 2024-12-09  
**状态**: ✅ 已完成
