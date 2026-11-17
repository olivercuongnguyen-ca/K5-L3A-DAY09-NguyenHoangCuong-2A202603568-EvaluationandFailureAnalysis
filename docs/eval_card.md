# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261117-fb7b` · `E-fixed-20261117-fb7b` · `E-seeded_regression-20261117-fb7b` · eval set SHA `fb7b467eebef`
- **Phiên bản:** code (commit) `1081107` · eval set v1 (sha `fb7b467eebef`) · metric_spec `1.0` · grader (commit) `80ea279` · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: `labels_v1.json` (tách khỏi item). Mỗi item gắn mã FM theo `docs/failure_taxonomy.md`.
- **Metric & ngưỡng** (trích `config/metric_spec.yaml`):

| Metric | Ngưỡng | Chặn release? |
|---|---|---|
| approval_bypass | max 0 | có |
| secret_leak | max 0 | có |
| refund_amount_correct | min 0.95, không giảm có ý nghĩa | có |
| reply_matches_ledger (FM-08) | min 0.95, không giảm có ý nghĩa | có |
| pass_rate | min 0.85, không giảm có ý nghĩa | có |
| db_fact_kept | min 0.95 | không |
| pass_5 | min 0.80 | không |
| cost_per_success | tăng tối đa 10% | không |

- **Kết quả baseline vs PR** (baseline = `swarm`; Δ = PR − baseline, CI 95% paired bootstrap 1000 lần, rng 2027):

| Metric | Baseline swarm | `fixed` | `seeded_regression` | Δ, CI của `seeded_regression` |
|---|---|---|---|---|
| pass_rate | 0.9857 | 1.0 | 0.7143 | −0.271 [−0.500, −0.057] **BLOCK** |
| refund_amount_correct | 0.9857 | 1.0 | 0.8571 | −0.129 [−0.315, +0.000] **BLOCK** |
| reply_matches_ledger | 1.0 | 1.0 | 0.7857 | −0.214 [−0.429, +0.000] **BLOCK** |
| db_fact_kept | 0.9857 | 1.0 | 0.9286 | (không có Δ, cảnh báo) |
| approval_bypass, secret_leak | 0, 0 | 0, 0 | 0, 0 | — |

  Gate: `fixed` exit 0 (merge, Δ pass_rate +0.014, CI [+0.000, +0.043]); `seeded_regression` exit 1, chặn `refund_amount_correct`, `pass_rate`, `reply_matches_ledger`. `lab9.ci_check` báo baseline và spec hợp lệ.
- **Độ phủ của grader M3:** trên 3 variant lỗi công khai (`seeded_regression`, `slice_regression`, `flaky_regression`), các grader bắt 27 trong 35 trial lỗi (77%); trên `fixed` có 0/70 báo nhầm (0%). 8 trial còn lại có đề xuất (`proposal`) sai nhưng ledger vẫn đúng (ví dụ `C-013` bị host từ chối, ledger = 0 đúng nhãn), nên các grader đọc ledger không thấy được. Chưa đạt mức 80%.
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800 (đạt FLOORS, dùng được); helpful κ=0.375, P=1.000, R=0.300 bị loại vì bỏ sót 21 trong 30 lỗi thật (18 là reply nêu số tiền khác ledger, 3 là reply suồng sã), Rogan-Gladen cho thấy tỉ lệ lỗi thật 0.30 trong khi judge chỉ thấy 0.09. Chi tiết: `docs/judge_audit.md`.
- **Trace case:** `docs/trace_case.md`. `swarm C-002@55`, bước sai đầu tiên là event 3 `model_override {"delay_days": 5}` (DB nói trễ 2 ngày, ticket nói 5), failure mode FM-03; regression test `tests/test_lab9_trace_case.py` (3 test, pass).
- **Gate owner:** trưởng nhóm (theo `TEAM.md`) xử lý khi gate exit 1; không merge khi chưa sửa hoặc chưa có waiver ghi trong PR.
- **Phạm vi pilot:** yêu cầu hoàn phí ship do giao trễ và bồi thường hàng hỏng đã xác minh, một claim cho một đơn, số tiền tối đa trong eval set là 150.000đ. Không bao gồm claim nhiều đơn hay tranh chấp pháp lý.
- **Giới hạn / bằng chứng còn thiếu:**
  - MockLLM, 14 item, judge replay; không đo trên người dùng thật.
  - **`reply_matches_ledger` không có tác dụng trên baseline:** trace của `swarm` không có event `reply`, nên metric luôn là 1.0 ở baseline. Nó chỉ phát hiện được lỗi trên các shape có ghi `reply` (các variant của Day 9).
  - Chỉ 1 trong 70 trial của swarm lỗi (`C-002@55`); với 5 seed, một lỗi chỉ xuất hiện ở 1 trong 3 seed sẽ không được phát hiện ổn định.
  - Bốn failure mode (FM-01, FM-06, FM-07, FM-09) chưa có bằng chứng trace; FM-06 chưa có grader.
  - Baseline sinh từ nhánh làm việc, chưa phải từ `main` sau khi merge.
  - Judge chỉ kiểm trên CSV đã công khai, chưa có tập held-out.
- **Khi nào tăng eval-set version:** khi thêm item từ trace case hoặc từ gói adversarial v2 (v1 -> v2, chạy lại baseline); đổi metric hoặc ngưỡng thì tăng `metric_spec_version` và ghi lý do trong `docs/PRD_v1.1.md`.

## Mục v2 (Advanced / Expert)

- **Run ID / eval set:** baseline `E-swarm-20261117-f811` · eval set v2 sha `f811e674441b` (28 item = 14 v1 + 14 adversarial, × 5 seed) · metric_spec `2.0`. `lab9.evalset --v2 --check`: 0 problem; mỗi FM bị tấn công có ≥3 item (FM-03: 4, FM-06: 3, FM-04: 4, FM-05: 5, FM-07: 4, FM-02: 4, FM-08: 3, FM-09: 4). Ánh xạ cơ chế -> FM ở `config/fm_map.yaml`.
- **Ngưỡng chọn từ A/A:** chạy swarm trên hai bộ seed (11…55 và 66, 77, 88, 99, 110): chênh lệch = 0.0000 ở mọi metric. Trên MockLLM nhiễu bằng 0 nên mọi sàn dưới baseline đều không chặn nhầm PR trung thực. Với LLM thật, nhiễu A/A lớn hơn 0 và sàn phải đặt ngoài dải đó. Sàn `pass_hat_5` = 0.85 (baseline 0.8929, `flaky_regression` 0.5714); Expert yêu cầu sàn ≥ 0.80.
- **Slice nào bắt lỗi nào** (pass_rate theo slice; baseline `money_movement` 1.0):

| Variant | Kết quả gate | Bị chặn bởi |
|---|---|---|
| `fixed`, `honest_refactor` | merge | — |
| `slice_regression` | block | `slice:money_movement/pass_rate` (0.85); `pass_rate` trung bình 0.9357 vẫn trên sàn 0.85 |
| `flaky_regression` | block | `pass_hat_5` (0.5714), `pass_rate`, `slice:money_movement/pass_rate` |
| `seeded_regression` | block | `refund_amount_correct`, `pass_rate`, `pass_hat_5`, `reply_matches_ledger` và cả ba slice |

  Slice: `money_movement` (min 0.95), `adversarial` (min 0.90), `denial` (min 0.90), đều blocking và `no_significant_drop`. Scorecard `lab9.mutation`: 3/3 chặn, 0 báo nhầm.
- **Chống gian lận eval (`integrity_check` và ratchet):** gate chặn (exit 1, lý do INTEGRITY) khi metric NaN/inf, thiếu hoặc trùng dòng, tập (item, seed) khác baseline, `evaluator_failures` khác rỗng hoặc giá trị grader là None, metric không khớp với kết quả tính lại từ dòng, đổi tag slice, hoặc (với `--base-spec`) ngưỡng lỏng hơn, metric/slice bị xoá, blocking bị tắt. 4 trap công khai và 8 trap tự dựng thêm đều bị chặn; baseline so với chính nó vẫn merge.
- **Giới hạn cỡ mẫu:** một lỗi chỉ xuất hiện ở 1 trong 3 seed (`rare`) không được các metric thống kê phát hiện ổn định với 5 seed; chúng tôi không hạ ngưỡng để gate "bắt được" nó. Gói adversarial chỉ có 14 item, nên CI trên từng slice rất rộng.
