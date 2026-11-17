# Team

## Thông tin nhóm

- Tên nhóm: Something
- Lớp: L3A
- Repo nhóm: `K5-L3A-DAY08-Something-FromWorkflowsToAgents`
- URL repo: https://github.com/olivercuongnguyen-ca/K5-L3A-DAY08-Something-FromWorkflowsToAgents

## Thành viên

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
| 1 | Vũ Trọng Quang | 2A202603535 | trongquangvu2004@gmail.com | Quangvu256 | Single agent (shape B) |
| 2 | Nguyễn Thị Hương Giang | 2A202603538 | 26ai.giangnth3@vinuni.edu.vn | nthgiang311 | Deterministic Workflow (shape A) |
| 3 | Nguyễn Hoàng Cương | 2A202603568 | olivercuongnguyen@gmail.com | olivercuongnguyen-ca | Orchestrator (shape C), benchmark, bonus B3, báo cáo, trưởng nhóm |

## Bảng đóng góp

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Vũ Trọng Quang (2A202603535) | Single agent (shape B) | `0907a74` (PR #3) | `src/tests/test_2A202603535_single_shape.py`: `test_cp3_t11_retry_same_claim_is_one_refund`, `test_cp3_t12_crash_is_not_swallowed_and_resume_is_once`, `test_cp4_crash_point_never_creates_two_refunds`, `test_cp4_t07_expired_approval_no_refund`, `test_cp4_t13_fully_refunded_order_no_refund`, `test_cp4_no_secret_or_raw_row_in_trace_or_stdout`, `test_cp2_*` (trace, needs_info, cap T14); `src/tests/test_2A202603535_single_guardrails.py`: `test_single_approval_of_other_claim_is_blocked`, `test_single_missing_approval_no_refund`, `test_single_ledger_amount_conflict_does_not_write_second_refund`, `test_single_unknown_claim_fails_with_trace`, `test_single_step_cap_fails_closed` |
| Nguyễn Thị Hương Giang (2A202603538) | Deterministic Workflow (shape A) | `51db0c9`, `abcfc5b`, `93c0930` | `src/tests/test_202603538_workflow_unknown_claim.py` – `test_workflow_unknown_claim_does_not_create_refund` |
| Nguyễn Hoàng Cương (2A202603568) | Orchestrator (shape C), benchmark, bonus B3, báo cáo, trưởng nhóm | `dd07988`, `b8fc761`, `af4df40`, `48f1f57`, `339325a`, `9a3168e` | `src/tests/test_2A202603568_orchestrator.py`: `test_ticket_delay_never_changes_the_money`, `test_handoff_is_read_only_and_trace_has_no_secret`, `test_full_quote_is_passed_so_host_pays_only_the_difference`, `test_zero_quote_does_not_call_the_host`, `test_host_rejection_keeps_full_quote_and_audit`; `src/tests/test_bonus_swarm_verified.py` (61 test của bonus B3) |

## Cá nhân

### 2A202603535_VuTrongQuang

Báo cáo chi tiết: [report/team/2A202603535_VuTrongQuang.md](report/team/2A202603535_VuTrongQuang.md).

### Phần việc phụ trách

- Shape B — Single ReAct agent: `src/lab8/shapes/single.py` (CP2, CP3).
- Kiểm chứng shape single trong cổng crash / approval / secret (CP4).

### Đóng góp cụ thể

- CP2: thay stub bằng `run_react` (`max_steps=8`). Agent chỉ dùng read tool, tiền do `compute_compensation` tính, trả về qua `finish()` có trace ở mọi nhánh. Thiếu `order_id` thì trả `needs_info`, không parse từ ticket. Truyền quote đầy đủ vào `durability.issue_refund` (T13, T14).
- CP3: truyền `crash_at` vào `issue_refund`, không bắt `InjectedCrash`. Gọi lại hoặc resume đều dựa vào ledger idempotent `refund:{claim_id}` (T11, T12).
- CP4: trace không ghi ticket, `parent_secret`, `raw_headers` hay order row thô.

### Bằng chứng

- Commit `0907a74`, merge qua PR #3 (`13013af`).
- `python -m pytest -q -m student -o addopts=` -> `248 passed`; `python -m pytest -q` -> xanh.
- `reports/benchmark.json`, shape `single`: pass_rate 1.0, pass^5 1.0, variance 0.0, cost/success 38.73 VND (mô phỏng).
- Run id: `R-single-C-014-s11`, `R-single-C-004-s11`, `R-single-C-005-s11`.

### 2A202603538_NguyenThiHuongGiang

Báo cáo chi tiết: [report/team/2A202603538_NguyenThiHuongGiang.md](report/team/2A202603538_NguyenThiHuongGiang.md).

### Phần việc phụ trách

- Shape A — Deterministic Workflow: `src/lab8/shapes/workflow.py` (CP2, CP3).
- Bổ sung kiểm thử hành vi workflow theo yêu cầu C8.
- Chạy kiểm thử và hidden benchmark self-check cho ba kiến trúc workflow, single và orchestrator.

### Đóng góp cụ thể

- CP2: triển khai `run_claim()` theo luồng xác định: đọc claim, kiểm tra thông tin, tra cứu đơn hàng, kiểm tra quyền truy cập, tính toán khoản bồi thường và thực hiện hoàn tiền. Xử lý các trạng thái `needs_info`, `escalated`, `denied`, `resolved` và `failed`. Sử dụng `compute_compensation()` để tính số tiền thay vì để LLM tự quyết định.
- CP3: truyền `crash_at` xuống `issue_refund()`, không bắt và nuốt ngoại lệ `InjectedCrash`, giữ nguyên cơ chế xử lý crash và retry của durability layer.
- C8: thêm test `test_workflow_unknown_claim_does_not_create_refund()` để xác nhận claim không tồn tại phải trả về `failed`, không tạo refund effect và không ghi nhận audit hoàn tiền.

### Bằng chứng

- Commit `51db0c9` – Implement deterministic workflow shape.
- Commit `abcfc5b` – Implement workflow crash recovery.
- Commit `93c0930` – Add workflow unknown claim test.
- Kiểm thử workflow: `62 passed, 240 deselected`.
- Kiểm thử riêng C8: `1 passed`.
- Kiểm thử toàn bộ test suite: `55 passed, 248 deselected`.
- Hidden benchmark self-check: 200 trials cho mỗi kiến trúc; workflow có mean steps 3.55, mean model calls 0, tổng simulated cost 7,050 VND; không ghi nhận error trials hoặc leak suspect trials. Dữ liệu không có nhãn nên không tính được pass rate chính thức.

### 2A202603568_NguyenHoangCuong

Báo cáo chi tiết: [report/team/2A202603568_NguyenHoangCuong.md](report/team/2A202603568_NguyenHoangCuong.md).

### Phần việc phụ trách

- Shape C — Orchestrator: `src/lab8/shapes/orchestrator.py` (CP2, CP3).
- Benchmark 4 shape x 5 seed và crash suite (`src/reports/benchmark.json`, `src/reports/crash.json`).
- Điền `report/team/decision_adr.md`.
- Bonus B3 (swarm + verifier): `src/bonus/swarm_verified.py`, `bonus/cases.jsonl`, `bonus/world.json`, `src/reports/bonus_public.json`, `src/reports/bonus_adversarial.json`, `report/team/bonus_report.md`.
- Báo cáo: `report/team/research_card.md` (R1), `report/team/group_report.md`, báo cáo cá nhân.

### Đóng góp cụ thể

- CP2: orchestrator không đọc nội dung ticket; tiền chỉ lấy từ `compute_compensation` dựa trên order row. Handoff qua `make_handoff` với `facts={}` và bốn tool đọc, investigator không có `issue_refund`. Truyền quote đầy đủ để host tự trừ phần đã hoàn (T14). Quote bằng 0 thì `denied` và không gọi host.
- CP3: truyền `crash_at` vào `issue_refund`; `InjectedCrash` chỉ ghi trace rồi `raise` lại (T12).
- CP4: trace chỉ ghi handoff đã sanitize, không ghi claim row, ticket hay secret.
- Benchmark và crash suite sinh bằng `lab8.benchmark` và `lab8.crash_test`, không sửa tay.
- Bonus B3: verifier bằng code đối chiếu `delay_days`, `status`, `damage_verified`, phí ship và số tiền đã trả với order có cấu trúc trước khi quote, tối đa 1 vòng sửa, ghi `verifier_override`. 11 claim đối kháng tự viết với nhãn tay; swarm_verified đạt 1.000 trên cả bộ public và bộ tự viết (swarm 0.986 và 0.891), cost/success cao hơn workflow khoảng 68–88%.

### Bằng chứng

- Commit `dd07988` (orchestrator), `b8fc761` (benchmark, crash), `af4df40` (hidden claims và test cá nhân).
- `python -m pytest -q -m student -o addopts=` -> `248 passed`; `python -m pytest -q` -> xanh.
- `reports/crash.json`: `crash_safety` = `20/20`.
- `reports/benchmark.json`, shape `orchestrator`: pass_rate 1.0, pass^5 1.0, variance 0, cost/success 56.65 VND (mô phỏng); workflow 34.29 VND.
- Run id: `R-orchestrator-C-001-s11`.
- Bonus: `python -m pytest -q tests/test_bonus_swarm_verified.py` -> 61 passed; trace minh họa `R-swarm_verified-B-01-s55`.
