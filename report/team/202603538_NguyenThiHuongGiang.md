# BÁO CÁO CÁ NHÂN – VINUXI CODELAB DAY 08

## 1. Thông tin cá nhân

- **Họ và tên:** Nguyễn Thị Hương Giang
- **MSSV:** 2A202603538
- **Email:** 26ai.giangnth3@vinuni.edu.vn
- **GitHub:** https://github.com/nthgiang311
- **Repository nhóm:** https://github.com/olivercuongnguyen-ca/K5-L3A-DAY08-Something-FromWorkflowsToAgents
- **Branch cá nhân:** `giang`

## 2. Phần việc được phân công

Tôi phụ trách **Shape A – Deterministic Workflow**, tập trung xây dựng luồng xử lý yêu cầu hoàn tiền theo hướng xác định, trong đó các bước nghiệp vụ được thực hiện theo trình tự cố định thay vì để LLM tự quyết định toàn bộ quá trình.

Các nhiệm vụ chính:

- Xây dựng luồng xử lý claim từ bước đọc thông tin đến tra cứu đơn hàng và tính toán khoản bồi thường.
- Xử lý các trạng thái nghiệp vụ như `needs_info`, `escalated`, `denied`, `resolved` và `failed`.
- Tích hợp thao tác hoàn tiền với durability layer.
- Xử lý tình huống crash và đảm bảo workflow có thể tiếp tục mà không tạo thêm hiệu ứng hoàn tiền ngoài ý muốn.
- Viết kiểm thử riêng cho phần workflow, đồng thời bổ sung một test thực tế theo yêu cầu C8.

## 3. Các nội dung đã thực hiện

### 3.1. CP2 – Xây dựng Deterministic Workflow

**File thực hiện:** `src/lab8/shapes/workflow.py`

Tôi triển khai hàm `run_claim()` để điều phối quá trình xử lý một claim theo trình tự:

1. Đọc thông tin claim bằng `get_claim_view()`.
2. Kiểm tra claim có tồn tại và có đủ thông tin đơn hàng hay không.
3. Tra cứu đơn hàng bằng `lookup_order()`.
4. Kiểm tra quyền truy cập và khả năng nhìn thấy đơn hàng.
5. Tính toán khoản bồi thường bằng `compute_compensation()`.
6. Kiểm tra số tiền đề xuất và thực hiện hoàn tiền thông qua `issue_refund()`.
7. Trả về kết quả xử lý cùng trace tương ứng.

Tôi thiết kế các nhánh xử lý theo trạng thái nghiệp vụ:

| Trường hợp | Kết quả |
|---|---|
| Claim không tồn tại | `failed` |
| Thiếu thông tin đơn hàng | `needs_info` |
| Không thể truy cập đơn hàng | `escalated` |
| Khoản bồi thường bằng 0 | `denied` |
| Hoàn tiền thành công | `resolved` |
| Hoàn tiền gặp lỗi hoặc conflict | `failed` |

**Một số quyết định kỹ thuật:**

- Sử dụng logic tính toán bồi thường có tính xác định thay vì yêu cầu LLM tự đưa ra số tiền.
- Lấy dữ liệu đơn hàng từ kết quả tra cứu, không tự suy diễn thông tin nghiệp vụ từ nội dung claim.
- Giao việc kiểm tra giới hạn, quyền thực hiện và ghi nhận giao dịch cho các thành phần tương ứng của hệ thống.
- Ghi trace theo từng bước để có thể theo dõi quá trình xử lý, đồng thời hạn chế đưa thông tin nhạy cảm vào trace.

**Commit:** `51db0c9` – Implement deterministic workflow shape.

### 3.2. CP3 – Xử lý Crash Recovery

**File thực hiện:** `src/lab8/shapes/workflow.py`

Tôi tiếp tục hoàn thiện workflow để hỗ trợ kiểm thử các tình huống crash trong quá trình thực hiện hoàn tiền.

Các thay đổi chính:

- Bổ sung tham số `crash_at` vào luồng xử lý.
- Truyền `crash_at` xuống `issue_refund()` để mô phỏng các điểm crash.
- Không bắt và nuốt ngoại lệ `InjectedCrash`, để cơ chế kiểm thử và durability layer có thể nhận biết đúng tình huống crash.
- Giữ nguyên trình tự nghiệp vụ của workflow đã xây dựng ở CP2.

Điểm quan trọng là workflow chịu trách nhiệm điều phối nghiệp vụ, còn việc đảm bảo tính an toàn khi retry và xử lý giao dịch được giao cho durability layer. Vì vậy, tôi không tự triển khai một cơ chế idempotency riêng trong workflow.

**Commit:** `abcfc5b` – Implement workflow crash recovery.

### 3.3. C8 – Bổ sung kiểm thử hành vi thực tế

**File kiểm thử:** `src/tests/test_202603404_workflow_unknown_claim.py`

Tôi bổ sung test `test_workflow_unknown_claim_does_not_create_refund()` để kiểm tra hành vi của workflow khi nhận một claim không tồn tại.

Test thực hiện các kiểm tra:

- Workflow trả về trạng thái `failed`.
- `error_reason` là `unknown_claim`.
- Số tiền đề xuất bằng 0.
- Không có refund effect được tạo ra.
- Không có audit record hoàn tiền được ghi nhận.

Test này kiểm tra hành vi thực tế của workflow thay vì chỉ kiểm tra một điều kiện hình thức.

**Commit:** `93c0930` – Add workflow unknown claim test.

## 4. Kết quả kiểm thử

### 4.1. Kiểm thử workflow

Sau khi hoàn thiện phần workflow và crash recovery, tôi chạy:

```powershell
python -m pytest -q -m student -o addopts= -k workflow
```

Kết quả:

```text
62 passed, 240 deselected
```

### 4.2. Kiểm thử C8

Chạy riêng test đã bổ sung:

```powershell
python -m pytest -q tests/test_202603404_workflow_unknown_claim.py
```

Kết quả:

```text
1 passed
```

### 4.3. Kiểm thử toàn bộ test suite

Sau khi tích hợp các thay đổi, tôi chạy:

```powershell
python -m pytest -q
```

Kết quả:

```text
55 passed, 248 deselected
```

Kết quả cho thấy các test được thực thi trong lần chạy này đều thành công.

## 5. Hidden benchmark – Kết quả tự kiểm

Tôi giải nén dữ liệu hidden benchmark vào `src/student_drop/` và chạy benchmark cho ba kiến trúc `workflow`, `single` và `orchestrator`.

Lệnh thực hiện:

```powershell
python -m lab8.benchmark --shapes workflow,single,orchestrator --cases student_drop/hidden_claims.jsonl --world student_drop/hidden_world_state.json --out reports/hidden_selfcheck.json
```

Do bộ dữ liệu được cung cấp không có nhãn, benchmark không thể tính pass rate hoặc xác định độ chính xác chính thức. Vì vậy, tôi chỉ sử dụng kết quả để quan sát khả năng xử lý, trạng thái trả về và các chỉ số vận hành.

| Chỉ số | Workflow | Single | Orchestrator |
|---|---:|---:|---:|
| Số trials | 200 | 200 | 200 |
| Mean steps | 3.55 | 4.825 | 2.90 |
| Mean model calls | 0 | 4.825 | 1 |
| Mean tool calls | 3.525 | 3.825 | 5.825 |
| Tổng simulated cost (VND) | 7,050 | 8,131 | 11,836.5 |
| Error trials | 0 | 0 | 0 |
| Leak suspect trials | 0 | 0 | 0 |

Phân bố trạng thái của cả ba kiến trúc:

| Trạng thái | Số lượng |
|---|---:|
| `denied` | 95 |
| `resolved` | 90 |
| `needs_info` | 5 |
| `escalated` | 10 |

**Nhận xét:**

- Workflow không sử dụng model calls trong lần tự kiểm này và có tổng simulated cost thấp nhất trong ba kiến trúc.
- Orchestrator có mean steps thấp nhất nhưng số tool calls và simulated cost cao nhất.
- Single có số model calls trung bình cao nhất.
- Cả ba kiến trúc có cùng phân bố trạng thái trong bộ dữ liệu này.
- Không ghi nhận error trials hoặc leak suspect trials trong báo cáo benchmark.

Đây chỉ là kết quả tự kiểm trên dữ liệu không nhãn. Các chỉ số trên không thể thay thế pass rate hoặc kết quả đánh giá chính thức của giảng viên. Simulated cost cũng không phải chi phí API thực tế.

## 6. Công cụ và cách thức thực hiện

- **Python:** triển khai workflow và kiểm thử.
- **Pytest:** chạy test riêng cho workflow và toàn bộ test suite.
- **Git/GitHub:** quản lý branch, commit và đồng bộ thay đổi với repository nhóm.
- **ChatGPT:** hỗ trợ phân tích yêu cầu bài lab, rà soát logic workflow, giải thích cơ chế crash recovery và hỗ trợ thiết kế test case.

Các thay đổi trong repository được tôi trực tiếp kiểm tra bằng cách đọc code, chạy test và đối chiếu kết quả thực tế trước khi commit.

## 7. Tự đánh giá và bài học rút ra

Qua phần việc được giao, tôi hiểu rõ hơn sự khác biệt giữa việc xây dựng một luồng xử lý nghiệp vụ và việc đảm bảo tính an toàn của các thao tác có tác động lên hệ thống.

Một số bài học chính:

- Một workflow xác định cần kiểm soát rõ thứ tự thực hiện và điều kiện chuyển trạng thái, thay vì phụ thuộc vào quyết định tự do của LLM.
- Không nên để một thành phần đảm nhiệm tất cả trách nhiệm. Workflow điều phối nghiệp vụ, trong khi durability layer xử lý các vấn đề liên quan đến giao dịch, retry và idempotency.
- Crash recovery không chỉ là bắt ngoại lệ. Cần hiểu trạng thái của hệ thống tại thời điểm xảy ra crash và cách tiếp tục xử lý mà không tạo ra hiệu ứng trùng lặp.
- Kiểm thử cần tập trung vào hành vi và tác động thực tế, chẳng hạn một claim không tồn tại không được tạo refund hoặc audit record.
- Kết quả benchmark cần được diễn giải đúng theo dữ liệu đầu vào. Với dữ liệu không nhãn, không thể kết luận kiến trúc nào có độ chính xác cao hơn chỉ dựa trên phân bố trạng thái.

Qua bài lab, tôi có thêm kinh nghiệm triển khai workflow bằng Python, đọc và sử dụng các thành phần có sẵn trong một codebase, viết test bằng pytest và quản lý thay đổi bằng Git.

## 8. Minh chứng đóng góp

| Nội dung | Minh chứng |
|---|---|
| CP2 – Deterministic Workflow | Commit `51db0c9` |
| CP3 – Crash Recovery | Commit `abcfc5b` |
| C8 – Workflow test | Commit `93c0930` |
| Code triển khai | `src/lab8/shapes/workflow.py` |
| Test bổ sung | `src/tests/test_202603404_workflow_unknown_claim.py` |
| Kết quả kiểm thử | `62 passed` cho workflow; `55 passed` cho toàn bộ test suite |
| Hidden benchmark | `src/reports/hidden_selfcheck.json` (kết quả tự kiểm, không nhãn) |



