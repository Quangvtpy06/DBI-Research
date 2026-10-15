# Thí điểm trích xuất bằng chứng theo trụ cột DBI

Đã đọc 1,878 đơn vị tài liệu; trích 2,489 ứng viên, 2,453 cụm quote/chỉ tiêu chính xác. Mẫu duyệt 163 dòng.

Khung 5 trụ cột là đề xuất pilot, chưa phải chuẩn DBI chính thức. Mỗi dòng là ứng viên chưa được con người xác nhận. Số dòng/cụm không phải điểm hoặc mức trưởng thành. Một quote có thể khớp nhiều chỉ tiêu.

| Đơn vị | P1 | P2 | P3 | P4 | P5 |
|---|---:|---:|---:|---:|---:|
| ZaloPay | 20 | 17 | 47 | 0 | 51 |
| VPBank | 48 | 59 | 64 | 28 | 88 |
| VCB | 14 | 26 | 45 | 10 | 62 |
| HDBank | 40 | 39 | 54 | 25 | 65 |
| ACB | 34 | 42 | 34 | 11 | 66 |
| VNG | 27 | 74 | 35 | 5 | 29 |

Bảng đếm số đơn vị tài liệu có ứng viên ở từng trụ cột. Với báo cáo, đơn vị kỹ thuật là trang; các trang cùng báo cáo không độc lập. Với review là mẫu tối đa 100 review/ứng dụng, cân bằng luân phiên platform/rating; không đại diện tỷ lệ khách hàng.

## Đọc kết quả

- evidence_candidates.csv: quote, nguồn, URL/trang, trạng thái, chủ thể, chỉ tiêu, số liệu nguyên văn và cờ cần duyệt. numbers_raw chưa được chuẩn hóa và không được tự dùng làm KPI.
- source_documents.csv: văn bản nguồn chuẩn hóa khoảng trắng để đối chiếu quote; pdf_page tính từ 1. date_or_period là ngày đăng hoặc kỳ báo cáo, chưa phải ngày sự kiện.
- annotation_sample.csv: duyệt accept/reject/unclear, sửa chủ thể/trạng thái/chỉ tiêu; nên có người thứ hai kiểm tra độc lập.
- pillar_coverage.csv: độ phủ ứng viên, không phải xếp hạng. VNG giữ riêng; chỉ gắn ZaloPay khi quote nêu rõ.

## Kết luận thí điểm

Có thể tiếp tục xây bộ trích xuất và bộ nhãn chuẩn. Chưa đủ điều kiện tổng hợp DBI: cần chốt taxonomy với chuyên gia, đo precision/recall trên tập độc lập (có cả đoạn không được trích), kiểm tra đúng chủ thể và thời gian, tách kế hoạch/kết quả, kiểm tra OCR/PDF, chuẩn hóa KPI và gom sự kiện giữa nguồn. Không biến không có ứng viên thành điểm 0. Sentiment chỉ mô tả giọng điệu, không xác nhận năng lực hay tính đúng của tuyên bố.

Các cờ multiple_entities, subject_not_explicit, group_not_zalopay và long_or_ocr_segment cần ưu tiên duyệt. reported_result/ reported_deployment vẫn là điều tài liệu tuyên bố; chưa chứng minh độc lập. Câu có cả kế hoạch và kết quả được giữ mixed_plan_and_actual thay vì chấm là thành tựu.

Không tự mở rộng crawl hoặc ghi đè sentiment/pilot cũ. Nguồn 2 chỉ sử dụng các bài thành công trong pilot 250 bài.

## Danh sách ưu tiên và phát hiện

review_shortlist.csv có 659 dòng ưu tiên duyệt sau khi loại một số cờ rủi ro và gộp trùng chính xác. Đây vẫn là ứng viên, không phải bằng chứng được chấp nhận. Mẫu annotation_sample.csv có 163 dòng; chạy verify_pillar_evidence.py để tạo thêm negative_control_sample.csv rà soát bỏ sót.

Nguồn đầu vào thực tế: 233 bài nguồn 2 đạt kiểm tra; 14 bài nguồn 1 có content (3 dòng còn lại không có content nên không dùng tiêu đề thay toàn văn); 721 trang BCTN không rỗng và 410 trang BCTC; 500 review (100/ứng dụng). Không phải 1.878 tài liệu độc lập vì báo cáo được chia trang.

Pilot chưa tìm thấy ứng viên P4 gắn rõ với ZaloPay. Các bằng chứng VNG không tự bù cho khoảng trống này; cần đọc bổ sung/chỉnh quy tắc và kiểm định trước khi kết luận.

Ví dụ ứng viên từ nguồn 2 (chưa xác minh sự thật hoặc kỳ KPI): ACB nêu hơn 1.000 nhân sự công nghệ, khoảng 8% lao động; HDBank nêu hơn 97% giao dịch cá nhân trên nền tảng số; ZaloPay nêu phục vụ trên 16 triệu người dùng. Xem quote, URL và date_or_period trong evidence_candidates.csv trước khi sử dụng. Những tỷ lệ khác nhau giữa bài và báo cáo có thể khác kỳ/phạm vi, cần chuẩn hóa thay vì tự chọn số lớn nhất.