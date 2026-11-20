"""Octop LDAP Router HTTP application. Routing only; it is not an authenticator."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .repository import (
    InvalidAssignment,
    PostgresRouterRepository,
    RepositoryConfigurationError,
    RepositoryUnavailable,
    RouteNotFound,
    resolve_target,
)

BASE_DIR = Path(__file__).resolve().parent.parent
HTML_PATH = BASE_DIR / "router" / "index.html"
EXPECTED_HOST = os.getenv("OCTOP_EXTERNAL_HOST", "ai.superice.com").strip().lower()
ALLOWED_PORTS = {
    int(part.strip())
    for part in os.getenv(
        "OCTOP_ALLOWED_PORTS", "8091,8092,8093,8094,8095,8096,8097,8098,8099,8100"
    ).split(",")
    if part.strip()
}
EMPLOYEE_RE = re.compile(
    os.getenv("OCTOP_EMPLOYEE_NO_REGEX", r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
)
LOGGER = logging.getLogger("octop_router")

app = FastAPI(title="Octop LDAP Router", version="2.2.0", docs_url=None, redoc_url=None, openapi_url=None)


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str = Field(min_length=1, max_length=255)


def get_repository():
    injected = getattr(app.state, "repository", None)
    if injected is not None:
        return injected
    try:
        return PostgresRouterRepository()
    except RepositoryConfigurationError as exc:
        raise HTTPException(status_code=503, detail="入口数据库连接尚未配置") from exc


def validate_employee_no(value: str) -> str:
    # Case-normalize only. Do not trim, strip DOMAIN\\, remove UPN suffixes,
    # convert to integer, or remove leading zeroes.
    if value != value.strip() or not EMPLOYEE_RE.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail="请输入公司统一账号（员工工号），不要包含域前缀或首尾空格",
        )
    return value.lower()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(HTML_PATH, media_type="text/html")


@app.post("/api/resolve", include_in_schema=False)
def resolve(body: ResolveRequest, repository: Any = Depends(get_repository)):
    employee_no = validate_employee_no(body.employee_id)
    try:
        result = resolve_target(repository, employee_no, EXPECTED_HOST, ALLOWED_PORTS)
    except RouteNotFound as exc:
        raise HTTPException(status_code=404, detail="未找到已启用的 Octop 应用授权，请联系管理员") from exc
    except InvalidAssignment as exc:
        LOGGER.warning("invalid Octop route assignment: %s", str(exc))
        raise HTTPException(status_code=409, detail="业务中心分配或应用注册配置异常，请联系管理员") from exc
    except RepositoryConfigurationError as exc:
        LOGGER.error("router repository configuration error")
        raise HTTPException(status_code=503, detail="入口数据库连接尚未配置") from exc
    except RepositoryUnavailable as exc:
        LOGGER.error("router database unavailable: %s", str(exc))
        raise HTTPException(status_code=503, detail="员工目录或应用注册库暂不可用") from exc

    response = JSONResponse(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz", include_in_schema=False)
def healthz(repository: Any = Depends(get_repository)):
    try:
        checks = repository.health()
    except Exception:
        checks = {"repository": "error"}
    ok = bool(checks) and all(value == "ok" for value in checks.values())
    if not ok:
        raise HTTPException(status_code=503, detail={"status": "degraded", "checks": checks})
    return {"status": "ok", "version": "2.2.0", "checks": checks}
