# -*- coding: utf-8 -*-
"""FastAPI 应用入口。本地部署，数据不出网。"""
import sys
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api import (
    analytes_api,
    auth_api,
    competitions,
    decision,
    dashboard,
    datahub,
    imports,
    participants_api,
    samples,
    stats_api,
    surveys,
    tracking,
)
from .database import Base, engine
from . import models  # noqa: F401

# 启动时自动建表（幂等，仅创建缺失的表，兼容已有数据库）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="短道速滑运动员血液数据分析平台",
    version="1.1.0",
    description="本地部署的运动员训练监控与科研分析工作台（短道速滑定制版）",
)

# 本地/局域网访问，放开 CORS（前端 Next.js 默认 3000 端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 认证（保留接口，业务 API 已免登录，本地模式无需登录）
app.include_router(auth_api.router)

# 业务 API（本地模式，无需登录）
app.include_router(dashboard.router)
app.include_router(tracking.router)
app.include_router(stats_api.router)
app.include_router(samples.router)
app.include_router(participants_api.router)
app.include_router(analytes_api.router)
app.include_router(imports.router)
app.include_router(surveys.router)
app.include_router(datahub.router)
app.include_router(competitions.router)
app.include_router(decision.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "blood-analysis-backend"}


# 打包版：由后端托管 Next.js 静态导出页面（API 路由优先，其余回退到静态文件）
def _static_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend_out"
    return Path(__file__).resolve().parent.parent.parent / "frontend" / "out"


_static = _static_dir()


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    """静态前端兜底：优先 API（已注册），其余按 .html / index.html 规则回退。"""
    base = _static.resolve()
    candidate = (base / full_path).resolve()
    if not candidate.is_relative_to(base):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if candidate.is_file():
        return FileResponse(candidate)

    html = (base / (full_path + ".html")).resolve()
    if html.is_relative_to(base) and html.is_file():
        return FileResponse(html)

    index = (base / full_path / "index.html").resolve()
    if index.is_relative_to(base) and index.is_file():
        return FileResponse(index)

    not_found = base / "404.html"
    if not_found.is_file():
        return FileResponse(not_found, status_code=404)
    return JSONResponse({"detail": "Not Found"}, status_code=404)
