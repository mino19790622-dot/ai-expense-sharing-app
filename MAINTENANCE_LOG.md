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

