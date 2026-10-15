# Kết quả mô-đun sentiment

Đã xử lý **116,072** đơn vị văn bản; xuất 95,382 câu/đoạn có từ khóa hoặc bằng chứng cảm xúc.

Đơn vị: review và bài báo; báo cáo dùng trang có câu liên quan. Không so sánh trực tiếp số đếm giữa các loại nguồn. Nhãn Neutral gồm cả trường hợp không có bằng chứng; cột no_evidence tách riêng trường hợp này.

| Đơn vị | Nguồn | N | Tích cực | Trung lập | Tiêu cực | Phủ từ điển % | Chỉ tiêu |
|---|---|---:|---:|---:|---:|---:|---|
| ACB | annual_report | 42 | 9 | 30 | 3 | 30.95 | NSI=0.1429 |
| ACB | app_review | 4184 | 1589 | 1247 | 1348 | 71.87 | NSI=0.0576 |
| ACB | financial_report | 4 | 0 | 4 | 0 | 0.0 | NSI=0.0 |
| ACB | press_crawl_1 | 1 | 1 | 0 | 0 | 100.0 | NSI=1.0 |
| ACB | press_crawl_2 | 47 | 38 | 6 | 3 | 89.36 | NSI=0.7447 |
| HDBank | annual_report | 56 | 32 | 23 | 1 | 58.93 | NSI=0.5536 |
| HDBank | app_review | 1744 | 587 | 638 | 519 | 63.93 | NSI=0.039 |
| HDBank | financial_report | 1 | 0 | 1 | 0 | 0.0 | NSI=0.0 |
| HDBank | press_crawl_1 | 4 | 4 | 0 | 0 | 100.0 | NSI=1.0 |
| HDBank | press_crawl_2 | 47 | 44 | 2 | 1 | 95.74 | NSI=0.9149 |
| VCB | annual_report | 36 | 15 | 19 | 2 | 50.0 | NSI=0.3611 |
| VCB | app_review | 15687 | 6138 | 5263 | 4286 | 67.57 | NSI=0.1181 |
| VCB | press_crawl_1 | 2 | 2 | 0 | 0 | 100.0 | NSI=1.0 |
| VCB | press_crawl_2 | 48 | 34 | 10 | 4 | 85.42 | NSI=0.625 |
| VNG | annual_report | 63 | 7 | 56 | 0 | 11.11 | NSI=0.1111 |
| VNG | financial_report | 9 | 0 | 9 | 0 | 0.0 | NSI=0.0 |
| VNG | press_crawl_2 | 45 | 35 | 7 | 3 | 91.11 | NSI=0.7111 |
| VPBank | annual_report | 57 | 22 | 33 | 2 | 42.11 | NSI=0.3509 |
| VPBank | app_review | 5292 | 1947 | 1983 | 1362 | 64.21 | NSI=0.1105 |
| VPBank | financial_report | 8 | 0 | 8 | 0 | 0.0 | NSI=0.0 |
| VPBank | press_crawl_1 | 7 | 5 | 1 | 1 | 85.71 | NSI=0.5714 |
| VPBank | press_crawl_2 | 46 | 43 | 2 | 1 | 95.65 | NSI=0.913 |
| ZaloPay | app_review | 88639 | 59485 | 26552 | 2602 | 70.39 | NSI=0.6417 |
| ZaloPay | press_crawl_1 | 3 | 2 | 1 | 0 | 66.67 | NSI=0.6667 |

## Đánh giá khả năng tiếp tục DBI

Có thể bắt đầu thiết kế và thí điểm trích xuất bằng chứng trên sentences.csv (có doc_id, trang, topic và văn bản gốc). Chưa đủ điều kiện công bố điểm/xếp hạng DBI:

- Sentiment là baseline từ điển, chưa có kiểm định độc lập. Gán nhãn annotation_sample.csv bởi hai người; tính đồng thuận trước hòa giải và Macro-F1 sau khi chốt gold. Mẫu phân tầng không đại diện tỷ lệ tự nhiên; khi ước lượng chỉ số toàn kho cần trọng số lấy mẫu hoặc test đại diện riêng.
- Không dùng sao làm gold: star_disagreement chỉ là tín hiệu rà soát. Không lấy điểm sentiment làm mức trưởng thành số.
- Tin nguồn 2 có nhiều bản ghi chỉ có tiêu đề: xem title_only trong summary.csv; không suy diễn nội dung chưa crawl.
- Cần gom các tin cùng sự kiện, xác nhận thực thể trong bài nhiều ngân hàng, kiểm tra ngày sự kiện và tách kế hoạch/đã triển khai/kết quả.
- Báo cáo thuộc ngân hàng/tập đoàn, review thuộc sản phẩm. VNG giữ riêng với ZaloPay; không tự quy dữ liệu toàn VNG thành năng lực ZaloPay.
- Topic là gợi ý regex, chưa phải năm trụ cột đã kiểm định. Câu không có sentiment vẫn có thể chứa bằng chứng năng lực số.
- OCR có thể sai dấu, bảng có thể mất cấu trúc; kiểm tra PDF gốc trước khi trích số. Trang là đơn vị kỹ thuật, không phải bằng chứng độc lập.
- IDF được tính trên kho đầu vào hiện tại cho mô tả; khi đánh giá holdout phải fit IDF/từ điển/ngưỡng trên train và cố định cho test. Delta=0.1 hiện là giả định, chưa được tối ưu.

## Tệp đầu ra

documents.csv: mọi văn bản được chấm; sentences.csv: câu/đoạn có tín hiệu; summary.csv: tổng hợp; review_queue.csv: nhãn hỗn hợp/bất đồng; annotation_sample.csv: mẫu gán nhãn; metadata.json: cấu hình và kiểm kê đầu vào.