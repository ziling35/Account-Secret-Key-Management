@echo off
chcp 65001 >nul
echo ============================================================
echo Docker 测试部署脚本
echo ============================================================
echo.

echo [1/4] 停止并删除旧容器...
docker-compose -f docker-compose.test.yml down
echo.

echo [2/4] 构建 Docker 镜像...
docker-compose -f docker-compose.test.yml build
if %errorlevel% neq 0 (
    echo ❌ 构建失败！
    pause
    exit /b 1
)
echo.

echo [3/4] 启动容器...
docker-compose -f docker-compose.test.yml up -d
if %errorlevel% neq 0 (
    echo ❌ 启动失败！
    pause
    exit /b 1
)
echo.

echo [4/4] 等待服务启动...
timeout /t 5 /nobreak >nul
echo.

echo ============================================================
echo ✅ 部署完成！
echo ============================================================
echo.
echo 服务地址: http://localhost:8000
echo 管理后台: http://localhost:8000/admin
echo 用户名: admin
echo 密码: admin123
echo.
echo 测试公告接口:
echo curl http://localhost:8000/api/client/announcement
echo.
echo 查看日志:
echo docker-compose -f docker-compose.test.yml logs -f
echo.
echo 停止服务:
echo docker-compose -f docker-compose.test.yml down
echo.
pause
