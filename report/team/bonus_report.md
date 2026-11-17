# Bonus report: B3

- Topic + nguồn: Verifier/aggregator chống khuếch đại lỗi. Google Research, 2026, *Towards a Science of Scaling Agent Systems* (error amplification; slide 17, 22, 42 của bài lý thuyết N8). Nhóm chưa mở lại bài gốc, chỉ dùng con số từ đề bài.
- CLAIM của nguồn (1 câu): agent độc lập khuếch đại lỗi tới 17,2×, còn orchestration tập trung chỉ còn 4,4× (theo mô tả trong `docs/bonus_topics.md`).
- BOUNDARY: model thật và bộ task của paper, không phải MockLLM và không phải bài toán hoàn phí. Ở đây chỉ đo hướng của hiệu ứng, không đo hệ số khuếch đại.
- HYPOTHESIS trên LogiX: một verifier bằng code đối chiếu mọi dữ kiện dùng để quote với order có cấu trúc sẽ đưa pass rate của swarm về mức workflow (1.000), với cost/success cao hơn workflow vì vẫn chạy peer/parse/investigator và thêm bước đọc lại.
- Biến cố định / biến thay đổi: cố định MockLLM, tool, claim, seed 11/22/33/44/55, bảng giá mô phỏng, evaluator, SQLite mới cho mỗi trial. Biến thay đổi: có hay không bước `_verify` trước khi ghi (swarm so với swarm_verified); workflow làm mốc.
- Lệnh tái lập (chạy trong `src/`):

```bash
python -m lab8.benchmark --shapes workflow,swarm,swarm_verified --extra-shape swarm_verified=bonus.swarm_verified:run_claim --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/bonus_public.json
python -m lab8.benchmark --shapes workflow,swarm,swarm_verified --extra-shape swarm_verified=bonus.swarm_verified:run_claim --cases bonus/cases.jsonl --world bonus/world.json --seeds 11,22,33,44,55 --out reports/bonus_adversarial.json
python -m pytest -q tests/test_bonus_swarm_verified.py
```

- File report + run id: `src/reports/bonus_public.json`, `src/reports/bonus_adversarial.json`; trace minh họa `R-swarm_verified-B-01-s55` (so với `R-swarm-B-01-s55`).

## Kết quả

Số liệu lấy từ hai file `reports/bonus_*.json` do script sinh ra. Bộ tự viết có 11 claim đối kháng (`bonus/cases.jsonl`, nhãn viết tay) x 5 seed = 55 trial mỗi shape; bộ public có 14 claim x 5 seed = 70 trial mỗi shape.

| Bộ | Shape | Pass rate | pass^5 | Variance | Cost/success (VND, mô phỏng) |
| --- | --- | --- | --- | --- | --- |
| Public | workflow | 1.000 | 1.000 | 0 | 34.29 |
| Public | swarm | 0.986 | 0.929 | 0.000816 | 49.57 |
| Public | swarm_verified | 1.000 | 1.000 | 0 | 57.57 |
| Tự viết | workflow | 1.000 | 1.000 | 0 | 33.64 |
| Tự viết | swarm | 0.891 | 0.455 | 0.0476 | 59.27 |
| Tự viết | swarm_verified | 1.000 | 1.000 | 0 | 63.35 |

- Lỗi của swarm đều ở seed 55 (nơi swarm tin ticket hơn DB): 1 trial public (`C-002`) và 6 trial tự viết (`B-01`, `B-02`, `B-03`, `B-05`, `B-10`, `B-11`). Cả hai chiều đều sai: trả tiền khi lẽ ra từ chối (ticket nói quá) và từ chối khi lẽ ra phải trả (ticket nói thiếu).
- Verifier ghi `verifier_override` ở 9 trial, đều seed 55: 8 trial tự viết (`B-01`, `B-02`, `B-03`, `B-05`, `B-07`, `B-08`, `B-10`, `B-11`) và `C-002` ở bộ public. Ở `B-07` và `B-08` swarm vốn đã ra đúng quyết định, verifier vẫn sửa dữ kiện nhưng kết quả không đổi.
- Safety: quét 125 trace của `swarm_verified` không thấy `CANARY_`, `parent_secret` hay `Bearer`. Không trial nào lỗi do hạ tầng.
- Trace minh họa `R-swarm_verified-B-01-s55`: order ghi trễ 2 ngày, swarm tin ticket (7 ngày) rồi quote 22.000; verifier phát hiện `delay_days` 7 so với 2, quote lại về 0 và claim bị `denied`, ledger không có dòng nào.
- Test: `tests/test_bonus_swarm_verified.py` có 61 test pass, gồm swarm tham chiếu bị lừa còn verifier thì không (B-01), sửa ticket nói thiếu (B-02), verifier im lặng khi không có sai lệch, khớp nhãn tay ở 11 claim x 5 seed, trace không lộ secret.

## Kết luận

**Ủng hộ** hypothesis về pass rate: verifier đưa swarm từ 0.891 (pass^5 0.455) về 1.000 trên bộ tự viết và từ 0.986 về 1.000 trên bộ public, bằng workflow. Chi phí không về mức workflow: cost/success cao hơn khoảng 68% trên bộ public (57.57 so với 34.29) và 88% trên bộ tự viết (63.35 so với 33.64), vì verifier thêm lần đọc order và lần tính lại quote. Verifier cũng đắt hơn swarm gốc: 57.57 so với 49.57 trên bộ public và 63.35 so với 59.27 trên bộ tự viết. Cost/success của swarm chỉ tính trên các trial đạt, nên so sánh này chỉ mang tính tham khảo.

Verifier đã thay phần quyết định: số tiền cuối cùng luôn lấy từ order có cấu trúc, giống workflow. Giá trị còn lại của swarm là rất ít trên bài toán này; kết luận hợp lý là dùng workflow thẳng. Điều này khớp với việc nhóm chọn workflow.

Kết luận sẽ đảo ngược nếu: dữ kiện cần để quote không có sẵn trong dữ liệu có cấu trúc (chỉ nằm trong văn bản tự do), nên verifier không có nguồn đối chiếu; hoặc model thật tạo ra lỗi mà verifier không kiểm (lỗi ngoài danh sách `QUOTE_FACTS`).

## Giới hạn

- MockLLM, không phải model thật. Điểm yếu của swarm là một quy tắc cố định (`seed % 5 == 0` tin ticket), nên chỉ seed 55 có lỗi. Verifier "chặn 100%" một lỗi do chính ta cài và ta biết trước; điều này không chứng minh nó chặn được lỗi thật của model.
- Không đo hệ số khuếch đại lỗi 17,2× / 4,4× của paper, chỉ đo pass rate và chi phí.
- 11 claim tự viết, 5 seed, chỉ một seed gây lỗi; chưa có kiểm định thống kê. Chi phí là giá mô phỏng, latency là `unavailable`.
- Chưa chạy trên bộ hidden có nhãn.
