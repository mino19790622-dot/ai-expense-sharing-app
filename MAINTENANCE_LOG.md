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

## 2026-10-02 — 统一 db.py 的标准库 import 排序（I001）

- **Change**: app/core/db.py 的 stdlib import 块按字母序排列：import json 从 time 之后提到 os 之前（json < os < sqlite3 < time）。纯写法统一，不改变任何运行时行为；顺手清零该文件唯一一处 ruff I001，使其从带债名单毕业。
- **Verification**: pytest tests: 36 passed；ruff check app/core/db.py: All checks passed（"files" 仅 app/core/db.py）

## 2026-10-05 — 整理 split 测试的导入顺序并补全用例说明

- **Change**: tests/test_split.py: 修正 I001 导入块（compute 归位到字母序末尾，第三方/本地之间补空行），并为 5 个测试函数各补一行 docstring，说明各策略断言的口径。未改任何断言与业务逻辑。
- **Verification**: pytest 36 passed；ruff check tests/test_split.py All checks passed

## 2026-10-06 — 整理测试公共配置的导入顺序并补 fixture 说明

- **Change**: tests/conftest.py: 修正 ruff I001 导入块（第三方与本地 import 之间补空行，app.core 归位到 app.main 之前），并给 client fixture 补一行 docstring 说明「前置清空三张表、保证用例互不干扰」；原来那行重复的同行注释一并删掉。os.environ 的三行前置赋值一行未动，仍在 import app 之前。未改任何断言与业务逻辑。
- **Verification**: pytest tests -q -> 36 passed（改前 36，未增减）；ruff check tests/conftest.py -> All checks passed；该文件唯一一处存量违规清零，仓库总量 67 -> 66

## 2026-10-07 — README 目录树与 API 表对齐 Stage 6

- **Change**: README.md 的目录树仍停留在 Stage 5：app/api/ 只列了 routes.py（漏 auth_routes.py），app/core/ 只列到 middleware.py（漏 auth.py / db.py）；routes.py 的端点注释漏了 /confirm 与 /history；tests/ 的说明也漏了 auth/confirm/strategies。另补上 API 速览表里缺失的 GET /api/v1/history 一行。纯文档，未改任何代码或断言。
- **Verification**: pytest tests -q -> 36 passed（改前 36，未增减）；ruff 不适用（本次只改 .md）；逐项核对：README 列出的 8 个测试域与 tests/ 下 8 个 test_*.py 一一对应，/history 端点确在 app/api/routes.py:207

## 2026-10-08 — Test the greedy _min_cash_flow core directly

- **Change**: tests/test_debt.py: the private helper _min_cash_flow was imported but never used (ruff F401) and had zero direct coverage, despite being the greedy core that settle() delegates to. Added two tests: exact 2-debtor/2-creditor chain output, and the no-op cases plus the int-cents conservation invariant. Expected values were obtained by running the function first, not inferred. Also sorted the import line (ruff I001). No business logic touched.
- **Verification**: pytest 38 passed (was 36, +2); ruff All checks passed on tests/test_debt.py; file now lint-clean (2 -> 0).

## 2026-10-09 — docs(db): list_history 的四条隐式契约

- **Change**: app/core/db.py 的 list_history() 原 docstring 只有一句「返回该用户的收据 + 对应分账，按时间倒序」。补写四条调用方必须知道的契约：(1) 以 receipts 为左表 LEFT JOIN splits ⇒ 无分账的收据照样返回且 split_id/method/shares 为 None，同一收据挂多条分账则各占一行；(2) receipt_id 为 NULL 的分账永远查不到（连接条件 s.receipt_id = r.id 匹配不上 NULL），而 POST /split 正是以 receipt_id=None 落库 ⇒ 只有 POST /confirm 的组合可追溯；(3) 硬编码 LIMIT 50、无分页参数，第 51 条起静默丢弃，调用方无法区分「只有 50 条」与「被截断」；(4) shares_json 为空串或 NULL 时 shares 收敛为 None，不抛 JSONDecodeError。四条均用临时库实测确认（无分账收据 1 行、双分账收据 2 行、孤儿分账 0 行、空串 shares_json → None）。纯文档，+15/-1，无行为变更。
- **Verification**: pytest 38 passed；ruff All checks passed（仅 lint 改动文件 app/core/db.py）

## 2026-10-15 — docs(db): pin the return and exception contracts of the user helpers

- **Change**: 给 app/core/db.py 的 create_user / get_user_by_username / get_user_by_id 补 docstring（+28 行，纯文档，无行为变更）。三条契约均先用 /tmp 临时库探针实测确认：(1) username 有 UNIQUE 约束，重复插入抛 sqlite3.IntegrityError('UNIQUE constraint failed: users.username')，不返回哨兵值；(2) auth_routes.py 的注册流程是 get_user_by_username 查重 + create_user 插入的两步写法，并发下同用户名会撞 UNIQUE 且异常未在路由层捕获 => 500 而非 409（TOCTOU）；(3) 两个 getter 命中返回 dict、未命中返回 None，auth.py:98-100 依赖该 None 语义判 401。
- **Verification**: ok:true — pytest 38 passed；ruff All checks passed（仅 lint 改动文件 app/core/db.py）

## 2026-10-16 — README 环境变量表补齐 + 测试数同步

- **Change**: README.md: ① 环境变量表原列 3 项(OCR_BACKEND/DASHSCOPE_API_KEY/ACCESS_LOG_FILE)，实测代码共读 6 项，补 OCR_MODEL(默认 qwen-vl-max, ocr.py:93, 仅 OCR_BACKEND=qwen 生效)/EXPENSE_DB(默认 app/data/app.db, db.py:19)/SECRET_KEY(默认 dev-insecure-change-me, auth.py:24, 令牌 HMAC 签名密钥); ② 本地运行段'当前 36 passed'与实测不符, 改为 38。仅文档 +4/-1, 无行为变更。
- **Verification**: pytest 38 passed; 仅改 .md, lint 跳过

## 2026-10-19 — 为 save_receipt / save_split 补写外键与 NULL 契约

- **Change**: app/core/db.py 两个此前无 docstring 的写入函数补文档（+35/-0，纯注释，业务逻辑零改动）：save_receipt 说明 receipts.user_id 声明了外键故传坏 user_id 抛 IntegrityError、其余四列均可为空会原样落 NULL、items_json 只透传需调用方序列化；save_split 说明 splits.receipt_id 没有外键故传坏 receipt_id 会静默成功、这类孤儿分账因 LEFT JOIN 永远查不到、receipt_id=None 是 /split 的刻意写法。四条断言全部用临时库探针实测取得。
- **Verification**: pytest 38 passed；ruff app/core/db.py All checks passed

## 2026-10-20 — OCR/scan 测试补 docstring

- **Change**: tests/test_ocr.py 的 5 个测试各补一行 docstring：说明 401 鉴权拦截、mock 后端固定 paid_by=u1 的原因、/scan 的 shares+receipt_id 双返回、非图片走 400 而非 422/500、history 断言用 >=1 不假设空库。纯注释，不改运行时行为。
- **Verification**: pytest 38 passed；ruff tests/test_ocr.py All checks passed

## 2026-10-21 — locustfile 的 /split 压测流量实际全是 404

- **Change**: 给 health / split 两个 task 补 docstring。核心事实：Stage 6 把业务路由挂到 APIRouter(prefix='/api/v1') 后，locustfile 里仍打旧路径 /split；TestClient 实测 POST /split -> 404，POST /api/v1/split 无 token -> 401，故 locust 报表里 split 的 p50/p99 是路由未命中的往返耗时，与 compute() 的 CPU 成本无关。修复需同时换路径 + 在 on_start 登录取 Bearer token，属改压测口径，本次只记录未改动。另注明 /health 是唯一免鉴权端点。
- **Verification**: pytest 38 passed; ruff locustfile.py All checks passed

## 2026-10-22 — test_confirm.py 补 docstring

- **Change**: 给 3 个无注释的测试（requires_auth / persists_receipt_and_shows_in_history / bad_method_400）与 3 个模块级辅助函数（_token / _hdr / _body）各补一行 docstring，写明 401 拦截发生在鉴权而非校验阶段、/history 按收据创建时间倒序故取 rows[0]、未知 method 由 compute() 抛 ValueError 后由路由层转 400。纯文档，不改运行时行为。
- **Verification**: pytest 38 passed, 1 warning; ruff clean (tests/test_confirm.py)

## 2026-10-24 — 补访问日志测试的模块说明与字段断言

- **Change**: tests/test_observability.py: ① 新增模块 docstring, 说明覆盖的两条契约, 并写明中间件实例在首次 dispatch 后缓存 _fh、不再读环境变量, 故不能靠换 ACCESS_LOG_FILE 验证其他分支; ② 原测试补三处断言: 两次请求应追加两行(len==2)、method==GET、client 字段存在。纯测试+文档, 无运行时行为变更。
- **Verification**: pytest 38 passed; ruff check tests/test_observability.py: All checks passed

## 2026-10-26 — 测试 /scan 的 paid_by 优先级与两条 400 分支

- **Change**: tests/test_ocr.py 新增 4 个测试：/ocr 非图片 400（此前零覆盖）、/scan participants 非法 JSON 400、显式 paid_by=u2 覆盖 mock 的 u1、paid_by 为幽灵 id 时回落 participants[0].id（用 x1/x2 使白名单条件真正成立）。纯测试增量，生产代码零改动。
- **Verification**: pytest 42 passed（改前 38，+4）；ruff tests/test_ocr.py All checks passed；app/api/routes.py 覆盖率 87%→93%（余 6 行均为 except ValueError）

## 2026-10-27 — README API 表补鉴权列与三个 auth 端点

- **Change**: API 速览表原缺 /api/v1/auth/{register,login,me} 三条，且只在 /history 一行写「需令牌」，暗示其余端点免鉴权。实际 routes.py 的 6 个业务端点全部挂了 Depends(get_current_user)。新增「鉴权」列逐行标注，并补一段说明令牌走 Authorization: Bearer（HTTPBearer）、401 带 WWW-Authenticate，register/login 的校验规则与「同报 401 防账号枚举」。纯文档，无代码改动。
- **Verification**: pytest 42 passed; 仅改 .md ⇒ lint 跳过

