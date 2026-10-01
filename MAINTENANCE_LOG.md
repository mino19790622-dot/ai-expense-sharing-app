# Maintenance log

> This file is appended automatically by a scheduled maintenance task, and the
> commits that touch it carry `[skip ci]`. Every entry corresponds to one real
> change that passed the repository's own checks before it was pushed.
>
> The entries are generated rather than hand-written, and they record
> maintenance work only — they are not a measure of manual development effort.

## 2026-09-22 — cover the proportional strategy and both degenerate fallbacks

- **Change**: new tests/test_split_strategies.py (6 tests): proportional end to end including the fact that tax follows consumption rather than headcount; the zero-consumption and zero-weight fallbacks; the unknown-method guard; and the payer receiving the integer-division remainder
- **Verification**: pytest tests: 36 passed; ruff: all checks passed

## 2026-09-23 — correct the stale test count in the README

- **Change**: README.md: the local-run section claimed '当前 28 passed', which no longer matched the suite; updated to the measured 36 passed
- **Verification**: pytest tests: 36 passed; ruff: not applicable (no .py changed)

## 2026-09-24 — 清掉 test_confirm.py 里未使用的 json 导入

- **Change**: tests/test_confirm.py 第 8 行 import json 全文件未被引用（其余 11 处 json 均为 client.post(json=...) 关键字或 .json() 方法调用），删除该行。同时消掉该文件唯一一处 ruff F401，使整份文件 lint 归零。
- **Verification**: pytest tests -q → 36 passed, 1 warning in 1.07s；ruff check tests/test_confirm.py → All checks passed!

## 2026-09-25 — test(auth): 让注册令牌真正被使用

- **Change**: tests/test_auth.py 中 token 被赋值却从未使用（ruff F841），把注册返回的令牌改为立即调用 /api/v1/auth/me 并断言 200 + username=alice；顺带清零该文件唯一一处存量 lint 违规。
- **Verification**: pytest 36 passed；ruff All checks passed

## 2026-09-30 — tests/test_auth.py 三个测试补 docstring

- **Change**: 为 test_register_and_login / test_me_requires_and_accepts_token / test_password_validation 各补一行 docstring，写清各自覆盖的断言（令牌可用性、401 分支、密码长度校验）。纯文档改动，未改任何断言或业务逻辑。
- **Verification**: pytest 36 passed; ruff check tests/test_auth.py -> All checks passed

## 2026-10-01 — 统一 locustfile.py 的 import 写法

- **Change**: locustfile.py: 'from locust import HttpUser, task, between' -> 'HttpUser, between, task'，按 ruff I001 排序；纯写法统一，不改变压测行为（三个名字都是同一模块的符号，导入顺序无语义影响）。
- **Verification**: pytest tests: 36 passed; ruff check locustfile.py: All checks passed

