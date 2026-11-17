# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape swarm --claim C-002 --seed 55
python -m lab9.trace_case --shape fixed --claim C-002 --seed 55   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case của nhóm: swarm C-002@55

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55`, baseline `E-swarm-20261117-fb7b` (`reports/baseline_v1.json`, item E-002, seed 55). Đây là trial duy nhất fail trong 70 trial của swarm. |
| Triệu chứng | Grader Lab 8 FAIL `status resolved != denied`. `refund_vnd` ledger = 20.000, label = 0; `refund_count` ledger = 1, label = 0. `RefundAmountCorrect` và `DbFactKept` đều báo lỗi; `ApprovalBypass` không báo vì label của C-002 có `approval_ok: true`. Trace của swarm không có event `reply`. |
| Bước sai đầu tiên | Event 3, `model_override`: `{"delay_days": 5}`. |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` và event 2 `investigator` đúng: DB trả order O-202 với `delay_days = 2`, `shipping_fee_vnd = 20000`. Ticket C-002 viết "Đơn giao trễ 5 ngày". Event 3 ghi đè 2 bằng 5 lấy từ ticket; event 4 `quote` chỉ ra 20.000đ (`SHIP-LATE-03`, `entitled`) vì số ngày đã bị sửa. Ledger sai là hệ quả của event 3, không phải của event 4. |
| Failure mode | FM-03 `ticket_trust` (`docs/failure_taxonomy.md`). |
| Đối chứng | `fixed C-002@55`: không có `model_override`; event 3 `quote` = 0 (`no_entitlement`, `clause_ids: []`); event 4 `reply` báo chưa đủ điều kiện; ledger 0; status `denied`; grader Lab 8 PASS. |
| Regression test | `tests/test_lab9_trace_case.py`: `test_ticket_trust_c002_seed55_first_wrong_step_is_model_override` (event 3 là `model_override {"delay_days": 5}`, `DbFactKept` và `RefundAmountCorrect` đều False, ledger 20.000), `test_fixed_control_same_claim_and_seed_is_clean` (cùng claim và seed trên `fixed` đều True), `test_ticket_trust_c002_other_seed_is_clean` (seed 11 không lỗi). Cả 3 test pass; trial lỗi bị bắt trên swarm và trial đối chứng pass trên `fixed`. Trial cũng là item E-002 của eval set với `provenance.from_trace = R-swarm-C-002-s55`. |
| Chưa chắc chắn | Trace không cho thấy vì sao agent chọn số ngày của ticket; chỉ thấy kết quả là event `model_override`. Việc lỗi chỉ xảy ra ở seed chia hết cho 5 là điều thấy trên 5 seed (11, 22, 33, 44 sạch, 55 lỗi), chưa chứng minh cho seed khác. Chưa biết ngưỡng chính xác của điều kiện kích hoạt trong mã swarm. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
