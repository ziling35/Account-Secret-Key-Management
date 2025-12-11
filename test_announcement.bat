@echo off
chcp 65001 >nul
echo ============================================================
echo 公告功能测试脚本
echo ============================================================
echo.

set BASE_URL=http://localhost:8000

echo [测试 1] 检查服务是否运行...
curl -s %BASE_URL%/api/client/announcement >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 服务未运行或无法访问
    echo 请先运行: test_docker.bat
    pause
    exit /b 1
)
echo ✅ 服务正常运行
echo.

echo [测试 2] 获取公告内容...
echo.
curl -s %BASE_URL%/api/client/announcement
echo.
echo.

echo [测试 3] 登录管理后台...
curl -s -c cookies.txt -X POST %BASE_URL%/admin/login ^
  -F "username=admin" ^
  -F "password=admin123" >nul
if %errorlevel% neq 0 (
    echo ❌ 登录失败
    pause
    exit /b 1
)
echo ✅ 登录成功
echo.

echo [测试 4] 获取公告列表...
echo.
curl -s -b cookies.txt %BASE_URL%/admin/api/announcements/list
echo.
echo.

echo [测试 5] 创建新公告...
curl -s -b cookies.txt -X POST %BASE_URL%/admin/api/announcements/create ^
  -F "content=这是一条测试公告，创建于 %date% %time%" ^
  -F "is_active=false"
echo.
echo.

echo [测试 6] 再次获取公告列表...
echo.
curl -s -b cookies.txt %BASE_URL%/admin/api/announcements/list
echo.
echo.

echo ============================================================
echo ✅ 测试完成！
echo ============================================================
echo.
echo 清理 cookies 文件...
if exist cookies.txt del cookies.txt
echo.
pause
