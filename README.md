# DBI Research — Đánh giá mức sẵn sàng chuyển đổi số

DBI Research là dự án nghiên cứu cá nhân sử dụng phân tích văn bản công khai để xây dựng điểm sẵn sàng chuyển đổi số và so sánh năm công ty: **VNG (VNZ, bao gồm ZaloPay), VPBank, Vietcombank (VCB), HDBank và ACB**.

Hệ thống thu thập dữ liệu, phân tích sắc thái, nhận diện tín hiệu theo bốn trụ cột, tính điểm tổng hợp và hiển thị kết quả bằng **Streamlit**. Mục đích là hỗ trợ nghiên cứu và trình bày một phương pháp có thể chạy lại; đây không phải xếp hạng chính thức hoặc xác nhận năng lực nội bộ của doanh nghiệp.

## Chức năng

- Bảng xếp hạng và biểu đồ nhiệt trên thang 100.
- Điểm thành phần và đóng góp theo trọng số của từng công ty.
- Độ phủ chỉ tiêu, nhóm nguồn dữ liệu và các đoạn văn dùng để tính điểm.
- Lọc đoạn trích theo công ty, trụ cột, từ khóa; tải CSV, PNG và SVG.
- Giải thích dữ liệu, công thức, phân mức và hạn chế bằng tiếng Việt.
- Chạy lại pipeline từ app hoặc dòng lệnh; lưu checkpoint và nhật ký xử lý.

## Dữ liệu sử dụng

| Nguồn | Nội dung và vai trò |
|---|---|
| Google Play và Apple App Store | Review ứng dụng để đánh giá sắc thái trải nghiệm khách hàng; chỉ tham gia trụ cột Khách hàng. |
| Báo cáo thường niên, báo cáo tài chính công khai | Văn bản về công nghệ, dữ liệu, định hướng và nguồn lực số; giữ trang PDF để truy vết. |
| Báo chí và sự kiện — bộ crawl 1 | Các bài có nội dung thu thập được từ nguồn công khai. |
| Google News RSS — bộ crawl 2 | Danh sách tin, giải mã URL báo gốc và bổ sung toàn văn trước khi sử dụng. |

Dữ liệu hiện có chủ yếu trong giai đoạn 2025–2026. Ngày/kỳ cụ thể được giữ ở từng bản ghi. Nguồn 2 mặc định đang sử dụng phạm vi pilot **50 bài/đơn vị**, chỉ những bài đạt kiểm tra mới được đưa vào bước trích bằng chứng. Không coi tiêu đề là toàn văn. Các trang PDF dạng ảnh cần được kiểm tra OCR; phần tải báo cáo không bảo đảm tự đọc được mọi PDF scan.

VNG là đơn vị được xếp hạng, ZaloPay nằm trong phạm vi VNG. Review ZaloPay chỉ phản ánh sản phẩm này, không đại diện tất cả sản phẩm của tập đoàn.

## Phương pháp tính điểm

### Bốn trụ cột

| Trụ cột | Trọng số | Nội dung |
|---|---:|---|
| Công nghệ | 40% | Hạ tầng, kết nối hệ thống, an toàn và xác thực |
| Khách hàng | 20% | Trải nghiệm, hỗ trợ và tiếp cận dịch vụ số |
| Dữ liệu | 30% | Nền tảng, quản trị và ứng dụng dữ liệu/AI |
| Chiến lược | 10% | Định hướng, quản trị chuyển đổi số và nguồn lực |

Mỗi trụ cột được quy đổi về **0–100**, không phải 20 điểm như các phiên bản thử nghiệm trước. Trụ cột Vận hành đã được bỏ khỏi mô hình xếp hạng hiện hành.

### Từ sắc thái đến điểm

Với P, N là số lần khớp cụm từ cảm xúc tích cực và tiêu cực sau xử lý phủ định:

```text
Tone = (P − N) / (P + N)
Điểm nguồn = 50 × (1 + Tone trung bình)
```

Hệ thống khớp cụm dài nhất, giữ ngữ cảnh phủ định và phân biệt cảnh báo/phòng chống với sự cố xảy ra. Đoạn không có tín hiệu cảm xúc không tự nhận điểm trung lập. Số sao review được giữ để đối chiếu, không thay thế đánh giá nội dung.

Các tín hiệu được trung bình theo tài liệu → nhóm nguồn → chỉ tiêu → trụ cột. Những trang cùng báo cáo được gộp thành một tài liệu. Hai bộ crawl báo chí thuộc cùng một nhóm nguồn khi tính điểm. Chỉ dùng các ô chỉ tiêu/nguồn có dữ liệu ở cả năm công ty, với cùng trọng số; không ưu tiên công ty có nhiều bài hơn.

Đoạn trùng chính xác và một số đoạn gần trùng bị loại. Thông tin có số liệu mới được giữ riêng. Mỗi đoạn chỉ đóng góp vào một chỉ tiêu/trụ cột; bộ lọc chưa bảo đảm nhận diện hoàn toàn mọi bài cùng sự kiện. Độ phủ và các tín hiệu được giữ có thể xem trong app.

### Điểm sẵn sàng R

```text
R = (40 × Công nghệ + 20 × Khách hàng + 30 × Dữ liệu + 10 × Chiến lược) / 100
```

Đây là trung bình có trọng số, **không chia thêm cho 4**. Xếp hạng giảm dần theo R. Nếu thiếu dữ liệu chung cho cả một trụ cột, hệ thống không tự gán 0 hoặc thay tỷ trọng để tính tổng.

| Mức | Phân loại | Ngưỡng điểm R |
|---|---|---|
| 1 | Cơ bản | 0 ≤ R < 25 |
| 2 | Đang phát triển | 25 ≤ R < 50 |
| 3 | Phát triển | 50 ≤ R < 75 |
| 4 | Nâng cao | 75 ≤ R < 100 |
| 5 | Dẫn đầu | R = 100 chính xác |

Phân mức dùng số chưa làm tròn. Các mức là quy ước của dự án; không ép năm công ty vào năm mức khác nhau.

## Cài đặt

Khuyến nghị **Python 3.12**. `requirements.txt` chỉ chứa các phụ thuộc chạy app, pipeline và crawler; không cần Playwright, pytest, vnstock hay thư viện kiểm thử. Các phụ thuộc gián tiếp được pip cài tự động.

Mở PowerShell tại thư mục `Digital_Bank_Ranking_DBI`:

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Nếu đã có môi trường PyCharm được cấu hình, dùng Python của môi trường đó thay cho đường dẫn `.venv` trong các lệnh. Môi trường hiện tại của workspace nằm ở thư mục cha: `..\.venv\Scripts\python.exe`. Không cần tạo lại môi trường nếu đã cài đủ thư viện.

## Chạy ứng dụng

Từ thư mục dự án:

```powershell
& '.\.venv\Scripts\python.exe' -m streamlit run app.py
```

Hoặc dùng script tiện ích, tự tìm `.venv` ở thư mục dự án rồi đến thư mục cha:

```powershell
.\run_app.ps1
```

Mở **http://127.0.0.1:8501**. Dừng ứng dụng bằng `Ctrl+C` trong terminal đã chạy. Nếu đã có app chạy ở cổng 8501, dùng cửa sổ đó hoặc chỉ định một cổng khác bằng `--server.port 8502`.

Khi dữ liệu và kết quả đã có trong `output/`, app mở trực tiếp. Nếu chưa có kết quả công bố, chạy pipeline trước hoặc dùng nút tính điểm lần đầu trong app. App không tự có sẵn dữ liệu nếu chỉ sao chép mã nguồn mà không sao chép thư mục dữ liệu.

## Chạy pipeline

Các lệnh dưới dùng môi trường `.venv` trong dự án; thay bằng môi trường PyCharm nếu cần.

```powershell
# Xử lý lại dữ liệu hiện có; không crawl mới
& '.\.venv\Scripts\python.exe' run_pipeline.py

# Tải thêm toàn văn từ danh sách nguồn 2 hiện có
& '.\.venv\Scripts\python.exe' run_pipeline.py --enrich-source2 --per-company 50

# Crawl mới review, tin, báo cáo và nguồn 2 rồi xử lý
& '.\.venv\Scripts\python.exe' run_pipeline.py --refresh --per-company 50

# Dùng lại sentiment đã có để chạy các bước sau
& '.\.venv\Scripts\python.exe' run_pipeline.py --skip-sentiment
```

Luồng: **làm sạch nguồn 2 → sentiment → ứng viên bằng chứng → kiểm tra truy vết → gán bốn trụ cột → loại trùng → tính R → heatmap → công bố kết quả cho app**. Khi dùng `--refresh`, các bước thu thập được chạy trước luồng này.

Tải mới cần mạng và có thể mất nhiều thời gian. Muốn xử lý toàn bộ danh sách nguồn 2, tăng `--per-company`, ví dụ `100000`. Không bảo đảm mọi website cho tải nội dung; lỗi từng bài được lưu để kiểm tra. Nếu bắt đầu từ mã nguồn thuần, cần chạy chế độ thu thập hoặc cung cấp bộ dữ liệu theo cấu trúc bên dưới trước khi chạy chế độ mặc định.

Pipeline lưu log từng bước và dừng nếu một bước lỗi. App giữ bản kết quả công bố thành công gần nhất khi tính lại. `output/.pipeline.lock` ngăn hai lượt chạy đồng thời; nếu bị tắt cưỡng bức, chỉ xóa tệp khóa sau khi xác nhận tiến trình cũ đã dừng.

## Cấu trúc dự án

```text
app.py                              Giao diện Streamlit
run_pipeline.py                     Điều phối các bước xử lý
run_app.ps1                         Mở app trên Windows
requirements.txt                    Thư viện cần cài
dbi_public_text_config.json          Từ khóa và cấu hình gán trụ cột
report_sources.json                 Danh mục báo cáo công khai
crawl_app_reviews.py                Thu thập review
crawl_press_events.py               Thu thập tin nguồn 1
Crawl_Annual_Report_5_company.py     Tải và trích văn bản báo cáo
crawl_events_company_p2/bank_project/
  collect.py                        Thu thập RSS nguồn 2
  enrich_fulltext.py                 Bổ sung toàn văn và checkpoint
  analyze.py                         Làm sạch nguồn 2
sentiment_module.py                 Phân tích sắc thái
analyze_text_mining.py               Bộ nhận diện chủ đề được sentiment sử dụng
extract_pillar_evidence.py           Trích ứng viên và lưu tài liệu truy vết
verify_pillar_evidence.py            Kiểm tra dữ liệu trong pipeline, không phải file test
evidence_taxonomy.json              Cấu hình mô-đun ứng viên bằng chứng
score_dbi_public_text.py             Bộ tổng hợp tín hiệu dùng bởi mô hình hiện hành
score_dbi_four_pillars.py            Tính R, phân mức và xuất heatmap
.streamlit/config.toml              Theme sáng và cấu hình app
```

Mô-đun ứng viên bằng chứng còn lưu taxonomy thí điểm để truy vết; bảng R và app dùng mô hình bốn trụ cột trong `score_dbi_four_pillars.py`, không dùng bảng năm trụ cột cũ.

```text
output/
  raw/          Dữ liệu review, tin và báo cáo nguồn
  processed/    Toàn văn, sentiment, ứng viên bằng chứng
  results/      ranking.csv, pillar_scores.csv, method.json, heatmap và diagnostics
  published/    Snapshot thành công; current.json trỏ bản app đang đọc
  logs/         Nhật ký từng bước
  pipeline_status.json
```

Toàn bộ `output/` là dữ liệu sinh khi chạy và được bỏ qua trong Git. Khi chia sẻ dự án kèm dữ liệu, cần chuyển thư mục này riêng. Không xóa `output/raw/` nếu muốn tính lại mà không crawl. Không xóa `output/processed/press_2_fulltext/` nếu muốn giữ nội dung đã tải và checkpoint. Dữ liệu cũ được giữ để đối chiếu khi chưa xác định chắc có thể bỏ.

## Hạn chế

- Điểm đo sắc thái thông tin quan sát, chưa xác nhận năng lực số thực tế hoặc chất lượng nội bộ.
- Báo cáo doanh nghiệp và tin quảng bá thường tích cực, khiến một số trụ cột chạm trần; điểm 100 không có nghĩa hoàn thiện.
- Review là mẫu tự chọn, không đại diện ngẫu nhiên cho toàn bộ khách hàng; mức độ thu thập giữa nền tảng và thời gian có thể khác nhau.
- Chỉ dùng dữ liệu chung giúp thống nhất trọng số nhưng có thể làm giảm số chỉ tiêu được đánh giá.
- Từ điển, regex, OCR và gán chủ thể có thể sai hoặc bỏ sót; ngày đăng không nhất thiết là ngày sự kiện.
- Chưa có đo lường độc lập về độ chính xác, khoảng tin cậy hoặc độ ổn định thứ hạng. Chênh lệch nhỏ chưa chứng minh khác biệt đáng kể.
- VNG và các ngân hàng khác loại hình hoạt động; cần nêu rõ phạm vi mẫu khi kết luận.

File `Công_thức_định_lượng_Chuyển_đổi_số.md` được giữ làm tài liệu nền. Cấu hình công thức và ngưỡng của lần chạy hiện hành nằm trong `output/results/method.json`.
