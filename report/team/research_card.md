# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R1 · Scaling |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Google Research, 2026, *Towards a Science of Scaling Agent Systems* (thư viện tham khảo, slide 68–69; URL lấy từ slide, nhóm chưa mở lại bài gốc). Loại bằng chứng: benchmark. |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Thêm agent chỉ có lợi khi task chia được thành các phần độc lập chạy song song; với task tuần tự, thêm agent làm tăng chi phí phối hợp và không cải thiện kết quả. (Nhóm diễn đạt lại theo phần thuyết trình ở slide; chưa đối chiếu từng câu với bài gốc.) |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Kết luận của paper dựa trên model thật và các bộ task của paper, không phải MockLLM và không phải bài toán hoàn phí. Ở đây chỉ kiểm chứng hướng của hiệu ứng trên 14 claim public, 5 seed, MockLLM. |
| HYPOTHESIS | Nếu đổi shape A->B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Claim hoàn phí gần như tuần tự (kiểm sở hữu -> chọn policy -> tính tiền -> gọi host; bước quote phụ thuộc `lookup_order`). Đổi shape A (workflow) -> C (orchestrator + investigator) thì pass rate gần như không đổi (cùng 1.0), còn cost/success tăng khoảng 50–70% và số tool call tăng vì thêm handoff và các lần đọc không cần thiết. |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Cố định: MockLLM, bộ tool, 14 claim public, seed 11/22/33/44/55, bảng giá mô phỏng (20/80 VND mỗi 1k token, 10 VND mỗi tool call), evaluator và SQLite mới cho mỗi trial. Biến duy nhất thay đổi: shape (workflow -> orchestrator); tiền luôn do `compute_compensation` tính ở cả hai. |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: orchestrator tốn hơn mà không đúng hơn (chi phí phối hợp). Đo bằng cost/success, mean tool calls, pass rate, pass^5 và variance giữa seed. |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json` (chạy trong `src/`; benchmark này được chạy trước khi viết phiếu, nên phiếu đọc lại kết quả của nó chứ không chạy lại một ablation riêng).
- Run id / file report: `src/reports/benchmark.json` (ví dụ `R-workflow-C-001-s11`, `R-orchestrator-C-001-s11`).
- Kết quả so với hypothesis: **đúng**. Workflow và orchestrator đều pass rate 1.000, pass^5 1.000, variance 0. Cost/success: workflow 34.29 VND, orchestrator 56.65 VND (+65%). Mean tool calls: 3.43 so với 5.57. Orchestrator tốn hơn mà không đúng hơn trên bài toán tuần tự này. Số bước ít hơn (2.79 so với 3.50) nhưng có thêm 1 lần gọi model (workflow 0), nên tổng chi phí vẫn cao hơn.
- Ngoài phạm vi hypothesis: swarm duy nhất có trial fail (`R-swarm-C-002-s55`, pass rate 0.986, pass^5 0.929). Nhóm chưa phân loại lỗi này theo MAST nên không đưa vào kết luận.
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Bộ public 14 claim đều đạt 1.0 ở ba shape nên pass rate không phân biệt được các shape; chênh lệch duy nhất là chi phí. Chưa kiểm chứng trên bộ hidden có nhãn.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
