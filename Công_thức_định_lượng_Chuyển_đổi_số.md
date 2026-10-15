# **Bộ công thức cho Đề án 5**

## Phân tích và phân loại tích cực – tiêu cực của văn bản chủ đề “Chuyển đổi số”

# **Ghi chú về nguồn và phạm vi**

Bản này viết lại từ bộ công thức cũ (phân tích văn bản báo cáo tài chính). Dữ liệu đầu vào mới là văn bản thuần về chuyển đổi số (tin tức, báo cáo, bài đăng, văn bản chính sách…), **không có dữ liệu giá hay lợi suất**. Vì vậy phần nghiên cứu sự kiện và các hồi quy trên lợi suất đã được bỏ. Thước đo độ đúng của phân loại bây giờ là **nhãn do con người gán**, không phải phản ứng của thị trường.

**Nguồn của các công thức:**

* Giữ lại từ bộ cũ: phủ định (Jegadeesh & Wu, mục 3), tone tỷ lệ (Loughran & McDonald, 2011, qua cách trình bày của Jegadeesh & Wu), tf.idf và Word Power (Jegadeesh & Wu, 2013), kiểm định dấu (MacKinlay, 1997), sai số chuẩn bền (White, 1980).

* Công thức mới thêm vào là công thức chuẩn của xử lý ngôn ngữ tự nhiên và thống kê, **không nằm trong bốn tài liệu gốc**. Khi đưa vào báo cáo cần trích nguồn: Turney (2002) cho SO-PMI; Monroe, Colaresi & Quinn (2008) cho log-odds có tiên nghiệm; Hutto & Gilbert (2014) cho cách tính điểm có cường độ; Cohen (1960) cho hệ số κ; McNemar (1947); Kruskal & Wallis (1952).

**Ký hiệu ưu tiên:**

| Ký hiệu | Ý nghĩa |
| :---- | :---- |
| **\[B\]** | Bắt buộc |
| **\[N\]** | Nên có (kiểm định độ vững) |
| **\[M\]** | Mở rộng |

## **Đối chiếu với bộ công thức cũ**

| Mục cũ | Xử lý | Lý do |
| :---- | :---- | :---- |
| A1 Phủ định | Giữ, mở rộng cho tiếng Việt (A4 mới) | Tiếng Việt có các cụm như “không ngừng”, “không thể thiếu” không phải phủ định |
| A2 Tone tỷ lệ | Giữ (C1) | Là phương pháp cơ sở |
| A3 tf.idf | Giữ (C2) | Dùng để so sánh với tone tỷ lệ |
| A4 Word Power | Chuyển thể (E1) | Thay lợi suất bằng nhãn con người gán |
| B1–B8 Nghiên cứu sự kiện | **Bỏ** | Cần giá cổ phiếu, lợi suất, VN-Index |
| C1–C3, C6 Hồi quy tone lên lợi suất | **Bỏ** | Biến phụ thuộc là lợi suất |
| C4 LM so với Harvard | Chuyển thể (F5) | So từ điển tổng quát với từ điển chủ đề bằng nhãn con người |
| C5 Yếu tố quyết định tone | Chuyển thể (G3) | Bỏ Size, BM, Accruals…; thay bằng thời gian, nguồn, độ dài |
| C7 Hồi quy cắt ngang, sai số White | Giữ ý tưởng ở G3 | Vẫn cần sai số chuẩn bền |
| C8 Fama–MacBeth | **Bỏ** | Dành cho panel hồi quy lợi suất theo năm |

# **PHẦN A. Chuẩn bị văn bản**

## **A1. Làm sạch văn bản \[B\]**

* Chuẩn hóa Unicode về dạng NFC (tiếng Việt có thể gặp dấu viết dạng tổ hợp và dựng sẵn, hai dạng này làm từ điển so khớp sai).

* Xóa mã HTML, đường dẫn, ký tự điều khiển; đưa về chữ thường; tách câu theo dấu chấm, chấm hỏi, chấm than và xuống dòng.

* **Không** loại bỏ stopword một cách máy móc, vì các từ phủ định và từ tăng cường (“không”, “rất”) mang thông tin cảm xúc.

## **A2. Tách từ tiếng Việt \[B\]**

Từ điển cảm xúc tiếng Việt gồm nhiều từ ghép (“rủi\_ro”, “an\_ninh\_mạng”, “chuyển\_đổi\_số”), nên phải tách từ trước khi đếm. Công cụ thường dùng: VnCoreNLP, underthesea, pyvi. Sau bước này, văn bản $i$ là chuỗi ${a}_{i}$ token ${w}_{i,1},\ldots ,{w}_{i,{a}_{i}}$.

## **A3. Nhận diện văn bản thuộc chủ đề \[B\]**

Gọi $D$ là tập từ khóa chủ đề (ví dụ: chuyển đổi số, số hóa, trí tuệ nhân tạo, điện toán đám mây, dữ liệu lớn, chính phủ số, kinh tế số). Mật độ chủ đề của văn bản $i$:

$${Rel}_{i}=\frac{\sum\limits_{d\in D}^{}{F}_{i,d}}{{a}_{i}}$$

Giữ văn bản nếu $\sum\limits_{d\in D}^{}{F}_{i,d}\geq m$ (gợi ý $m=3$) hoặc ${Rel}_{i}\geq \rho$. Ngưỡng $m$ và $\rho$ do nhóm chọn và nêu rõ trong báo cáo.

## **A4. Xử lý phủ định \[B\]**

Theo Jegadeesh & Wu: không đếm từ cảm xúc nếu có từ phủ định trong khoảng 3 token đứng trước, và không để cửa sổ này vượt qua ranh giới câu.

* Từ phủ định: *không, chưa, chẳng, chả, không hề, chưa hề, chưa từng*.

* **Ngoại lệ** (không tính là phủ định): *không chỉ, không những, chẳng những, không ngừng, không thể thiếu*. Ví dụ “không ngừng đổi mới” mang nghĩa tích cực.

Đặt ${\nu }_{i,k}=1$ nếu token thứ $k$ của văn bản $i$ bị phủ định theo quy tắc trên, ngược lại ${\nu }_{i,k}=0$. Tần suất hiệu chỉnh của từ $j$:

$${F}_{i,j}^{eff}=\sum\limits_{k=1}^{{a}_{i}}1\left[{{w}_{i,k}=j}\right]\left({1-{\nu }_{i,k}}\right)$$

# **PHẦN B. Xây dựng từ điển cảm xúc cho chủ đề Chuyển đổi số**

Đây là phần thay cho việc dùng từ điển tài chính của LM. Cùng lý do với bản cũ: từ điển tổng quát dễ phân loại sai trong ngữ cảnh chuyên ngành.

## **B1. Từ điển hạt giống (seed) \[B\]**

Lập ba danh sách: ${S}^{+}$ (tích cực), ${S}^{-}$ (tiêu cực), và danh sách **từ nhập nhằng** cần loại hoặc xử lý riêng. Hai người độc lập rà soát từng từ. Gợi ý khởi đầu (cần kiểm tra lại trên dữ liệu thật):

| Tích cực | Tiêu cực | Nhập nhằng (cần xử lý theo ngữ cảnh) |
| :---- | :---- | :---- |
| hiệu quả, tối ưu, đột phá, thuận tiện, minh bạch, tiên phong, tăng trưởng, đổi mới, tiết kiệm | rủi ro, chậm trễ, lãng phí, rò rỉ, tấn công mạng, thiếu hụt, lạc hậu, thất bại, gián đoạn, quá tải, manh mún | thách thức, thay thế, cắt giảm, tự động hóa, áp lực, thay đổi |

Với từ nhập nhằng, có hai cách: loại khỏi từ điển, hoặc đưa vào dưới dạng cụm (n-gram) có nghĩa rõ ràng. Ví dụ, “cơ hội và thách thức” là cụm trung lập mang tính khuôn mẫu, không nên tính “thách thức” như từ tiêu cực.

## **B2. Mở rộng từ điển bằng SO-PMI \[N\]**

(Turney, 2002.) Đo mức độ đồng xuất hiện của từ ứng viên $j$ với các từ hạt giống trong cùng câu hoặc trong cửa sổ $\pm L$ token:

$$PMI\left({x,y}\right)={log}_{2}\frac{P\left({x,y}\right)}{P\left({x}\right) P\left({y}\right)}$$

$$SO\left({j}\right)=\sum\limits_{p\in {S}^{+}}^{}PMI\left({j,p}\right)-\sum\limits_{n\in {S}^{-}}^{}PMI\left({j,n}\right)$$

Nếu $SO\left({j}\right)>\tau$ thì đưa $j$ vào danh sách ứng viên tích cực; nếu $SO\left({j}\right)<-\tau$ thì đưa vào danh sách ứng viên tiêu cực. Chỉ xét từ xuất hiện ít nhất 5 lần để tránh PMI không ổn định. Ứng viên phải được người rà soát duyệt trước khi vào từ điển.

## **B3. Mở rộng bằng độ tương đồng vector từ (embedding) \[N\]**

Huấn luyện hoặc dùng sẵn vector từ tiếng Việt (word2vec, fastText) trên tập văn bản chuyển đổi số. Với vector ${v}_{j}$ của từ ứng viên:

$$cos\left({u,v}\right)=\frac{u\cdot v}{\parallel u\parallel  \parallel v\parallel }$$

$${S}_{j}=\frac{1}{\left|{{S}^{+}}\right|}\sum\limits_{p\in {S}^{+}}^{}cos\left({{v}_{j},{v}_{p}}\right)-\frac{1}{\left|{{S}^{-}}\right|}\sum\limits_{n\in {S}^{-}}^{}cos\left({{v}_{j},{v}_{n}}\right)$$

${S}_{j}$ dương nhiều thì thiên về tích cực, âm nhiều thì thiên về tiêu cực. Cũng cần người duyệt.

## **B4. Log-odds có tiên nghiệm Dirichlet, khi đã có văn bản gán nhãn \[N\]**

(Monroe, Colaresi & Quinn, 2008.) Tìm những từ phân biệt mạnh nhất giữa nhóm văn bản tích cực và tiêu cực. Gọi ${y}_{j}^{+}$, ${y}_{j}^{-}$ là số lần từ $j$ xuất hiện trong các văn bản nhãn tích cực và tiêu cực; ${n}^{+}=\sum\limits_{j}^{}{y}_{j}^{+}$, ${n}^{-}=\sum\limits_{j}^{}{y}_{j}^{-}$; ${\alpha }_{j}={\alpha }_{0}{f}_{j}$ với ${f}_{j}$ là tần suất tương đối của từ $j$ trong toàn bộ kho văn bản và ${\alpha }_{0}=\sum\limits_{j}^{}{\alpha }_{j}$ (chọn cố định, ví dụ 500, và kiểm tra độ vững).

$${\delta }_{j}=log\frac{{y}_{j}^{+}+{\alpha }_{j}}{{n}^{+}+{\alpha }_{0}-{y}_{j}^{+}-{\alpha }_{j}}-log\frac{{y}_{j}^{-}+{\alpha }_{j}}{{n}^{-}+{\alpha }_{0}-{y}_{j}^{-}-{\alpha }_{j}}$$

$${\sigma }^{2}\left({{\delta }_{j}}\right)\approx \frac{1}{{y}_{j}^{+}+{\alpha }_{j}}+\frac{1}{{y}_{j}^{-}+{\alpha }_{j}},  {z}_{j}=\frac{{\delta }_{j}}{\sigma \left({{\delta }_{j}}\right)}$$

Nếu ${z}_{j}>1,96$ thì từ thiên về tích cực; nếu ${z}_{j}<-1,96$ thì thiên về tiêu cực. *Lưu ý:* tập văn bản dùng để tạo từ điển không được dùng lại để đánh giá (phải tách tập huấn luyện và tập kiểm tra).

## **B5. Điểm cường độ của từ \[M\]**

Gán mỗi từ trong từ điển một điểm ${s}_{j}\in \left[{-1,1}\right]$ (trung bình điểm của các người gán nhãn; ví dụ “đột phá” $=+0,8$, “hiệu quả” $=+0,5$, “rủi ro” $=-0,6$). Với từ điển nhị phân chỉ có ${s}_{j}=\pm 1$.

# **PHẦN C. Chỉ số giọng điệu (tone) của văn bản**

## **C1. Tone theo trọng số tỷ lệ \[B\]**

Đây là phương pháp cơ sở của LM (2011), dùng tần suất đã hiệu chỉnh phủ định ở A4:

$${Neg}_{i}=\sum\limits_{j\in Neg}^{}\frac{{F}_{i,j}^{eff}}{{a}_{i}},  {Pos}_{i}=\sum\limits_{j\in Pos}^{}\frac{{F}_{i,j}^{eff}}{{a}_{i}}$$

$${Tone}_{i}=\frac{{Pos}_{i}-{Neg}_{i}}{{Pos}_{i}+{Neg}_{i}} (hoặc\ {Pos}_{i}-{Neg}_{i})$$

Trong đó ${F}_{i,j}^{eff}$ là số lần từ $j$ xuất hiện trong văn bản $i$ sau khi loại các lần bị phủ định, ${a}_{i}$ là tổng số từ của văn bản $i$.

*Lưu ý:*

* Dạng tỷ số nằm trong $\left[{-1,1}\right]$ và không phụ thuộc ${a}_{i}$ (vì ${a}_{i}$ triệt tiêu); dạng hiệu thì có phụ thuộc.

* Nếu ${Pos}_{i}+{Neg}_{i}=0$ thì tone không xác định. Quy ước gán ${Tone}_{i}=0$ (trung lập) và **báo cáo tỷ lệ văn bản rơi vào trường hợp này**.

* Công thức Tone tổng hợp ở dòng cuối là cách xây dựng phổ biến, không nằm nguyên văn trong các file. Cần nêu rõ định nghĩa trong báo cáo.

## **C2. Trọng số tf.idf \[B, để so sánh với tone tỷ lệ\]**

(J\&W, Eq. 1–3)

$${w}_{j}^{idf}=log\frac{N}{{df}_{j}}$$

$${w}_{i,j}^{tf.idf}=\{\frac{1+log{tf}_{i,j}}{1+log{a}_{i}} {w}_{j}^{idf}\ nếu\ {tf}_{i,j}>0\ 0\ ngược\ lại{\ }$$

$${Score}_{i}^{tf.idf}=\frac{1}{1+log{a}_{i}}\sum\limits_{j=1}^{J}{w}_{i,j}^{tf.idf}$$

Trong đó $N$ là tổng số văn bản trong kho chủ đề chuyển đổi số, ${df}_{j}$ là số văn bản chứa từ $j$ ít nhất một lần. Tính riêng cho danh sách từ tích cực và tiêu cực, rồi lấy hiệu (hoặc tỷ số tương tự C1) để ra điểm tổng. ${tf}_{i,j}$ dùng ${F}_{i,j}^{eff}$.

## **C3. Điểm có cường độ và từ tăng cường, giảm nhẹ \[N\]**

(Hutto & Gilbert, 2014, đơn giản hóa.) Với mỗi token $k$ trong từ điển, gọi ${s}_{k}$ là điểm cường độ (B5):

* ${m}_{k}=1,5$ nếu ngay trước đó là từ tăng cường (*rất, cực kỳ, vô cùng, hết sức, đặc biệt*); ${m}_{k}=0,5$ nếu là từ giảm nhẹ (*hơi, tương đối, phần nào, một chút*); còn lại ${m}_{k}=1$.

* ${\varphi }_{k}=1$ nếu không bị phủ định. Nếu bị phủ định: ${\varphi }_{k}=0$ (quy tắc J\&W, mặc định) hoặc ${\varphi }_{k}=-\lambda$ với $\lambda \in (0,1]$ (đảo chiều có suy giảm, dùng khi muốn “không rủi ro” được tính là tích cực).

$${Tone}_{i}^{val}=\frac{\sum\limits_{k}^{}{s}_{k} {m}_{k} {\varphi }_{k}}{\sum\limits_{k}^{}\left|{{s}_{k} {m}_{k} {\varphi }_{k}}\right|}\in \left[{-1,1}\right]$$

Khi $\left|{{s}_{k}}\right|=1$, ${m}_{k}=1$ và ${\varphi }_{k}\in \{0,1\}$, công thức này trùng dạng tỷ số của C1.

## **C4. Tone cấp câu và gộp lên văn bản \[N\]**

Văn bản dài (báo cáo, văn bản chính sách) thường trộn nhiều ý nên tone cả văn bản bị trung hòa. Tính tone cho từng câu $s$ rồi gộp:

$${Tone}_{i}=\frac{1}{{S}_{i}}\sum\limits_{s=1}^{{S}_{i}}{Tone}_{i,s}$$

$${PosShare}_{i}=\frac{1}{{S}_{i}}\sum\limits_{s=1}^{{S}_{i}}1\left[{{Tone}_{i,s}>\delta }\right], {NegShare}_{i}=\frac{1}{{S}_{i}}\sum\limits_{s=1}^{{S}_{i}}1\left[{{Tone}_{i,s}<-\delta }\right]$$

$${NetShare}_{i}={PosShare}_{i}-{NegShare}_{i}$$

${S}_{i}$ là số câu của văn bản $i$; $\delta$ là ngưỡng ở D1.

## **C5. Tone gắn với chủ đề (cửa sổ lân cận từ khóa) \[N\]**

Một bài báo về kinh tế có thể nhắc “chuyển đổi số” ở một đoạn nhưng phần lớn từ cảm xúc lại nói về chủ đề khác. Để tone phản ánh đúng chủ đề, chỉ đếm từ cảm xúc nằm gần từ khóa chủ đề. Gọi ${P}_{i}$ là tập vị trí token thuộc $D$ trong văn bản $i$, và

$${C}_{i}=\left\{{k: \min\limits_{p\in {P}_{i}}\left|{k-p}\right|\leq {L}_{c}}\right\}$$

là tập vị trí “trong ngữ cảnh chủ đề” (gợi ý ${L}_{c}=10$; thử thêm 5 và 15 để kiểm tra độ vững). Hoặc đơn giản hơn: chỉ giữ câu có chứa từ khóa thuộc $D$. Tần suất hiệu chỉnh theo chủ đề:

$${F}_{i,j}^{DX}=\sum\limits_{k=1}^{{a}_{i}}1\left[{{w}_{i,k}=j}\right]\left({1-{\nu }_{i,k}}\right)1\left[{k\in {C}_{i}}\right]$$

Thay ${F}_{i,j}^{eff}$ bằng ${F}_{i,j}^{DX}$ trong C1 để có ${Tone}_{i}^{DX}$. Khi mẫu gồm toàn văn bản chuyên về chuyển đổi số, có thể bỏ qua bước này.

# **PHẦN D. Quy tắc phân loại**

## **D1. Phân loại ba lớp theo ngưỡng \[B\]**

$${\hat{y}}_{i}=\{Tích\ cực\ nếu\ {Tone}_{i}>\delta \ Tiêu\ cực\ nếu\ {Tone}_{i}<-\delta \ Trung\ lập\ nếu\ \left|{{Tone}_{i}}\right|\leq \delta {\ }$$

Cách chọn ngưỡng $\delta \geq 0$:

* $\delta =0$: mặc định, đơn giản nhất.

* ${\delta }^{*}=arg{max}_{\delta } Macro-F1\left({\delta }\right)$, tìm trên lưới $\delta \in \{0;0,05;\ldots ;0,30\}$ **chỉ trên tập huấn luyện**, rồi cố định để chạy trên tập kiểm tra \[N\].

* Phân loại tương đối \[M\]: lấy phân vị 1/3 trên là tích cực, 1/3 dưới là tiêu cực. Cách này chỉ so sánh các văn bản với nhau, không phản ánh sắc thái tuyệt đối.

## **D2. Phân loại nhị phân \[N\]**

Bỏ các văn bản trung lập hoặc không có từ cảm xúc (${Pos}_{i}+{Neg}_{i}=0$), rồi phân loại tích cực nếu ${Tone}_{i}>0$, tiêu cực nếu ${Tone}_{i}<0$. Báo cáo kèm số văn bản bị loại.

# **PHẦN E. Học máy có giám sát (so sánh và mở rộng)**

Dùng khi nhóm có đủ văn bản gán nhãn (từ vài trăm trở lên). Mục đích chính là có một mốc so sánh cho phương pháp từ điển ở Phần C.

## **E1. Word Power với nhãn thủ công \[M\]**

(Chuyển thể từ J\&W Eq. 4–8: thay lợi suất ${r}_{i}$ bằng nhãn ${y}_{i}$, ví dụ $+1,0,-1$ hoặc thang 1–5.)

$${Score}_{i}=\sum\limits_{j=1}^{J}{w}_{j} {F}_{i,j} \frac{1}{{a}_{i}}$$

Ước lượng hệ số từng từ bằng hồi quy:

$${y}_{i}=a+\sum\limits_{j=1}^{J}{B}_{j} {F}_{i,j}\frac{1}{{a}_{i}}+{\epsilon }_{i}$$

Chuẩn hóa để lấy trọng số:

$${w}_{j}=\frac{{B}_{j}-B‾}{SD\left({{B}_{j}}\right)}$$

Kiểm định sức mạnh thông tin của Score:

$${y}_{i}=a+b\sum\limits_{j}^{}{w}_{j}{F}_{i,j}\frac{1}{{a}_{i}}+{\epsilon }_{i}$$

Vì số từ $J$ thường lớn hơn số văn bản, cần hồi quy có phạt (ridge hoặc lasso) với $\lambda$ chọn bằng kiểm chứng chéo. Trọng số ${w}_{j}$ cho văn bản thuộc nhóm (fold) $k$ được ước lượng từ các nhóm còn lại, để không dùng chính văn bản đang kiểm định (tương tự quy tắc “mọi năm khác năm $T$” của bản cũ).

## **E2. Naive Bayes đa thức \[M\]**

$${\hat{y}}_{i}=arg\max\limits_{c}\left[{logP\left({c}\right)+\sum\limits_{j=1}^{J}{F}_{i,j}logP\left({j∣c}\right)}\right],  P\left({j∣c}\right)=\frac{{n}_{j,c}+1}{\sum\limits_{j′}^{}{n}_{j′,c}+J}$$

${n}_{j,c}$ là số lần từ $j$ xuất hiện trong các văn bản lớp $c$; “+1” là làm trơn Laplace.

## **E3. Hồi quy logistic trên đặc trưng tf.idf \[M\]**

Hai lớp:

$$P\left({{y}_{i}=1∣{x}_{i}}\right)=\frac{1}{1+exp\left({-\left({{w}^{\top }{x}_{i}+b}\right)}\right)}$$

$$\min\limits_{w,b} -\frac{1}{N}\sum\limits_{i=1}^{N}\left[{{y}_{i}log{p}_{i}+\left({1-{y}_{i}}\right)log\left({1-{p}_{i}}\right)}\right]+\lambda \parallel w{\parallel }^{2}$$

Ba lớp (tích cực, trung lập, tiêu cực) dùng softmax:

$$P\left({c∣{x}_{i}}\right)=\frac{exp\left({{w}_{c}^{\top }{x}_{i}+{b}_{c}}\right)}{\sum\limits_{c′}^{}exp\left({{w}_{c′}^{\top }{x}_{i}+{b}_{c′}}\right)}$$

## **E4. Mô hình ngôn ngữ tiền huấn luyện (PhoBERT) \[M\]**

Tinh chỉnh PhoBERT với đầu ra softmax trên vector ${h}_{\left[{CLS}\right]}$ của văn bản:

$$P\left({c∣{văn\ bản}_{i}}\right)=softmax{\left({W {h}_{\left[{CLS}\right]}+b}\right)}_{c}$$

Hàm mất mát là cross-entropy giống E3. Thường cho kết quả tốt nhất nhưng khó giải thích; nên dùng làm mốc tham chiếu chứ không thay thế phương pháp từ điển nếu mục tiêu là giải thích được.

# **PHẦN F. Đánh giá chất lượng phân loại**

Phần này thay cho vai trò của phản ứng thị trường trong bản cũ: mọi phương pháp ở Phần C–E đều phải được đối chiếu với nhãn do con người gán.

## **F1. Tập nhãn chuẩn (gold standard) \[B\]**

Cỡ mẫu tối thiểu để ước lượng tỷ lệ đúng với sai số $e$ và độ tin cậy 95%:

$$n=\frac{{z}^{2} p\left({1-p}\right)}{{e}^{2}}$$

Với $p=0,5$, $e=0,05$, $z=1,96$ thì $n\approx 385$ văn bản. Nên lấy mẫu phân tầng theo nguồn và theo thời gian, đủ ít nhất khoảng 100 văn bản mỗi lớp. Tách tập huấn luyện/kiểm định (để chọn $\delta$, tạo từ điển) và tập kiểm tra (chỉ dùng một lần để báo cáo).

## **F2. Độ đồng thuận giữa người gán nhãn \[B\]**

Hai người gán nhãn độc lập, tính hệ số Cohen:

$$\kappa =\frac{{p}_{o}-{p}_{e}}{1-{p}_{e}},  {p}_{e}=\sum\limits_{c}^{}{p}_{c}^{\left({1}\right)} {p}_{c}^{\left({2}\right)}$$

${p}_{o}$ là tỷ lệ hai người gán trùng nhau; ${p}_{c}^{\left({1}\right)},{p}_{c}^{\left({2}\right)}$ là tỷ lệ mỗi người gán lớp $c$. Theo Landis & Koch (1977), $\kappa$ từ 0,61 đến 0,80 là đồng thuận đáng kể, trên 0,80 là gần như hoàn hảo. Nếu có từ ba người gán trở lên, dùng Krippendorff’s $\alpha$. Các văn bản bất đồng cần họp thống nhất lại nhãn trước khi chốt tập nhãn chuẩn.

## **F3. Ma trận nhầm lẫn và các chỉ số \[B\]**

Với mỗi lớp $c$, gọi ${TP}_{c}$, ${FP}_{c}$, ${FN}_{c}$ là số dự đoán đúng, dự đoán thừa và dự đoán sót.

$$Accuracy=\frac{\sum\limits_{c}^{}{TP}_{c}}{n}$$

$${Precision}_{c}=\frac{{TP}_{c}}{{TP}_{c}+{FP}_{c}},  {Recall}_{c}=\frac{{TP}_{c}}{{TP}_{c}+{FN}_{c}}$$

$${F1}_{c}=\frac{2 {Precision}_{c} {Recall}_{c}}{{Precision}_{c}+{Recall}_{c}}$$

$$Macro-F1=\frac{1}{C}\sum\limits_{c=1}^{C}{F1}_{c},  Weighted-F1=\sum\limits_{c=1}^{C}\frac{{n}_{c}}{n} {F1}_{c}$$

Khi các lớp lệch nhau nhiều (văn bản chuyển đổi số thường nghiêng về tích cực), ưu tiên báo cáo Macro-F1 cùng với Accuracy.

## **F4. Tương quan giữa điểm tone và nhãn thứ bậc \[N\]**

Nếu nhãn người gán có thứ bậc (ví dụ $-1,0,+1$ hoặc thang 1–5), tính hệ số Spearman giữa ${Tone}_{i}$ và nhãn:

$${\rho }_{S}=1-\frac{6\sum\limits_{i}^{}{d}_{i}^{2}}{n\left({{n}^{2}-1}\right)}$$

${d}_{i}$ là chênh lệch hạng của văn bản $i$ giữa hai dãy. Công thức này dùng khi không có hạng trùng nhau; nếu có nhiều hạng trùng, tính hệ số Pearson trên các hạng.

## **F5. So sánh hai phương pháp hoặc hai từ điển \[B, phục vụ mục tiêu so sánh từ điển tổng quát với từ điển chủ đề\]**

(Thay cho C4 của bản cũ.) Chạy cả hai phương pháp trên cùng tập kiểm tra. Gọi $b$ là số văn bản phương pháp A phân loại đúng nhưng B sai, $c$ là số văn bản B đúng nhưng A sai. Kiểm định McNemar (có hiệu chỉnh liên tục):

$${\chi }^{2}=\frac{{\left({\left|{b-c}\right|-1}\right)}^{2}}{b+c} \sim  {\chi }^{2}\left({1}\right)$$

Giá trị tới hạn ở mức 5% là 3,84. Kết hợp thêm độ phủ từ điển:

$${Coverage}_{i}=\frac{\sum\limits_{j\in Pos\cup Neg}^{}{F}_{i,j}}{{a}_{i}}$$

và tỷ lệ văn bản không có từ cảm xúc nào. Từ điển tổng quát thường có độ phủ cao nhưng nhiều từ cảm xúc không đúng nghĩa trong chủ đề chuyển đổi số; từ điển chủ đề thì ngược lại. Báo cáo cả hai khía cạnh.

## **F6. Khoảng tin cậy bootstrap và độ vững \[N\]**

Lấy lại mẫu có hoàn lại $B=1000$ lần từ tập kiểm tra, tính Macro-F1 mỗi lần, và lấy phân vị 2,5% và 97,5% làm khoảng tin cậy 95%. Kiểm tra độ vững bằng cách thay đổi từng tham số một: độ dài cửa sổ phủ định (2, 3, 4), ${L}_{c}$ (5, 10, 15), $\delta$, dạng tone (C1, C2, C3), và đo mức thống nhất nhãn giữa các biến thể bằng $\kappa$.

# **PHẦN G. Thống kê mô tả và phân tích xu hướng**

## **G1. Chỉ số cảm xúc theo kỳ \[N\]**

Với kỳ $t$ (tháng, quý, năm), gọi ${P}_{t}$, ${N}_{t}$, ${T}_{t}$ là số văn bản tích cực, tiêu cực và tổng số văn bản được phân loại:

$${NSI}_{t}=\frac{{P}_{t}-{N}_{t}}{{T}_{t}},  {\overline{Tone}}_{t}=\frac{1}{{n}_{t}}\sum\limits_{i\in t}^{}{Tone}_{i}$$

${NSI}_{t}$ (chỉ số cảm xúc ròng) nằm trong $\left[{-1,1}\right]$. Có thể làm trơn bằng trung bình trượt 3 kỳ khi mẫu theo kỳ nhỏ.

## **G2. Kiểm định so sánh giữa các nhóm \[N\]**

So sánh hai nhóm văn bản (ví dụ báo chí và văn bản doanh nghiệp, hoặc hai giai đoạn). Kiểm định Welch:

$$t=\frac{{x‾}_{1}-{x‾}_{2}}{\sqrt{\frac{{s}_{1}^{2}}{{n}_{1}}+\frac{{s}_{2}^{2}}{{n}_{2}}}}$$

Với từ ba nhóm trở lên, dùng kiểm định Kruskal–Wallis (phi tham số):

$$H=\frac{12}{n\left({n+1}\right)}\sum\limits_{g=1}^{G}\frac{{R}_{g}^{2}}{{n}_{g}}-3\left({n+1}\right)$$

${R}_{g}$ là tổng hạng của nhóm $g$; $H$ xấp xỉ phân phối ${\chi }^{2}\left({G-1}\right)$.

**Kiểm định dấu** (MacKinlay Eq. 23, chuyển thể) cho câu hỏi “tích cực có nhiều hơn tiêu cực không”: gọi ${N}^{+}$ là số văn bản tích cực và $N={N}^{+}+{N}^{-}$ (bỏ trung lập):

$$\theta =\frac{{N}^{+}-0,5N}{0,5\sqrt{N}} \sim  N\left({0,1}\right)$$

## **G3. Hồi quy xu hướng và yếu tố ảnh hưởng đến tone \[N\]**

(Chuyển thể từ J\&W Eq. 11 và MacKinlay Eq. 26–27.) Biến phụ thuộc là tone, các biến giải thích là thời gian, nhóm nguồn và độ dài:

$${Tone}_{i}=a+b {Time}_{i}+\sum\limits_{g=2}^{G}{\gamma }_{g} {Group}_{i,g}+c ln{a}_{i}+{\epsilon }_{i}$$

${Time}_{i}$ là năm hoặc quý của văn bản; ${Group}_{i,g}$ là biến giả cho nhóm nguồn (báo chí, cơ quan nhà nước, doanh nghiệp…) hoặc ngành. Giả thuyết ${H}_{0}:b=0$ kiểm tra xem tone có xu hướng thay đổi theo thời gian hay không. Dùng sai số chuẩn bền với phương sai thay đổi (White, 1980). Nếu muốn so sánh từng từ tích cực và tiêu cực riêng, chạy hai hồi quy với ${Pos}_{i}$ và ${Neg}_{i}$ làm biến phụ thuộc.

# **PHẦN H. Quy trình tóm tắt**

1. **Chuẩn bị** (Phần A): làm sạch, tách từ, lọc văn bản đúng chủ đề, đánh dấu phủ định.

2. **Từ điển** (Phần B): lập từ điển hạt giống, mở rộng bằng B2–B4 nếu cần, rà soát từ nhập nhằng.

3. **Tính điểm** (Phần C): tone tỷ lệ C1 và tf.idf C2 là hai chỉ số bắt buộc; C3–C5 là các phiên bản cải tiến.

4. **Phân loại** (Phần D): chọn $\delta$ trên tập huấn luyện, áp dụng lên tập kiểm tra.

5. **Đánh giá** (Phần F): tập nhãn chuẩn, $\kappa$, Accuracy, Macro-F1, so sánh với từ điển tổng quát bằng McNemar.

6. **Phân tích** (Phần G): xu hướng theo thời gian và so sánh nhóm sau khi đã kiểm chứng độ tin cậy của phân loại.

**Bộ tối thiểu để làm đủ đề án:** A1–A4, B1, C1, C2, D1, F1, F2, F3, F5.