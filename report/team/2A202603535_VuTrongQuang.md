# Báo cáo cá nhân — 2A202603535_VuTrongQuang

## 1. Thông tin thành viên

- Họ tên: Vũ Trọng Quang
- MSSV: 2A202603535
- Email: trongquangvu2004@gmail.com
- GitHub: Quangvu256

## 2. Phần việc phụ trách

- **Shape B — Single ReAct agent**: `src/lab8/shapes/single.py` (CP2, CP3).
- **Kiểm chứng shape `single` trong cổng crash / approval / secret** (CP4) và viết bộ test riêng `src/tests/test_2A202603535_single_shape.py` bám sát CP2–CP4.
- **Tài liệu hóa luồng xử lý**: `docs/single_agent_workflow.md` (mô tả ranh giới ReAct loop – Host Boundary).

## 3. Đóng góp cụ thể

**Commit chính:** `0907a74` (`src/lab8/shapes/single.py`, `src/reports/single_only.json`, CP2–CP3), merge vào `main` qua PR #3 (`13013af`).

### CP1 — Cài đặt, đọc contract, chia vai

- Cài môi trường Python trong `src/.venv`, chạy `lab8.smoke` pass trên Windows.
- Đọc `docs/business_rules.md`, `docs/contracts.md` và `swarm_reference.py`; xác định ranh giới của Shape B: tiền do `compute_compensation` tính (không do `MockLLM`), chữ trong ticket là dữ liệu người dùng, và các `status` hợp lệ của `RunResult` (`resolved`, `denied`, `needs_info`, `escalated`, `failed`).

### CP2 — Shape single

- Thay stub `TODO CP2`: `run_react` với `max_steps=8`, trả kết quả bằng `finish()`, có trace ở mọi nhánh return kể cả `needs_info`, `escalated` và `step_cap`.
- **Mức tự chủ B:** agent chỉ được chọn read tool (`get_claim_view → lookup_order → lookup_refund_history → compute_compensation`), không gọi `issue_refund`. Tiền do `compute_compensation` tính, không do MockLLM. `MockLLM.complete` chỉ được đếm vào `Budget`.
- **Chữ trong ticket là dữ liệu người dùng:** thiếu `order_id` thì trả `needs_info`, không parse từ ticket. Clause cũ (C-006) hay prompt injection (C-009) không đổi được số tiền.
- **Quote đầy đủ (T13, T14):** truyền nguyên quote vào `durability.issue_refund` để host áp per-order cap (C-014: quote 150000, host ghi 120000).
- **Shape tự từ chối thì không có audit `policy_denied`:** khi `proposal <= 0`, shape trả `denied` mà không gọi host (C-002, C-006, C-009).

### CP3 — Ledger, crash

- Truyền `crash_at` vào `durability.issue_refund`. Không bắt `InjectedCrash`: chỉ ghi event `crash`, gọi `trace.write()` rồi `raise`.
- Gọi lại cùng claim (T11) hay resume sau crash (T12) đều dựa vào ledger idempotent `refund:{claim_id}`, nên chỉ có một refund (khắc phục lỗi thiếu ledger như `lab8.demo.buggy_workflow`).

### CP4 — Crash, approval, secret

- Cả 3 điểm crash (`before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`) chạy qua shape `single` đều không tạo hơn một refund (`test_cp4_crash_point_never_creates_two_refunds`).
- Approval hết hạn (T07) và đơn đã hoàn đủ (T13): cổng host chặn, không refund (`_ledger_rows == 0`).
- Guardrail ngoài ma trận public (`src/tests/test_2A202603535_single_guardrails.py`): approval của claim khác bị chặn (`approval_claim_mismatch`), thiếu approval (`missing_approval`), ledger lệch tiền không bị ghi đè (`amount_conflict`), claim không tồn tại (`unknown_claim`), chạm step cap thì `failed` và không gọi `issue_refund`.
- Trace là ranh giới bảo mật: `get_claim_view` chỉ ghi `{tool, found, has_order_id}`; không ghi `ticket`, `CANARY_SECRET_*`, `parent_secret`, `raw_headers` hay order row thô.

### CP5 — Benchmark & hoàn thiện tài liệu

- Chạy benchmark riêng cho shape `single` trên 14 public claims × 5 seeds (`11, 22, 33, 44, 55`) xuất ra `src/reports/single_only.json`.
- Viết `src/tests/test_2A202603535_single_shape.py` (20 test case bám sát CP2–CP4, commit `8c30bf7`), `src/tests/test_2A202603535_single_guardrails.py` (5 test guardrail, commit `2080a32`) và `docs/single_agent_workflow.md`.
- Mutation check (sửa tạm `single.py`, chạy 25 test, rồi khôi phục): nuốt `InjectedCrash` → 4 fail; bỏ kiểm `outcome["ok"]` → 5 fail; ghi ticket vào trace → 5 fail. Bỏ nhánh `step_cap` → 0 fail vì là equivalent mutant (`run_react` đã trả `final.status = failed`, nhánh `failed` chung xử lý giống hệt).

## 4. Bằng chứng

Lệnh "Tự kiểm tra" theo `CHECKPOINTS.md`, chạy trong `src/` (bằng `.\.venv\Scripts\python.exe`):

| CP | Lệnh / Nguồn | Kết quả quan sát thực tế |
|---|---|---|
| CP1 | `python -m lab8.smoke` | `lab8.smoke pass` |
| CP2–CP3 | `python -m pytest -q -m student -o addopts=` | `248 passed, 79 deselected` (gồm T11, T12 của `single`) |
| CP2–CP4 | `python -m pytest -q tests/test_2A202603535_single_shape.py tests/test_2A202603535_single_guardrails.py` | `25 passed` (test tự viết cho shape `single`) |
| CP3 | `python -m pytest -q` | `79 passed, 248 deselected` |
| CP4 | `python -m lab8.crash_test --count 20 --out reports/crash.json` | Chưa tạo file `src/reports/crash.json` trên repo; đã kiểm chứng 3 crash points qua `test_2A202603535_single_shape.py` |
| CP5 | `src/reports/single_only.json` (shape `single`, 70 trials) | `pass_rate = 1.0`, `pass_5 = 1.0`, `seed_min–seed_max = 1.0–1.0`, `seed_variance = 0.0`, `cost_per_success_vnd = 38.73` (`38.7271...`, mô phỏng), `mean_steps = 4.64`, `mean_model_calls = 4.64`, `mean_tool_calls = 3.64` |

Run id dẫn chứng (đã xác nhận có file trong `src/traces/`): `R-single-C-014-s11` (T14), `R-single-C-004-s11` (`needs_info`), `R-single-C-005-s11` (`escalated`, không lộ PII).

## 5. Công cụ AI đã dùng

- **Claude Code (Claude Opus):** hỗ trợ rà trạng thái checkpoint, soạn bản nháp ban đầu của báo cáo này, viết `test_2A202603535_single_guardrails.py` và chạy mutation check (commit `8c30bf7`, `2080a32` có dòng `Co-Authored-By`).
- **Antigravity (Gemini 4 Hydrogen (Medium)):** rà soát lại toàn bộ `CHECKPOINTS.md`, đối chiếu số liệu thực tế trong `src/reports/single_only.json`, chạy lại `smoke` và `pytest`, cập nhật bảng bằng chứng và hoàn thiện mục Tự đánh giá.
- **Cách tự kiểm tra:** chạy lại trực tiếp các lệnh `lab8.smoke`, `pytest -q`, `pytest -q -m student -o addopts=`, `pytest -q tests/test_2A202603535_single_shape.py` trong `src/`; đối chiếu từng con số và tên symbol với `src/lab8/shapes/single.py`, `src/reports/single_only.json` và `src/traces/`. Không có số liệu nào được nhập tay hoặc suy đoán.

## 6. Tự đánh giá

- **Mức độ hoàn thành theo `CHECKPOINTS.md`:**
  - **CP1 – CP3:** Đạt 100% phần việc cá nhân cho Shape B (`single.py` đã merge qua PR #3, pass toàn bộ `79` core tests và `248` student matrix tests).
  - **CP4:** Đã kiểm chứng đầy đủ 3 crash points, approval hết hạn (T07), đơn hoàn đủ (T13)
  - **CP5:** Đã có kết quả benchmark riêng cho `single` (`src/reports/single_only.json`: `pass_rate 1.0`, `pass^5 1.0`, `seed_variance 0.0`)
- **Việc cần làm tiếp trước deadline:**
  1. Phối hợp nhóm chạy `lab8.crash_test` (`reports/crash.json`) và `lab8.benchmark` 4 shape (`reports/benchmark.json`), điền `TEAM.md` và chạy `python -m lab8.check_submission` đạt `0 FAIL`.
- **Bài học kỹ thuật rút ra:** Việc tách cứng ranh giới giữa vòng lặp ReAct (chỉ đọc dữ liệu và gọi `compute_compensation`) với Host Boundary (`durability.issue_refund`) giúp hệ thống vừa giữ được cấu trúc agentic ở bước thu thập ngữ cảnh, vừa đảm bảo tính tất định, chống prompt injection và giữ an toàn idempotency (`refund:{claim_id}`) khi xảy ra crash.


