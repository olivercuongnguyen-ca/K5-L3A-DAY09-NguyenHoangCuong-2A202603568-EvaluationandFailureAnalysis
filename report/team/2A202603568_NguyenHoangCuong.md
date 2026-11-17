# Báo cáo cá nhân — 2A202603568_NguyenHoangCuong

## 1. Thông tin thành viên

- Họ tên: Nguyễn Hoàng Cương
- MSSV: 2A202603568
- Email: olivercuongnguyen@gmail.com
- GitHub: olivercuongnguyen-ca

## 2. Phần việc phụ trách

- Shape C `orchestrator` (`src/lab8/shapes/orchestrator.py`): orchestrator đọc claim, dựng handoff cho investigator chỉ có tool đọc, rồi tự gọi `durability.issue_refund`.
- Benchmark 4 shape x 5 seed trên bộ public và crash suite (`src/reports/benchmark.json`, `src/reports/crash.json`).
- Điền `report/team/decision_adr.md`.
- Bonus B3 (swarm + verifier bằng code): `src/bonus/`, `src/tests/test_bonus_swarm_verified.py`, `src/reports/bonus_*.json`, `report/team/bonus_report.md`.
- Báo cáo nhóm: `report/team/research_card.md` (R1) và `report/team/group_report.md`.

## 3. Đóng góp cụ thể

Commit chính:

| Commit | Nội dung |
| --- | --- |
| `dd07988` | `done orchestrator`: viết shape orchestrator (77 dòng thêm, 6 dòng bỏ) |
| `b8fc761` | `done benchmark`: sinh `benchmark.json` và `crash.json` bằng `lab8.benchmark` và `lab8.crash_test` |
| `01a8175` | `update benchmark for swarm`: chạy lại benchmark có shape swarm |
| `9e719a2` | `fill decision_adr`: điền ADR và tên nhóm trong `TEAM.md` |
| `48f1f57` | `demo bonus`: `swarm_verified.py`, 11 claim đối kháng và world tự viết |
| `339325a` | `done research card`: phiếu nghiên cứu R1 |
| `9a3168e` | `done bonus report`: `bonus_report.md` |

Quyết định kỹ thuật trong `orchestrator.py`:

- Orchestrator không đọc nội dung ticket. Tiền chỉ lấy từ `compute_compensation` dựa trên order row, nên không có đường để chữ trong ticket ("ignore policy", "trễ 9 ngày") ảnh hưởng số tiền. Đây là chỗ khác với swarm tham chiếu (`REFERENCE_WEAKNESS`).
- Handoff dựng bằng `make_handoff` với `facts={}` và bốn tool đọc: `lookup_order`, `lookup_policy`, `lookup_refund_history`, `compute_compensation`. Trace chỉ ghi handoff đã sanitize, không ghi claim row hay parent context.
- Truyền **quote đầy đủ** vào `issue_refund`. Host tự trừ phần đã hoàn trên đơn, nên T14 (đơn đã hoàn 30.000, hỏng hàng 150.000 thì ledger 120.000) đúng; nếu shape tự trừ thì host trừ hai lần.
- Quote bằng 0 thì trả `denied` và không gọi `issue_refund`. Quote lớn hơn 0 mà host từ chối thì `denied` với `proposal_amount` bằng quote, để host ghi audit `policy_denied`.
- `crash_at` được truyền vào `issue_refund`. `InjectedCrash` chỉ được bắt để ghi trace rồi `raise` lại, không nuốt (T12).
- Mọi nhánh return đi qua `finish()` nên luôn có trace đúng contract và `refund_effects` lấy từ ledger.
- Chỉ dùng một lời gọi model `draft` để soạn chữ trả lời. Model không quyết định tiền.

Test đã thêm hoặc sửa: `src/tests/test_2A202603568_orchestrator.py` (không gắn marker `student`, chạy trong cổng host):

- `test_ticket_delay_never_changes_the_money`: ticket C-002 ghi trễ 5 ngày nhưng order ghi 2 ngày, orchestrator phải `denied` ở cả 5 seed (swarm tin ticket và trả 20.000 ở seed 55).
- `test_handoff_is_read_only_and_trace_has_no_secret`: handoff chỉ có tool đọc, `facts` rỗng; trace không chứa secret, PII hay nội dung ticket.
- `test_full_quote_is_passed_so_host_pays_only_the_difference`: T14, `proposal_amount` 150.000 và ledger 120.000.
- `test_zero_quote_does_not_call_the_host`: quote bằng 0 thì không có audit và không có dòng ledger.
- `test_host_rejection_keeps_full_quote_and_audit`: T07, approval hết hạn thì `denied`, quote giữ 35.000, có audit `policy_denied`.

Bonus B3 (`src/bonus/swarm_verified.py`): giữ nguyên swarm (kể cả điểm yếu seed % 5 == 0 tin ticket) và thêm bước `_verify` trước khi ghi. Verifier đọc lại order có cấu trúc, so `status`, `delay_days`, `damage_verified`, phí ship và số tiền đã trả với dữ kiện dùng để quote; nếu lệch thì quote lại từ dữ liệu có cấu trúc (tối đa 1 vòng) và ghi `verifier_override` vào trace. Kết quả: pass rate về 1.000, nhưng cost/success cao hơn workflow khoảng 68–88%, nên verifier thay luôn phần quyết định và swarm gần như không còn giá trị riêng. Giới hạn: lỗi của swarm là quy tắc cố định, không phải lỗi thật của model.

## 4. Bằng chứng

- `python -m pytest -q -m student -o addopts= -k orchestrator` ra `62 passed`.
- Cổng host `python -m pytest -q` ra `63 passed` (Python 3.12.16), gồm 9 test mới của `test_2A202603568_orchestrator.py`.
- `python -m lab8.crash_test --count 20 --out reports/crash.json` ra `crash_safety` = `20/20`.
- Benchmark public, 14 claim x 5 seed, `src/reports/benchmark.json`:

| Shape | Pass rate | pass^5 | Variance | Cost/success (VND, mô phỏng) |
| --- | --- | --- | --- | --- |
| workflow | 1.000 | 1.000 | 0 | 34.29 |
| single | 1.000 | 1.000 | 0 | 38.73 |
| orchestrator | 1.000 | 1.000 | 0 | 56.65 |
| swarm | 0.986 | 0.929 | 0.000816 | 49.57 |

- Run id ví dụ: `R-orchestrator-C-001-s11`.
- Bonus B3: `python -m pytest -q tests/test_bonus_swarm_verified.py` ra `61 passed`; `python -m pytest -q` ra `150 passed`. Benchmark swarm, swarm_verified và workflow ghi vào `reports/bonus_public.json` (14 claim x 5 seed) và `reports/bonus_adversarial.json` (11 claim x 5 seed):

| Bộ | Shape | Pass rate | pass^5 | Cost/success (VND, mô phỏng) |
| --- | --- | --- | --- | --- |
| Public | swarm | 0.986 | 0.929 | 49.57 |
| Public | swarm_verified | 1.000 | 1.000 | 57.57 |
| Tự viết | swarm | 0.891 | 0.455 | 59.27 |
| Tự viết | swarm_verified | 1.000 | 1.000 | 63.35 |
| Tự viết | workflow | 1.000 | 1.000 | 33.64 |

- Trace minh họa `R-swarm_verified-B-01-s55`: order trễ 2 ngày, swarm tin ticket (7 ngày) và quote 22.000; verifier phát hiện lệch và quote lại về 0, claim `denied`.
- `check_submission` ra 0 FAIL.
- Quét `CANARY_SECRET`, `parent_secret`, `raw_headers` trên `src/traces` (280 file) và `src/reports` cho kết quả rỗng.

## 5. Công cụ AI đã dùng

- Claude Code: giải thích luật nghiệp vụ và contract, hướng dẫn từng bước viết `orchestrator.py`, tìm nguyên nhân hai test benchmark đỏ (lệch version do dùng Python 3.9, cần 3.11 trở lên). Viết test bonus, chạy benchmark.
- Cách tự kiểm tra: tự gõ và chạy `orchestrator.py`, tự chạy 62 test student của shape, cổng host, crash suite và benchmark. Đối chiếu số liệu trong ADR và báo cáo này với `reports/benchmark.json` và `reports/crash.json` do script sẵn sinh ra. Đọc lại `workflow.py` để xác nhận danh sách event trace trong ADR đúng với code, và ADR đã được sửa hai chỗ sai sau lần đối chiếu đó.

## 6. Tự đánh giá

**Kết quả:** Shape orchestrator đạt độ chính xác tốt trên benchmark public: pass rate 1.000, pass^5 1.000, variance 0, qua 62 test student, và crash suite 20/20. Tuy nhiên, chi phí cao hơn nhiều so với workflow: 56.65 so với 34.29 VND/success (cao hơn khoảng 65%), và trung bình 5.57 tool call mỗi trial so với 3.43. Chi phí tăng vì phải thêm bước handoff, chạy investigator và gọi thêm tool đọc (`lookup_policy`, `lookup_refund_history`) mà quy trình này không thực sự cần để ra đúng số tiền.

**Nhận định:** Với bài toán claim hoàn phí, quy trình gần như cố định (kiểm sở hữu, chọn policy hiện hành, tính tiền, gọi host), nên orchestrator không phù hợp: nó không đúng hơn workflow nhưng tốn hơn. Chia việc cho investigator chỉ có ích khi các bước đọc độc lập và có thể chạy song song, còn ở đây bước quote phụ thuộc vào kết quả `lookup_order`. Vì vậy nhóm chọn workflow. Kết luận này dựa trên bộ public, nơi cả ba shape đều đạt 1.000.

**Điều học được:** Việc viết orchestrator và đọc các shape khác giúp nắm các bước dựng một pattern agent và ranh giới giữa code với model: code đọc claim và quyết định số tiền, model chỉ soạn chữ; handoff phải qua allowlist chứ tóm tắt bằng LLM không phải là redaction; investigator chỉ có tool đọc, chỉ orchestrator gọi `issue_refund`; phải truyền quote đầy đủ để host tự trừ phần đã hoàn (T14); `crash_at` phải đi tới host và không được nuốt `InjectedCrash`; trace là ranh giới bảo mật nên không ghi claim row hay order row thô.
