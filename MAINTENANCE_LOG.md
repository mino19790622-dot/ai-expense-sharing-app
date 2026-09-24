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

