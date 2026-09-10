# app/main.py
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

# 允许在 .env 里放密钥型配置（DASHSCOPE_API_KEY / OCR_BACKEND / SECRET_KEY 等）
from dotenv import load_dotenv

load_dotenv()

# 引入路由模块
from app.api.routes import router
from app.api.auth_routes import router as auth_router
# Stage 5：JSONL 访问日志中间件（可观测性）
from app.core.middleware import AccessLogMiddleware
# Stage 6：存储层，启动时建表
from app.core import db

# 启动即建表（幂等）
db.init_db()

# 1) 创建应用实例
app = FastAPI(
    title="Expense App",
    version="0.2.0",
    description="AI 记账分账服务：分账引擎 + 债务最小化结算 + 收据 OCR/VLM 解析 + 多用户鉴权看板",
)

# 2) 挂路由（业务 + 鉴权）
app.include_router(router)
app.include_router(auth_router)

# 3) 挂上访问日志中间件（对所有请求生效，业务代码无感）
app.add_middleware(AccessLogMiddleware)

# 4) 前端看板（Stage 6）：根路径返回单页应用
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# 5) 健康检查
@app.get("/health")
def health_check():
    return {"status": "ok"}
