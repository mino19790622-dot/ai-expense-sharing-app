"""
Stage 6 — 鉴权路由
====================
  POST /api/v1/auth/register  注册并返回令牌
  POST /api/v1/auth/login     登录并返回令牌
  GET  /api/v1/auth/me        返回当前登录用户（需令牌）
"""
import re

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core import db
from app.core.auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _validate(username: str, password: str) -> None:
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="用户名需为 3-20 位字母/数字/下划线")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")


@router.post("/register")
def register(req: AuthRequest):
    _validate(req.username, req.password)
    if db.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    uid = db.create_user(req.username, hash_password(req.password))
    return {"token": create_token(uid), "user": {"id": uid, "username": req.username}}


@router.post("/login")
def login(req: AuthRequest):
    user = db.get_user_by_username(req.username)
    # 用户名不存在或密码不对都返回 401，不暴露具体原因（防账号枚举）
    if not user or not verify_password(req.password, user["pw_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_token(user["id"]), "user": {"id": user["id"], "username": user["username"]}}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "username": user["username"]}
