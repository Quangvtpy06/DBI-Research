# Thử nghiệm bổ sung toàn văn nguồn 2

Kết quả cuối sau QA và sửa selector: **233/250 bản ghi đạt cổng tự động (93,2%)**. Các trường hợp chưa đạt: 9 quá ngắn/rỗng, 6 HTTP lỗi, 1 chuyển về trang chủ, 1 không có alias đơn vị trong nội dung. Không có lỗi giải mã Google News trong lượt thử này.

Đã kiểm tra đủ 250 ID duy nhất, đúng 50 bài/đơn vị; 6/6 unit tests đạt; bước analyze.py chạy thành công và lưu riêng trong analyzed/. Đã đọc kiểm tra đầu/cuối của mẫu 3 bài/đơn vị, đồng thời rà soát các trường hợp không có alias. Kiểm tra này phát hiện trích lẫn tin liên quan ở Báo Đầu Tư/Bnews/Thời báo Ngân hàng; đã bổ sung selector riêng, tải lại các bài bị ảnh hưởng và kiểm tra lại vùng bài chính. Đây không phải kiểm định thủ công toàn bộ 250 bài.

Trong 233 bản ghi đạt: có 231 nội dung khác nhau theo hash chính xác, còn 69 bản ghi không khớp bộ gợi ý số hóa trong quality_audit.csv. Không diễn giải số 69 là kết luận chắc chắn bài không liên quan: regex còn có thể bỏ sót. Cần lọc chủ đề/thực thể và gom bài trùng trước khi đưa vào DBI; không dùng toàn bộ 233 bài như 233 bằng chứng độc lập. Nguồn RSS gồm cả website tổng hợp/mạng xã hội, không phải tất cả là cơ quan báo chí.

| Đơn vị | Bài thử | Số nguồn báo | Đạt cổng toàn văn | Tỷ lệ % |
|---|---:|---:|---:|---:|
| ACB | 50 | 50 | 47 | 94.0 |
| HDB | 50 | 50 | 47 | 94.0 |
| VCB | 50 | 50 | 48 | 96.0 |
| VNG | 50 | 43 | 45 | 90.0 |
| VPB | 50 | 50 | 46 | 92.0 |

Mẫu luân phiên theo tên nguồn báo, seed cố định; không phải mẫu ngẫu nhiên đại diện toàn kho. VNG là tập đoàn, chưa đồng nhất ZaloPay. Thành công nghĩa là qua cổng độ dài, có alias thực thể và không phải trang chủ; chưa chứng minh bài đúng chủ đề DBI hoặc không lẫn nội dung thừa. Kiểm tra URL và nội dung trước khi đưa vào DBI.

Các tệp: enriched_news.csv (checkpoint từng bài), failed_news.csv, summary.csv, by_source.csv, metadata.json. Chạy lại cùng lệnh sẽ tiếp tục phần chưa chạy; --retry-failed để thử lại bài lỗi. Không sửa raw_news.csv/clean_news.csv cũ.
