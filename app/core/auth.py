"""
Stage 6 — 鉴权核心（标准库实现，零额外依赖）
============================================
  - 密码哈希：hashlib.pbkdf2_hmac（带随机盐，10 万次迭代）
  - 令牌：base64(payload) + "." + HMAC-SHA256 签名（自签名 bearer token）
  - 依赖项：get_current_user，直接挂到路由上即可保护端点

为什么不用 jwt / passlib？
  演示项目里它们完全能省，用 stdlib 既减少依赖面，又能在面试中
  讲清「密码为何要加盐哈希、令牌为何要签名防篡改」这类底层原理。
"""
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# 密钥从 .env 的 SECRET_KEY 读取；没配就用一个明显的开发默认值（生产必须配）
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
TOKEN_TTL = 60 * 60 * 24 * 7  # 令牌有效期 7 天

# auto_error=False：拿不到令牌时我们自己返回 401，而不是让框架抛 403
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# 密码
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """返回 'salt_hex$hash_hex'，盐随每次调用随机生成。"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        # 用 compare_digest 防止计时攻击
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 令牌（自签名 bearer token）
# ---------------------------------------------------------------------------
def create_token(user_id: int) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + TOKEN_TTL}).encode()
    body = base64.urlsafe_b64encode(payload).decode()
    sig = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str) -> Optional[int]:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body))
        if int(payload["exp"]) < time.time():
            return None
        return int(payload["uid"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FastAPI 依赖项：挂到路由上即可要求登录
# ---------------------------------------------------------------------------
def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    uid = verify_token(creds.credentials)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 懒导入避免循环引用（auth 与 db 互相不直接 import）
    from app.core import db

    user = db.get_user_by_id(uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user
