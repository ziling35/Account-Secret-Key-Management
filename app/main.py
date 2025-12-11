from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import admin, client

# 创建FastAPI应用
app = FastAPI(
    title="Windsurf账号池管理系统",
    description="管理和分发Windsurf账号的后端系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（Electron应用）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 异常处理：未登录重定向到登录页
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401 and request.url.path.startswith("/admin") and not request.url.path.startswith("/admin/login"):
        return RedirectResponse(url="/admin/login")
    # 返回 JSON 响应而不是 raise，避免被当成未处理异常导致 500 错误
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# 注册路由
app.include_router(admin.router)
app.include_router(client.router)

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    init_db()
    print("✅ 数据库初始化完成")

# 根路径重定向到管理面板
@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/admin")

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
