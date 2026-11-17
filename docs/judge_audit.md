# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

Dương tính = FAIL (judge có nhiệm vụ tìm lỗi). Dữ liệu: replay, n = 100 mỗi tiêu chí; chạy bằng `lab9.judge` sau khi cài `stats.py` (test `confusion`, `precision_recall`, `cohen_kappa`, `rogan_gladen` xanh).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt cả 3 (tp 24, fp 4, fn 6, tn 66) | **Dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt** κ và recall (tp 9, fp 0, fn 21, tn 70) | **Loại** |

Hiệu chỉnh Rogan-Gladen (tỉ lệ lỗi thật ≈ 0.30 ở cả hai tiêu chí):
- tone_ok: quan sát 0.28 → hiệu chỉnh 0.30 (judge đo gần đúng).
- helpful: quan sát **0.09** → hiệu chỉnh **0.30**. Judge báo thấp gần gấp ba lần tỉ lệ lỗi thật.

## ≥5 case audit thủ công (tone_ok)
Cột "Người nói" là nhãn trong CSV; ghi chú lấy từ cột `note` của CSV, kết hợp đọc lại reply.

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" và "nha" quá suồng sã với khách; judge coi là thân thiện. **Rubric:** cấm xưng "em/bạn" và đuôi "nha/nhé" với khách; "thân thiện" không bao gồm suồng sã. |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | Người | Xưng "bạn" với khách lớn tuổi. **Rubric:** cùng điều khoản như #1; thêm ví dụ FAIL có "Dạ" ở đầu nhưng vẫn suồng sã (judge bị "Dạ" đánh lạc hướng). |
| 3 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh ("không cần nhắn thêm"); judge chỉ thấy "Dạ, vui lòng". **Rubric:** chấm cả câu, không chấm theo từ khóa lịch sự; câu cấm/ra lệnh khách là FAIL. |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì "thiếu xin lỗi". **Rubric:** lời xin lỗi chỉ bắt buộc khi từ chối hoặc có lỗi/trễ, không bắt buộc khi hoàn tiền thành công. |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | Từ "refund" được CS LogiX cho phép; judge phạt vì tiếng Anh. **Rubric:** thêm danh sách từ vay được phép (refund); chỉ phạt tiếng Anh khi gây khó hiểu. |
| 6 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Cột note của CSV ghi: nhãn người sai do đọc nhầm ticket, judge đúng, sửa nhãn. **Hành động:** sửa nhãn người thành FAIL. Đây là lỗi nhãn, không phải lỗi rubric, nên không đổi rubric. |
| 7 | H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa "sẽ hoàn thêm" ngoài kết quả hệ thống. Đây là lỗi cam kết sai, không hẳn là giọng điệu. **Rubric:** tách khỏi tone_ok; số tiền và cam kết kiểm bằng code (xem FM-08). |

Tổng kết 10 bất đồng của tone_ok: judge bỏ sót 6 lỗi (fn: giọng suồng sã, ra lệnh, emoji, dịch máy, hứa thêm) và báo nhầm 4 (fp: phạt thiếu xin lỗi, từ "refund", lặp "Dạ", và H-081 mà case này nhãn người sai nên judge thật ra đúng).

## Kết luận
- **Dùng `tone_ok`** làm judge: κ = 0.757, P = 0.857, R = 0.800, cả ba đạt ngưỡng. Vẫn cần sửa rubric theo các hành động ở bảng (xưng hô, giọng ra lệnh, điều kiện xin lỗi, từ vay) vì 10/100 mẫu còn bất đồng.
- **Loại `helpful`** (không dùng làm gate): recall chỉ 0.300, κ = 0.375 (ma trận: bỏ sót 21 trong 30 lỗi thật, fn = 21, fp = 0). Precision 1.000 không cứu được: judge không bao giờ báo nhầm nhưng bỏ sót 70% lỗi, nên một lần PASS không có nghĩa là reply tốt. Rogan-Gladen cho thấy tỉ lệ lỗi thật 0.30 trong khi judge chỉ thấy 0.09.
- **Nguyên nhân bỏ sót của `helpful`:** trong 21 lỗi bị judge cho PASS, 18 là reply nêu số tiền khác ledger (ghi chú "ledger ghi …"), 3 là reply quá suồng sã ("Ok bạn … nhé"). Số tiền là thứ phải chấm bằng code, không bằng judge; đây chính là FM-08 (`misreport`).
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. Nhãn người cũng có thể sai (H-081).
