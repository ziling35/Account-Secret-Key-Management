# Docker 本地测试指南

## 📋 前置要求

- ✅ 已安装 Docker Desktop
- ✅ Docker 服务正在运行

## 🚀 快速开始

### 方法 1: 使用测试脚本（推荐）

#### Windows 用户
```bash
# 1. 启动测试环境
test_docker.bat

# 2. 测试公告功能
test_announcement.bat
```

### 方法 2: 手动命令

```bash
# 1. 构建并启动
docker-compose -f docker-compose.test.yml up -d --build

# 2. 查看日志
docker-compose -f docker-compose.test.yml logs -f

# 3. 停止服务
docker-compose -f docker-compose.test.yml down
```

## 🧪 测试步骤

### 1. 启动服务

```bash
cd d:\zmoney\Account-Secret-Key-Management
test_docker.bat
```

等待输出：
```
✅ 部署完成！
服务地址: http://localhost:8000
管理后台: http://localhost:8000/admin
```

### 2. 测试公告接口

#### 方式 A: 使用测试脚本
```bash
test_announcement.bat
```

#### 方式 B: 手动测试

**测试客户端接口**:
```bash
curl http://localhost:8000/api/client/announcement
```

预期响应：
```json
{
  "content": "欢迎使用 PaperCrane-Windsurf！\n\n最新更新：\n- 新增公告功能\n- 优化账号切换速度\n- 修复已知问题\n\n如有问题请联系管理员。",
  "created_at": "2025-12-08T...",
  "updated_at": "2025-12-08T..."
}
```

**测试管理接口**:
```bash
# 1. 登录
curl -c cookies.txt -X POST http://localhost:8000/admin/login \
  -F "username=admin" \
  -F "password=admin123"

# 2. 获取公告列表
curl -b cookies.txt http://localhost:8000/admin/api/announcements/list

# 3. 创建新公告
curl -b cookies.txt -X POST http://localhost:8000/admin/api/announcements/create \
  -F "content=测试公告内容" \
  -F "is_active=true"

# 4. 切换公告状态
curl -b cookies.txt -X POST http://localhost:8000/admin/api/announcements/1/toggle
```

### 3. 测试客户端显示

启动 Windsurf 客户端，应该在主页顶部看到公告卡片。

### 4. 查看日志

```bash
# 实时查看日志
docker-compose -f docker-compose.test.yml logs -f

# 只看最近 50 行
docker-compose -f docker-compose.test.yml logs --tail=50
```

## 🔍 验证清单

- [ ] 服务启动成功（http://localhost:8000）
- [ ] 公告接口返回正确内容
- [ ] 管理后台可以登录
- [ ] 可以创建新公告
- [ ] 可以更新公告
- [ ] 可以切换公告状态
- [ ] 客户端正确显示公告

## 🛠️ 常见问题

### Q1: 端口被占用
```
Error: bind: address already in use
```

**解决方案**:
```bash
# 查看占用 8000 端口的进程
netstat -ano | findstr :8000

# 停止占用的进程或修改端口
# 编辑 docker-compose.test.yml，将 8000:8000 改为 8001:8000
```

### Q2: Docker 构建失败
```
ERROR: failed to solve
```

**解决方案**:
```bash
# 清理 Docker 缓存
docker system prune -a

# 重新构建
docker-compose -f docker-compose.test.yml build --no-cache
```

### Q3: 数据库迁移失败
```
❌ announcements 表创建失败
```

**解决方案**:
```bash
# 进入容器手动迁移
docker exec -it windsurf-test bash
python migrate_announcement.py
exit
```

### Q4: 无法访问服务
```
curl: (7) Failed to connect to localhost port 8000
```

**解决方案**:
```bash
# 检查容器状态
docker ps

# 查看容器日志
docker logs windsurf-test

# 重启容器
docker-compose -f docker-compose.test.yml restart
```

### Q5: 公告接口返回空内容
```json
{"content": ""}
```

**可能原因**:
1. 数据库迁移未执行
2. 没有启用的公告

**解决方案**:
```bash
# 进入容器
docker exec -it windsurf-test bash

# 检查数据库
python -c "
from app.database import SessionLocal
from app.models import Announcement
db = SessionLocal()
announcements = db.query(Announcement).all()
for a in announcements:
    print(f'ID: {a.id}, Active: {a.is_active}, Content: {a.content[:50]}...')
db.close()
"

# 手动启用公告
python -c "
from app.database import SessionLocal
from app.models import Announcement
db = SessionLocal()
announcement = db.query(Announcement).first()
if announcement:
    announcement.is_active = True
    db.commit()
    print('✅ 公告已启用')
db.close()
"

exit
```

## 📊 性能测试

### 压力测试
```bash
# 使用 Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/client/announcement

# 或使用 curl 循环
for /L %i in (1,1,100) do @curl -s http://localhost:8000/api/client/announcement >nul && echo Request %i OK
```

## 🧹 清理环境

### 停止服务
```bash
docker-compose -f docker-compose.test.yml down
```

### 完全清理（包括数据）
```bash
# 停止并删除容器、网络、卷
docker-compose -f docker-compose.test.yml down -v

# 删除镜像
docker rmi account-secret-key-management-app

# 删除测试数据目录
rmdir /s /q test_data
```

## 📝 测试报告模板

```
测试日期: 2025-12-08
测试人员: [您的名字]
环境: Docker (SQLite)

功能测试:
✅ 服务启动
✅ 公告接口
✅ 管理登录
✅ 创建公告
✅ 更新公告
✅ 删除公告
✅ 切换状态
✅ 客户端显示

性能测试:
- 响应时间: < 100ms
- 并发请求: 100/s
- 错误率: 0%

问题记录:
[如有问题请记录]

结论:
✅ 测试通过 / ❌ 测试失败
```

## 🔗 相关链接

- API 文档: http://localhost:8000/docs
- 管理后台: http://localhost:8000/admin
- 公告功能文档: ANNOUNCEMENT_FEATURE.md

## 📞 技术支持

如有问题，请查看：
1. Docker 日志: `docker logs windsurf-test`
2. 应用日志: `docker exec windsurf-test cat /app/logs/app.log`
3. 数据库状态: `docker exec windsurf-test python -c "from app.database import engine; print(engine.table_names())"`
