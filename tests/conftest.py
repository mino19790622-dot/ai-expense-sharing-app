"""
Stage 6 测试公共配置
====================
  - 把存储指向临时库，避免污染真实 data/app.db
  - 用固定 SECRET_KEY，保证令牌可复现
  - 每个测试前清空三张表，保证用例互不干扰
"""
import os

# 必须在 import app 之前设置，db.py 在模块加载时读取 EXPENSE_DB
os.environ["EXPENSE_DB"] = "/tmp/test_expense_stage6.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-stage6"
os.environ["OCR_BACKEND"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.core import db as db_module
from app.main import app


@pytest.fixture
def client():
    """返回一个前置清空三张表的 TestClient，保证用例之间互不干扰。"""
    c = db_module._conn()
    c.executescript("DELETE FROM splits; DELETE FROM receipts; DELETE FROM users;")
    c.commit()
    c.close()
    return TestClient(app)
