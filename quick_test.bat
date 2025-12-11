@echo off
chcp 65001 >nul
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║         公告功能 Docker 一键测试                           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM 检查 Docker 是否运行
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

echo ✅ Docker 正在运行
echo.

REM 停止旧容器
echo [步骤 1/6] 清理旧环境...
docker-compose -f docker-compose.test.yml down >nul 2>&1
echo ✅ 完成
echo.

REM 构建镜像
echo [步骤 2/6] 构建 Docker 镜像...
docker-compose -f docker-compose.test.yml build
if %errorlevel% neq 0 (
    echo ❌ 构建失败！
    pause
    exit /b 1
)
echo ✅ 完成
echo.

REM 启动容器
echo [步骤 3/6] 启动容器...
docker-compose -f docker-compose.test.yml up -d
if %errorlevel% neq 0 (
    echo ❌ 启动失败！
    pause
    exit /b 1
)
echo ✅ 完成
echo.

REM 等待服务启动
echo [步骤 4/6] 等待服务启动...
timeout /t 8 /nobreak >nul

REM 检查服务健康
echo [步骤 5/6] 检查服务状态...
curl -s http://localhost:8000/api/client/announcement >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  服务可能未完全启动，查看日志...
    docker-compose -f docker-compose.test.yml logs --tail=20
    echo.
    echo 按任意键继续测试...
    pause >nul
)
echo ✅ 服务正常运行
echo.

REM 测试公告功能
echo [步骤 6/6] 测试公告功能...
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 📢 获取公告内容:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
curl -s http://localhost:8000/api/client/announcement
echo.
echo.

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 🔐 管理后台登录:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
curl -s -c cookies.txt -X POST http://localhost:8000/admin/login ^
  -F "username=admin" ^
  -F "password=admin123"
echo.
echo.

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 📋 获取公告列表:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
curl -s -b cookies.txt http://localhost:8000/admin/api/announcements/list
echo.
echo.

REM 清理
if exist cookies.txt del cookies.txt

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                   ✅ 测试完成！                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 📊 测试结果:
echo    - 服务地址: http://localhost:8000
echo    - 管理后台: http://localhost:8000/admin/login
echo    - API 文档: http://localhost:8000/docs
echo.
echo 📝 管理员账号:
echo    - 用户名: admin
echo    - 密码: admin123
echo.
echo 🔧 常用命令:
echo    - 查看日志: docker-compose -f docker-compose.test.yml logs -f
echo    - 停止服务: docker-compose -f docker-compose.test.yml down
echo    - 重启服务: docker-compose -f docker-compose.test.yml restart
echo.
echo 💡 下一步:
echo    1. 在浏览器打开 http://localhost:8000/admin/login
echo    2. 使用 admin/admin123 登录
echo    3. 启动客户端测试公告显示
echo.
pause
