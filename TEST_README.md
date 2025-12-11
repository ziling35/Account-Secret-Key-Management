# 🚀 公告功能测试指南

## 📦 已创建的测试文件

### Docker 配置
- ✅ `Dockerfile.test` - 测试环境 Dockerfile（使用 SQLite）
- ✅ `docker-compose.test.yml` - Docker Compose 测试配置

### 测试脚本
- ✅ `quick_test.bat` - **一键测试脚本（推荐）**
- ✅ `test_docker.bat` - Docker 部署脚本
- ✅ `test_announcement.bat` - 公告功能测试脚本

### 文档
- ✅ `DOCKER_TEST_GUIDE.md` - 详细测试指南
- ✅ `ANNOUNCEMENT_FEATURE.md` - 公告功能文档

## ⚡ 快速开始

### 最简单的方式（推荐）

```bash
# 双击运行或在命令行执行
quick_test.bat
```

这个脚本会自动：
1. ✅ 检查 Docker 状态
2. ✅ 清理旧环境
3. ✅ 构建镜像
4. ✅ 启动服务
5. ✅ 等待服务就绪
6. ✅ 测试公告接口
7. ✅ 显示测试结果

### 分步执行

```bash
# 1. 部署服务
test_docker.bat

# 2. 测试功能
test_announcement.bat
```

## 🧪 测试内容

### 自动测试项
- ✅ 服务启动检查
- ✅ 公告接口响应
- ✅ 管理后台登录
- ✅ 公告列表获取
- ✅ 创建新公告
- ✅ 更新公告
- ✅ 切换公告状态

### 手动测试项
- ⬜ 浏览器访问管理后台
- ⬜ 客户端显示公告
- ⬜ 公告内容格式化
- ⬜ 关闭公告功能

## 📋 测试环境信息

### 服务配置
- **服务地址**: http://localhost:8000
- **管理后台**: http://localhost:8000/admin/login
- **API 文档**: http://localhost:8000/docs
- **数据库**: SQLite (test.db)

### 管理员账号
- **用户名**: admin
- **密码**: admin123

### 容器信息
- **容器名**: windsurf-test
- **镜像**: account-secret-key-management-app
- **端口映射**: 8000:8000

## 🔍 验证步骤

### 1. 验证服务启动
```bash
curl http://localhost:8000/api/client/announcement
```

预期输出：
```json
{
  "content": "欢迎使用 PaperCrane-Windsurf！...",
  "created_at": "2025-12-08T...",
  "updated_at": "2025-12-08T..."
}
```

### 2. 验证管理后台
1. 浏览器打开: http://localhost:8000/admin/login
2. 输入用户名: `admin`
3. 输入密码: `admin123`
4. 点击登录

### 3. 验证客户端显示
1. 启动 Windsurf 客户端
2. 在主页顶部应该看到紫色渐变的公告卡片
3. 公告内容应该显示正确
4. 可以点击关闭按钮

## 🛠️ 常用命令

### 查看日志
```bash
# 实时日志
docker-compose -f docker-compose.test.yml logs -f

# 最近 50 行
docker-compose -f docker-compose.test.yml logs --tail=50
```

### 进入容器
```bash
docker exec -it windsurf-test bash
```

### 重启服务
```bash
docker-compose -f docker-compose.test.yml restart
```

### 停止服务
```bash
docker-compose -f docker-compose.test.yml down
```

### 完全清理
```bash
docker-compose -f docker-compose.test.yml down -v
docker rmi account-secret-key-management-app
```

## 🐛 故障排查

### 问题 1: Docker 未运行
**症状**: `error during connect: This error may indicate that the docker daemon is not running`

**解决**:
1. 启动 Docker Desktop
2. 等待 Docker 完全启动
3. 重新运行测试脚本

### 问题 2: 端口被占用
**症状**: `bind: address already in use`

**解决**:
```bash
# 查找占用进程
netstat -ano | findstr :8000

# 结束进程（替换 PID）
taskkill /F /PID <PID>

# 或修改端口
# 编辑 docker-compose.test.yml
# 将 "8000:8000" 改为 "8001:8000"
```

### 问题 3: 构建失败
**症状**: `ERROR: failed to solve`

**解决**:
```bash
# 清理 Docker 缓存
docker system prune -a

# 重新构建
docker-compose -f docker-compose.test.yml build --no-cache
```

### 问题 4: 公告接口返回空
**症状**: `{"content": ""}`

**解决**:
```bash
# 进入容器
docker exec -it windsurf-test bash

# 手动运行迁移
python migrate_announcement.py

# 检查数据库
python -c "
from app.database import SessionLocal
from app.models import Announcement
db = SessionLocal()
print('公告数量:', db.query(Announcement).count())
announcement = db.query(Announcement).first()
if announcement:
    print('公告状态:', announcement.is_active)
    print('公告内容:', announcement.content[:50])
db.close()
"

exit
```

## 📊 性能测试

### 基准测试
```bash
# 使用 Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/client/announcement

# 或使用 curl 循环
for /L %i in (1,1,100) do @curl -s http://localhost:8000/api/client/announcement >nul && echo Request %i OK
```

### 预期性能
- **响应时间**: < 100ms
- **并发能力**: 100+ req/s
- **错误率**: 0%

## ✅ 测试检查清单

### 基础功能
- [ ] Docker 环境正常
- [ ] 服务成功启动
- [ ] 公告接口可访问
- [ ] 返回正确的 JSON 格式
- [ ] 公告内容完整

### 管理功能
- [ ] 管理后台可登录
- [ ] 可以查看公告列表
- [ ] 可以创建新公告
- [ ] 可以更新公告
- [ ] 可以删除公告
- [ ] 可以切换启用状态

### 客户端集成
- [ ] 客户端可以获取公告
- [ ] 公告显示样式正确
- [ ] 支持多行文本
- [ ] 可以关闭公告
- [ ] 错误处理正常

### 边界测试
- [ ] 没有公告时返回空内容
- [ ] 多条公告只显示启用的
- [ ] 长文本正确显示
- [ ] 特殊字符处理正确

## 📝 测试报告

测试完成后，请填写：

```
测试日期: ___________
测试人员: ___________
环境: Docker (SQLite)

测试结果:
✅ / ❌ 服务启动
✅ / ❌ 公告接口
✅ / ❌ 管理后台
✅ / ❌ 客户端显示

性能指标:
- 响应时间: _____ ms
- 并发能力: _____ req/s
- 错误率: _____ %

问题记录:
___________________________
___________________________

总体评价:
✅ 测试通过 / ❌ 测试失败

备注:
___________________________
```

## 🎯 下一步

测试通过后：
1. ✅ 将代码提交到 Git
2. ✅ 部署到生产环境（使用 PostgreSQL）
3. ✅ 运行生产环境迁移: `python migrate_announcement.py`
4. ✅ 在管理后台创建正式公告
5. ✅ 通知用户更新客户端

## 📞 支持

如有问题，请查看：
- 详细指南: `DOCKER_TEST_GUIDE.md`
- 功能文档: `ANNOUNCEMENT_FEATURE.md`
- API 文档: http://localhost:8000/docs
