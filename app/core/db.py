"""
Stage 6 — 多用户存储层（标准库实现，零额外依赖）
================================================
用 sqlite3 做持久化，保存：用户、收据、分账记录。
这样每个登录用户只能看到自己的数据，做到「多用户隔离」。

设计取舍（面试能讲）：
  - 没引入 SQLAlchemy / Postgres —— 演示项目用 stdlib sqlite3 足够，
    且把「技术选型克制、不为 demo 上重依赖」这一点讲出来是加分项。
  - DB 路径由环境变量 EXPENSE_DB 控制，测试时可指向临时文件，互不污染。
"""
import json
import os
import sqlite3
import time

# 默认落在项目 data/app.db；测试用环境变量覆盖为临时库
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app.db")
DB_PATH = os.getenv("EXPENSE_DB", _DEFAULT_DB)


def _conn() -> sqlite3.Connection:
    """打开一个连接。check_same_thread=False 让它在 Starlette 的多线程请求里可用。"""
    parent = os.path.dirname(DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 让查询结果可以按列名取
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建表（幂等）。应用启动时调用一次即可。"""
    conn = _conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT UNIQUE NOT NULL,
                pw_hash    TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                filename   TEXT,
                total      REAL,
                paid_by    TEXT,
                items_json TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS splits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                receipt_id  INTEGER,
                method      TEXT,
                shares_json TEXT,
                created_at  REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 用户
# ---------------------------------------------------------------------------
def create_user(username: str, pw_hash: str) -> int:
    """插入一个新用户，返回其自增主键（`int`）。

    调用方需要知道的三条契约：
      1. `users.username` 带 `UNIQUE` 约束 ⇒ 用户名重复时**抛**
         `sqlite3.IntegrityError`（"UNIQUE constraint failed: users.username"），
         而不是返回 None / -1 之类的哨兵值。调用方必须自己 try/except。
      2. `app/api/auth_routes.py` 的注册流程是「先 `get_user_by_username` 查重、
         再 `create_user` 插入」的两步写法 —— 这是 TOCTOU：两个并发请求带同一
         用户名时，两者都可能查到「不存在」并通过检查，随后第二个插入撞上
         UNIQUE 约束抛异常，且该异常在路由层未被捕获 ⇒ 500 而不是 409。
         要做成并发安全，需在此捕获 IntegrityError 后转成业务错误。
      3. `_conn()` 每条连接都执行 `PRAGMA foreign_keys = ON`，但本函数只写
         users 表，不受外键约束影响。
    """
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO users(username, pw_hash, created_at) VALUES(?,?,?)",
            (username, pw_hash, time.time()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_by_username(username: str):
    """按用户名查用户。命中返回 `dict`（不是 `sqlite3.Row`），未命中返回 `None`。

    注意 `_conn()` 设了 `row_factory = sqlite3.Row`，但本函数用 `dict(row)`
    转换后再返回 —— 调用方可以直接 `.get()` / 下标取值，也可以安全地
    `if not user:` 判空，两种写法都成立。
    """
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(uid: int):
    """按主键查用户。语义与 `get_user_by_username` 一致：命中 `dict`、未命中 `None`。

    调用方（`app/core/auth.py` 的鉴权依赖）用 `None` 表示「token 里的 uid
    在库中已不存在」（例如库被重建），从而判为未授权。
    """
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 收据 & 分账记录
# ---------------------------------------------------------------------------
def save_receipt(user_id: int, filename, total, paid_by, items_json) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO receipts(user_id, filename, total, paid_by, items_json, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (user_id, filename, total, paid_by, items_json, time.time()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_split(user_id: int, receipt_id, method: str, shares_json: str) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO splits(user_id, receipt_id, method, shares_json, created_at) "
            "VALUES(?,?,?,?,?)",
            (user_id, receipt_id, method, shares_json, time.time()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_history(user_id: int):
    """返回该用户的收据 + 对应分账，按**收据**创建时间倒序。

    调用方需要知道的四条契约：
      1. 以 receipts 为左表 LEFT JOIN splits ⇒ 没有分账的收据照样返回，
         `split_id` / `method` / `shares` 均为 None；同一张收据若挂多条分账，
         则每条分账各占一行（收据字段重复），不是合并成一行。
      2. `receipt_id` 为 NULL 的分账永远查不到 —— 连接条件是
         `s.receipt_id = r.id`，NULL 匹配不上任何 r.id。`POST /split` 正是
         这样落库的（app/api/routes.py 传 receipt_id=None），所以只有
         `POST /confirm` 产生的收据-分账组合可在此追溯。
      3. 硬编码 `LIMIT 50`，没有分页参数 ⇒ 第 51 条起被**静默丢弃**，
         调用方无法从返回结果区分「只有 50 条」和「被截断了」。
      4. `shares_json` 为空串或 NULL 时 `shares` 收敛为 None，
         不会抛 JSONDecodeError。
    """
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT r.id, r.filename, r.total, r.paid_by, r.created_at, "
            "       s.method, s.shares_json, s.id AS split_id "
            "FROM receipts r "
            "LEFT JOIN splits s ON s.receipt_id = r.id "
            "WHERE r.user_id = ? "
            "ORDER BY r.created_at DESC LIMIT 50",
            (user_id,),
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["shares"] = json.loads(d.pop("shares_json")) if d["shares_json"] else None
            out.append(d)
        return out
    finally:
        conn.close()
