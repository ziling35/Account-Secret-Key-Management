# 公告功能使用文档

## 功能说明

为系统添加了公告功能，管理员可以在后台发布公告，客户端启动时自动获取并显示。

## 数据库迁移

### 1. 运行迁移脚本

```bash
python migrate_announcement.py
```

这将在数据库中创建 `announcements` 表并添加示例公告。

### 2. 表结构

```sql
CREATE TABLE announcements (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,              -- 公告内容
    is_active BOOLEAN DEFAULT FALSE,    -- 是否启用
    priority INTEGER DEFAULT 0,         -- 优先级
    created_at TIMESTAMP,               -- 创建时间
    updated_at TIMESTAMP,               -- 更新时间
    created_by TEXT,                    -- 创建人
    updated_by TEXT                     -- 更新人
);
```

## API 接口

### 客户端接口（公开）

#### 获取公告
```http
GET /api/client/announcement
```

**响应示例**:
```json
{
  "content": "欢迎使用 PaperCrane-Windsurf！\n\n最新更新：\n- 新增公告功能",
  "created_at": "2025-12-08T00:00:00",
  "updated_at": "2025-12-08T12:00:00"
}
```

### 管理端接口（需要登录）

#### 1. 获取公告列表
```http
GET /admin/api/announcements/list
```

#### 2. 创建公告
```http
POST /admin/api/announcements/create
Content-Type: application/x-www-form-urlencoded

content=公告内容&is_active=true
```

#### 3. 更新公告
```http
POST /admin/api/announcements/{id}/update
Content-Type: application/x-www-form-urlencoded

content=更新后的内容&is_active=true
```

#### 4. 删除公告
```http
POST /admin/api/announcements/{id}/delete
```

#### 5. 切换启用状态
```http
POST /admin/api/announcements/{id}/toggle
```

## 管理后台使用

### 方法1: 使用 API 测试工具

可以使用 Postman、curl 等工具调用管理接口。

**示例 - 创建公告**:
```bash
curl -X POST http://localhost:8000/admin/api/announcements/create \
  -H "Cookie: admin_session=YOUR_SESSION_TOKEN" \
  -F "content=这是一条测试公告" \
  -F "is_active=true"
```

### 方法2: 添加管理页面

建议在管理后台添加公告管理页面，位置：`app/templates/announcements.html`

**页面功能**:
- 公告列表展示
- 创建/编辑公告
- 启用/禁用公告
- 删除公告

**路由添加** (在 `app/routers/admin.py` 中):
```python
@router.get("/announcements", response_class=HTMLResponse)
async def announcements_page(request: Request, username: str = Depends(verify_admin)):
    """公告管理页面"""
    return templates.TemplateResponse("announcements.html", {"request": request})
```

## 业务逻辑

### 1. 唯一启用规则
- 同时只能有一条公告处于启用状态
- 启用新公告时，自动禁用其他公告
- 确保客户端始终获取到最新的公告

### 2. 错误处理
- 客户端接口即使出错也返回空内容，不影响客户端使用
- 管理端接口返回详细错误信息

### 3. 权限控制
- 客户端接口：公开，无需认证
- 管理端接口：需要管理员登录

## 测试步骤

### 1. 运行迁移
```bash
python migrate_announcement.py
```

### 2. 启动服务
```bash
python run_local.py
```

### 3. 测试客户端接口
```bash
curl http://localhost:8000/api/client/announcement
```

应该返回示例公告内容。

### 4. 测试管理接口

先登录获取 session:
```bash
curl -X POST http://localhost:8000/admin/login \
  -F "username=admin" \
  -F "password=your_password" \
  -c cookies.txt
```

然后获取公告列表:
```bash
curl http://localhost:8000/admin/api/announcements/list \
  -b cookies.txt
```

### 5. 测试客户端显示

启动客户端，应该在主页顶部看到公告卡片。

## 常见问题

### Q: 迁移脚本报错？
A: 确保已安装所有依赖，并且数据库文件可访问。

### Q: 客户端不显示公告？
A: 检查：
1. 后端服务是否正常运行
2. 公告是否已启用 (`is_active=true`)
3. 浏览器控制台是否有错误

### Q: 如何修改公告内容？
A: 使用管理接口或直接修改数据库:
```sql
UPDATE announcements 
SET content = '新的公告内容', updated_at = CURRENT_TIMESTAMP 
WHERE is_active = 1;
```

### Q: 如何禁用公告？
A: 调用切换接口或直接修改数据库:
```sql
UPDATE announcements SET is_active = 0 WHERE id = 1;
```

## 文件清单

### 后端修改
- ✅ `app/models.py` - 添加 Announcement 模型
- ✅ `app/schemas.py` - 添加公告相关 Schema
- ✅ `app/routers/client.py` - 添加客户端公告接口
- ✅ `app/routers/admin.py` - 添加管理端公告接口
- ✅ `migrate_announcement.py` - 数据库迁移脚本

### 客户端修改（已完成）
- ✅ `modules/keyManager.js` - 添加获取公告方法
- ✅ `renderer/index.html` - 添加公告显示区域
- ✅ `renderer/style.css` - 添加公告样式
- ✅ `renderer/renderer.js` - 添加公告逻辑
- ✅ `preload.js` - 添加 IPC 接口
- ✅ `main.js` - 添加 IPC 处理器

## 下一步优化

1. **添加管理页面**: 创建 `announcements.html` 模板
2. **富文本编辑**: 支持 Markdown 格式
3. **定时发布**: 支持设置生效时间和过期时间
4. **多语言**: 根据客户端语言返回不同公告
5. **统计**: 记录公告查看次数

## 版本信息

- 添加日期: 2025-12-08
- 后端版本: 需要运行迁移脚本
- 客户端版本: 1.0.1+
