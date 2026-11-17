# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: f882a82
- Run id dẫn chứng: R-workflow-C-001-s11 (toàn bộ 70 trial: `src/reports/benchmark.json`)
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000-1.000 / 0.000000 (public, 14 claim x 5 seed)
- Cost per success (mô phỏng, VND): 34.29
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Nhóm chọn `workflow`. Trên cùng 14 claim public, cùng 5 seed (11, 22, 33, 44, 55) và cùng bảng giá mô phỏng, ba shape nhóm viết đều đạt pass rate 1.000, pass^5 1.000 và variance 0, nên độ đúng không phân biệt được chúng. Chi phí thì có: `workflow` 34.29 VND/success (0 model call, 3.5 step), `single` 38.73, `orchestrator` 56.65, `swarm` 49.57. `swarm` còn đạt 0.986 / pass^5 0.929 vì ở seed 55 nó tin số ngày trong ticket thay vì cột `delay_days`. Luật nghiệp vụ của bài là quy trình cố định (kiểm sở hữu, chọn policy hiện hành, tính tiền, gọi host), nên chọn shape ít tự chủ nhất vẫn làm đủ việc.

| Shape | Pass rate | pass^5 | Variance | Cost/success (VND) | Mean steps |
| --- | --- | --- | --- | --- | --- |
| workflow | 1.000 | 1.000 | 0 | 34.29 | 3.50 |
| single | 1.000 | 1.000 | 0 | 38.73 | 4.64 |
| orchestrator | 1.000 | 1.000 | 0 | 56.65 | 2.79 |
| swarm | 0.986 | 0.929 | 0.000816 | 49.57 | 2.80 |

## Có đáng đổi lấy multi-agent không

Không, trên bộ public. Multi-agent (`orchestrator`, `swarm`) không đạt pass cao hơn mà tốn thêm chi phí (56.65 và 49.57 so với 34.29), và `swarm` còn có variance giữa các seed. Quyết định sẽ đảo lại nếu: (1) trên bộ hidden `workflow` thấp hơn rõ rệt (dưới ngưỡng 0.75) ở nhóm claim mà ticket mơ hồ hoặc cần đọc hiểu ngôn ngữ tự do; (2) bài toán có phần đọc độc lập thật sự song song, khi đó critical path của `orchestrator` có thể có lợi; (3) dùng model thật, vì MockLLM không phản ánh độ dao động và lỗi của model sản xuất.

## Trace và bằng chứng

Trace của `workflow` ghi các event: `claim_read` (chỉ `found`, `claim_id`, `has_order_id`), `order_lookup` (chỉ `visible` và `reason`), `quote` (số tiền, lý do, clause), `refund_result` (`ok`, `reason`, `conflict`), `decision` (status khi thiếu order id), `error` (chỉ mã lý do) và `crash` (chỉ tên điểm crash). Cố ý **không** ghi: claim row nguyên bản (có `ticket` và `parent_secret`), order row (kể cả các field trong allowlist, vì không cần), SĐT, địa chỉ, tên hàng, ghi chú nội bộ, header. `workflow` không có handoff hay investigator nên không có event tương ứng. Lý do: grader quét trace để tìm secret và PII, nên trace là một phần của ranh giới bảo mật. Mọi nhánh return (`needs_info`, `escalated`, `denied`, `failed`, `resolved`) đều ghi trace trong chính lần chạy qua `finish()`. Bằng chứng: quét `CANARY_SECRET`, `parent_secret`, `raw_headers` trên `src/traces` (280 file) và `src/reports` cho kết quả rỗng; `grep print(` trên ba file shape không có kết quả; shape không ghi file nào ngoài `traces/<run_id>*`.

## Giới hạn

MockLLM không phải model sản xuất. Latency để `unavailable`. Không sửa JSON cho đủ 0.75. Số liệu trong file này lấy từ bộ public (14 claim x 5 seed), nơi cả ba shape đều đạt 1.000 nên khả năng phân biệt thấp. Cost là chi phí mô phỏng theo `config/pricing.yaml`, không phải hóa đơn API.
