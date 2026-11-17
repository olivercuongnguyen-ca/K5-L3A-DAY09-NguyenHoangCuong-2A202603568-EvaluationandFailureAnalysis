# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: Something (lớp L3A)
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): `f882a82`

## 2. Mục tiêu và cách tiếp cận

Bài toán LogiX-VN: xử lý claim hoàn phí giao hàng trễ hoặc hàng hỏng. Quy trình về cơ bản cố định: kiểm quyền sở hữu đơn, chọn policy hiện hành, tính tiền, xin approval, ghi refund. Ba điều bắt buộc: không refund khi thiếu approval hợp lệ, không lộ `CANARY_SECRET_*`, crash không tạo quá một refund. Câu hỏi của lab là cần bao nhiêu tự chủ của agent để làm đúng việc này, đo bằng pass rate, pass^5, variance và cost/success trên cùng claim, seed và bảng giá.

Phân công (chi tiết ở `TEAM.md`): Giang viết shape A (workflow); Quang viết shape B (single ReAct); Cương viết shape C (orchestrator), chạy benchmark, crash suite và điền ADR. Shape D (swarm) là bản tham chiếu có sẵn để so sánh. Thứ tự làm: workflow trước (làm mốc), rồi single, rồi orchestrator, cuối cùng chạy benchmark chung cho cả bốn shape.

## 3. Giải pháp

**Ranh giới code / model (chung cho cả ba shape).** Code quyết định lọc theo principal, policy hiệu lực, số tiền (`compute_compensation`), approval, idempotency và việc ghi refund. Model chỉ đọc ticket mơ hồ và soạn chữ trả lời; model không bao giờ quyết định số tiền. Mọi việc ghi đi qua một đường duy nhất là `durability.issue_refund` của host, với quote đầy đủ (host tự trừ phần đã hoàn trên đơn, nên shape không được tự trừ). `crash_at` được truyền xuống host và `InjectedCrash` không bị nuốt; retry và resume dựa vào ledger idempotent `refund:{claim_id}`. Tham khảo [docs/architecture.md](../../docs/architecture.md).

**A — Workflow (`src/lab8/shapes/workflow.py`).** `run_claim()` chạy các bước cố định trong Python: đọc claim, kiểm tra thiếu thông tin (`needs_info`), tra đơn và quyền truy cập (`escalated` nếu không thấy), tính quote, gọi host. Không có lần gọi model nào (mean model calls 0). Trạng thái trả về: `needs_info`, `escalated`, `denied`, `resolved`, `failed`.

**B — Single (`src/lab8/shapes/single.py`).** Một vòng ReAct (`run_react`, `max_steps=8`). Agent chỉ có tool đọc; tiền do `compute_compensation` tính; thiếu `order_id` thì `needs_info`, không parse từ ticket. Vượt giới hạn bước thì thất bại an toàn (không ghi gì).

**C — Orchestrator (`src/lab8/shapes/orchestrator.py`).** Orchestrator không đọc nội dung ticket để quyết tiền. Nó dựng handoff `handoff.v1` qua `make_handoff` với `facts={}` và bốn tool đọc (`lookup_order`, `lookup_policy`, `lookup_refund_history`, `compute_compensation`), giao cho investigator chỉ đọc, rồi tự gọi `issue_refund`. Quote bằng 0 thì `denied` và không gọi host. Một lần gọi model `draft` để soạn chữ.

**Handoff và trace.** Handoff chỉ gồm các field allowlist; `parent_secret`, header, history và tool ghi không được có mặt (tóm tắt bằng LLM không tính là redaction). Trace của workflow ghi `claim_read`, `order_lookup`, `quote`, `refund_result`, `decision`, `error`, `crash`; orchestrator thêm `handoff` và `investigator` (đã sanitize). Cố ý không ghi claim row, ticket, order row thô, SĐT, địa chỉ hay header. Mọi nhánh return đều đi qua `finish()` nên luôn có trace.

## 4. Kết quả

Bộ public: 14 claim x 5 seed (11, 22, 33, 44, 55) = 70 trial mỗi shape, số liệu từ `src/reports/benchmark.json`. Chi phí là giá mô phỏng (VND), không phải hóa đơn API; latency là `unavailable`.

| Shape | Pass rate | pass^5 | Seed min–max | Variance | Cost/success | Mean steps |
| --- | --- | --- | --- | --- | --- | --- |
| workflow | 1.000 | 1.000 | 1.000–1.000 | 0 | 34.29 | 3.50 |
| single | 1.000 | 1.000 | 1.000–1.000 | 0 | 38.73 | 4.64 |
| orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0 | 56.65 | 2.79 |
| swarm | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 |

- **Crash safety:** `src/reports/crash.json` đạt 20/20 (điểm crash `before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`, cùng các kịch bản lệch số tiền khi retry, retry thiếu approval và swarm).
- **Tự kiểm trên `student_drop/`:** `src/reports/hidden_selfcheck.json`, 200 trial mỗi shape cho workflow, single, orchestrator; không có trial lỗi hạ tầng hay nghi lộ secret. Dữ liệu không có nhãn nên không tính được pass rate chính thức. Mean steps: workflow 3.55, single 4.83, orchestrator 2.90.
- **Swarm:** trial fail duy nhất là `R-swarm-C-002-s55` (ở seed 55 swarm tin ticket hơn cột `delay_days`).
- **Bonus B3** (`report/team/bonus_report.md`): thêm verifier bằng code vào swarm đưa pass rate về 1.000 trên cả bộ public và bộ 11 claim đối kháng tự viết, nhưng cost/success cao hơn workflow khoảng 68–88%.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

- **Sai phiên bản Python.** Hai test benchmark đỏ khi chạy bằng Python 3.9; dự án cần 3.11 trở lên. Chạy lại bằng `.venv` (Python 3.12) thì xanh (`python -m pytest -q`).
- **Swarm tin ticket ở seed 55.** `R-swarm-C-002-s55` trả 20.000 VND dù đơn chỉ trễ 2 ngày (lý do: `status resolved != denied`). Orchestrator và workflow không có đường nào để chữ trong ticket đổi số tiền, nên không gặp lỗi này. Test `test_ticket_delay_never_changes_the_money` giữ điều đó.
- **Mất nội dung khi merge.** Sau một lần merge từ `main` (`resolve merge conflicts from main`), `TEAM.md` mất dòng và mục cá nhân của Cương, và tên file test của Giang bị ghi sai (`test_202603404_...` thay vì `test_202603538_...`). Nhóm phát hiện bằng `python -m lab8.check_submission` (báo số thành viên trong bảng đóng góp) và đọc lại file, rồi khôi phục. Bài học: chạy `check_submission` sau mỗi merge.
- **Trừ tiền hai lần (T14).** Nếu shape tự trừ phần đã hoàn trên đơn rồi host lại trừ, kết quả sai. Cách xử lý: mọi shape truyền quote đầy đủ, host trừ một lần (đơn đã hoàn 30.000, hỏng hàng 150.000 thì ledger 120.000).

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

MockLLM không phải model sản xuất; latency là `unavailable`.

- Trên bộ public cả ba shape nhóm viết đều đạt 1.000 nên pass rate không phân biệt được chúng; chênh lệch duy nhất là chi phí mô phỏng. Chưa kiểm chứng trên bộ hidden có nhãn.
- Chọn workflow vì quy trình cố định. Kết luận đảo lại nếu: workflow rớt dưới ngưỡng 0.75 ở nhóm claim có ticket mơ hồ cần đọc hiểu ngôn ngữ tự do; có phần đọc độc lập thật sự song song; hoặc dùng model thật.
- Điểm yếu của swarm là một quy tắc cố định (seed chia hết cho 5), nên việc verifier bonus chặn được nó không chứng minh nó chặn được lỗi thật của model.
- Hướng cải thiện: thêm claim hidden có nhãn, chạy với model thật, kiểm định thống kê giữa các shape, phân loại lỗi swarm theo MAST.

## 8. Tài liệu tham khảo

- `docs/architecture.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/metrics.md` của đề bài.
- Google Research, 2026, *Towards a Science of Scaling Agent Systems* (qua thư viện tham khảo ở slide 68–69; nhóm chưa đọc lại bài gốc).
- Số liệu: `src/reports/benchmark.json`, `crash.json`, `hidden_selfcheck.json`, `bonus_public.json`, `bonus_adversarial.json`.
