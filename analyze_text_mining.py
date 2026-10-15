"""Phân tích sắc thái và chủ đề chuyển đổi số từ dữ liệu đã crawl.

Mặc định chương trình đọc hai nguồn hiện có:
- S3: Thông cáo báo chí và sự kiện ngành.
- S4: Google Play và Apple App Store.

Điểm từng nguồn tuân theo tài liệu phương pháp:
    Điểm nguồn (%) = P / (P + N + T) * 100

Chạy:
    python analyze_text_mining.py --output output/legacy/text_mining
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence


ENTITIES = ("ZaloPay", "VPBank", "VCB", "HDBank", "ACB")

SOURCES = {
    "S1": "Báo cáo thường niên và báo cáo phát triển bền vững",
    "S2": "Báo cáo tài chính hợp nhất",
    "S3": "Thông cáo báo chí và sự kiện ngành",
    "S4": "Google Play và App Store",
}

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai_tri_tue_nhan_tao": (
        "ai",
        "tri tue nhan tao",
        "artificial intelligence",
        "machine learning",
        "hoc may",
        "genai",
        "generative ai",
        "chatbot",
        "tro ly ao",
    ),
    "cloud_dien_toan_dam_may": (
        "cloud",
        "dien toan dam may",
        "ha tang dam may",
        "cloud native",
        "multi cloud",
        "hybrid cloud",
    ),
    "du_lieu_big_data": (
        "big data",
        "du lieu lon",
        "data lake",
        "data warehouse",
        "phan tich du lieu",
        "quan tri du lieu",
    ),
    "core_banking": ("core banking", "corebanking", "he thong loi", "ngan hang loi"),
    "open_banking_api": ("open banking", "open api", "api mo", "banking as a service", "baas"),
    "blockchain": ("blockchain", "chuoi khoi", "smart contract", "hop dong thong minh"),
    "tu_dong_hoa_rpa": (
        "tu dong hoa",
        "rpa",
        "robotic process automation",
        "quy trinh tu dong",
    ),
    "ngan_hang_so_mobile_banking": (
        "ngan hang so",
        "mobile banking",
        "digital banking",
        "digibank",
        "ung dung ngan hang",
        "app ngan hang",
    ),
    "thanh_toan_so_qr_vi_dien_tu": (
        "thanh toan so",
        "thanh toan dien tu",
        "vi dien tu",
        "qr code",
        "quet qr",
        "vietqr",
        "khong tien mat",
        "contactless",
    ),
    "bao_mat_an_ninh_mang": (
        "bao mat",
        "an ninh mang",
        "cybersecurity",
        "ma hoa",
        "lua dao",
        "hack",
        "lo thong tin",
        "mat du lieu",
    ),
    "sinh_trac_hoc_dinh_danh": (
        "sinh trac hoc",
        "face id",
        "faceid",
        "nfc",
        "ekyc",
        "vneid",
        "xac thuc",
        "dinh danh dien tu",
        "smart otp",
        "otp",
    ),
    "cong_nghe_chuyen_doi_so": (
        "chuyen doi so",
        "so hoa",
        "cong nghe so",
        "nen tang so",
        "he sinh thai so",
        "fintech",
        "doi moi sang tao",
    ),
    "trai_nghiem_ui_ux": (
        "trai nghiem khach hang",
        "ui",
        "ux",
        "giao dien",
        "de dung",
        "kho dung",
        "tien loi",
        "bat tien",
        "phuc tap",
    ),
    "hieu_nang_on_dinh": (
        "nhanh",
        "muot",
        "on dinh",
        "cham",
        "lag",
        "treo",
        "crash",
        "bao tri",
        "loi he thong",
        "khong vao duoc",
    ),
    "giao_dich_chuyen_tien": (
        "giao dich",
        "chuyen tien",
        "nhan tien",
        "thanh toan",
        "tru tien",
        "hoan tien",
    ),
    "ho_tro_khach_hang": (
        "cham soc khach hang",
        "cskh",
        "hotline",
        "tong dai",
        "ho tro",
        "phan hoi",
    ),
    "phi_lai_suat": ("phi", "thu phi", "lai suat"),
    "tiet_kiem_vay_tin_dung": (
        "tiet kiem",
        "khoan vay",
        "vay",
        "tin dung",
        "giai ngan",
    ),
    "the_ngan_hang": ("the atm", "the tin dung", "the ghi no", "khoa the"),
}

TOPIC_LABELS = {
    "ai_tri_tue_nhan_tao": "AI và trí tuệ nhân tạo",
    "cloud_dien_toan_dam_may": "Cloud và điện toán đám mây",
    "du_lieu_big_data": "Dữ liệu và Big Data",
    "core_banking": "Core Banking",
    "open_banking_api": "Open Banking và API",
    "blockchain": "Blockchain",
    "tu_dong_hoa_rpa": "Tự động hóa và RPA",
    "ngan_hang_so_mobile_banking": "Ngân hàng số và Mobile Banking",
    "thanh_toan_so_qr_vi_dien_tu": "Thanh toán số QR và ví điện tử",
    "bao_mat_an_ninh_mang": "Bảo mật và an ninh mạng",
    "sinh_trac_hoc_dinh_danh": "Sinh trắc học và định danh",
    "cong_nghe_chuyen_doi_so": "Công nghệ và chuyển đổi số",
    "trai_nghiem_ui_ux": "Trải nghiệm khách hàng UI UX",
    "hieu_nang_on_dinh": "Hiệu năng và độ ổn định",
    "giao_dich_chuyen_tien": "Giao dịch và chuyển tiền",
    "ho_tro_khach_hang": "Hỗ trợ khách hàng",
    "phi_lai_suat": "Phí và lãi suất",
    "tiet_kiem_vay_tin_dung": "Tiết kiệm vay và tín dụng",
    "the_ngan_hang": "Thẻ ngân hàng",
    "khac_chua_ro_tu_khoa": "Khác chưa rõ từ khóa",
}

POSITIVE_TERMS = (
    "tot",
    "rat tot",
    "tuyet voi",
    "xuat sac",
    "hai long",
    "tien loi",
    "de dung",
    "nhanh",
    "muot",
    "on dinh",
    "an toan",
    "tin cay",
    "thanh cong",
    "tang truong",
    "dan dau",
    "hang dau",
    "duoc vinh danh",
    "dat giai",
    "giai thuong",
    "doi moi",
    "nang cao",
    "cai thien",
    "hieu qua",
)

NEGATIVE_TERMS = (
    "te",
    "rat te",
    "kem",
    "that vong",
    "khong hai long",
    "loi",
    "loi he thong",
    "khong vao duoc",
    "khong dung duoc",
    "khong cho",
    "khong the",
    "khong the giao dich",
    "khong giao dich duoc",
    "mai khong",
    "cham",
    "lag",
    "treo",
    "crash",
    "bat tien",
    "kho dung",
    "mat tien",
    "tru tien",
    "lua dao",
    "rui ro",
    "su co",
    "gian doan",
    "ro ri",
    "ro ri du lieu",
    "lo du lieu",
    "tan cong",
    "tan cong mang",
    "gian lan",
    "mao danh",
    "mat tien",
    "khoa tai khoan",
    "khieu nai",
    "phan anh",
    "canh bao",
    "vi pham",
    "xu phat",
    "khung hoang",
    "chap mach",
    "len con",
    "dien",
    "ngu",
    "rac",
    "vo van",
    "nham",
    "buc",
    "uc che",
    "kho chiu",
)

ANALYZED_FIELDS = (
    "entity",
    "source_code",
    "source_name",
    "platform",
    "record_id",
    "record_date",
    "rating",
    "title",
    "text",
    "sentiment",
    "sentiment_basis",
    "positive_terms",
    "negative_terms",
    "topics",
    "matched_keywords",
    "original_category",
    "url",
)


@dataclass
class AnalyzedRecord:
    """Bản ghi chuẩn hóa dùng chung cho mọi nguồn dữ liệu."""

    entity: str
    source_code: str
    platform: str
    record_id: str
    record_date: str
    rating: str
    title: str
    text: str
    sentiment: str
    sentiment_basis: str
    positive_terms: list[str]
    negative_terms: list[str]
    topic_hits: dict[str, Counter[str]]
    original_category: str = ""
    url: str = ""

    def to_csv_row(self) -> dict[str, str]:
        """Chuyển bản ghi phân tích thành một dòng CSV dễ kiểm tra."""

        topics = sorted(self.topic_hits) or ["khac_chua_ro_tu_khoa"]
        keyword_parts = [
            f"{topic}:{keyword}={count}"
            for topic in sorted(self.topic_hits)
            for keyword, count in sorted(self.topic_hits[topic].items())
        ]
        return {
            "entity": self.entity,
            "source_code": self.source_code,
            "source_name": SOURCES[self.source_code],
            "platform": self.platform,
            "record_id": self.record_id,
            "record_date": self.record_date,
            "rating": self.rating,
            "title": self.title,
            "text": self.text,
            "sentiment": self.sentiment,
            "sentiment_basis": self.sentiment_basis,
            "positive_terms": ";".join(self.positive_terms),
            "negative_terms": ";".join(self.negative_terms),
            "topics": ";".join(topics),
            "matched_keywords": ";".join(keyword_parts),
            "original_category": self.original_category,
            "url": self.url,
        }


# Ghi chú: Lưu topic dưới dạng Counter để vừa đếm số bản ghi nhắc đến vừa đếm số lần xuất hiện.


def configure_console_utf8() -> None:
    """Ưu tiên UTF-8 cho log tiếng Việt trên Windows."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


# Ghi chú: Hàm chỉ đổi encoding hiển thị, không thay đổi dữ liệu đầu vào.


def parse_date(value: str) -> date:
    """Đọc ngày theo định dạng YYYY-MM-DD."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Ngày phải có định dạng YYYY-MM-DD") from exc


# Ghi chú: Kiểm tra ngày ngay ở argparse giúp lỗi nhập liệu dễ hiểu hơn.


def normalize_text(value: str) -> str:
    """Bỏ dấu, chuyển chữ thường và gom khoảng trắng để so khớp ổn định."""

    decomposed = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    lowered = without_marks.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", lowered).strip()


# Ghi chú: Dữ liệu gốc vẫn được giữ nguyên; bản chuẩn hóa chỉ dùng để phân loại.


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Tạo regex có ranh giới từ cho một từ hoặc cụm từ đã chuẩn hóa."""

    escaped = re.escape(normalize_text(phrase)).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)")


# Ghi chú: Ranh giới từ tránh trường hợp 'ai' khớp nhầm bên trong một từ dài.


TOPIC_PATTERNS = {
    topic: {keyword: phrase_pattern(keyword) for keyword in keywords}
    for topic, keywords in TOPIC_KEYWORDS.items()
}
POSITIVE_PATTERNS = {term: phrase_pattern(term) for term in POSITIVE_TERMS}
NEGATIVE_PATTERNS = {term: phrase_pattern(term) for term in NEGATIVE_TERMS}


def count_pattern_hits(text: str, patterns: dict[str, re.Pattern[str]]) -> Counter[str]:
    """Đếm số lần xuất hiện của từng cụm từ trong văn bản chuẩn hóa."""

    return Counter({term: len(pattern.findall(text)) for term, pattern in patterns.items() if pattern.search(text)})


# Ghi chú: Counter không lưu từ khóa không xuất hiện nên file tổng hợp gọn hơn.


def classify_topics(text: str) -> dict[str, Counter[str]]:
    """Gán một hoặc nhiều nhóm chủ đề và giữ bằng chứng từ khóa."""

    normalized = normalize_text(text)
    return {
        topic: hits
        for topic, patterns in TOPIC_PATTERNS.items()
        if (hits := count_pattern_hits(normalized, patterns))
    }


# Ghi chú: Chủ đề độc lập với sentiment, nên một lời chê vẫn được xếp đúng nhóm vấn đề.


def text_sentiment_evidence(text: str) -> tuple[list[str], list[str]]:
    """Tìm bằng chứng tích cực và tiêu cực trong nội dung chữ."""

    normalized = normalize_text(text)
    positive = sorted(count_pattern_hits(normalized, POSITIVE_PATTERNS))
    negative = sorted(count_pattern_hits(normalized, NEGATIVE_PATTERNS))

    for term in list(positive):
        negated = re.search(rf"\b(?:khong|chua|chang)\s+(?:he\s+)?{phrase_pattern(term).pattern}", normalized)
        if negated:
            positive.remove(term)
            negative.append(f"phủ định:{term}")

    for term in list(negative):
        if term.startswith("phủ định:") or term.startswith("khong ") or term.startswith("chua "):
            continue
        negated_negative = re.search(
            rf"\b(?:khong|chua|chang)\s+(?:bi\s+|con\s+|he\s+)?{phrase_pattern(term).pattern}",
            normalized,
        )
        if negated_negative:
            negative.remove(term)
    return positive, sorted(set(negative))


# Ghi chú: Phủ định giúp 'không tốt' thành tín hiệu xấu và 'không bị lỗi' không bị coi là lời chê.


def classify_text_sentiment(text: str) -> tuple[str, list[str], list[str]]:
    """Phân loại nội dung không có sao dựa trên chênh lệch bằng chứng từ ngữ."""

    positive, negative = text_sentiment_evidence(text)
    if len(positive) > len(negative):
        return "Positive", positive, negative
    if len(negative) > len(positive):
        return "Negative", positive, negative
    return "Neutral", positive, negative


# Ghi chú: Khi bằng chứng bằng nhau hoặc không có bằng chứng, kết quả là Neutral thay vì đoán.


def review_sentiment(rating: int, content: str) -> tuple[str, str, list[str], list[str]]:
    """Phân loại review bằng mô hình lai số sao và bằng chứng trong nội dung."""

    positive, negative = text_sentiment_evidence(content)
    positive_count = len(positive)
    negative_count = len(negative)
    sentiment = "Negative" if rating <= 2 else "Neutral" if rating == 3 else "Positive"
    basis = f"rating_{rating}_star"

    if rating >= 4 and negative_count >= 2 and negative_count >= positive_count + 2:
        sentiment = "Negative"
        basis += ";text_override_negative"
    elif rating == 3 and positive_count >= 2 and negative_count == 0:
        sentiment = "Positive"
        basis += ";text_override_positive"
    elif rating == 3 and negative_count >= 2 and positive_count == 0:
        sentiment = "Negative"
        basis += ";text_override_negative"
    elif rating <= 2 and positive_count >= 2 and positive_count >= negative_count + 2:
        sentiment = "Positive"
        basis += ";text_override_positive"

    text_label = "Positive" if positive_count > negative_count else "Negative" if negative_count > positive_count else "Neutral"
    if text_label != "Neutral" and text_label != sentiment and "text_override" not in basis:
        basis += ";text_mismatch_review"
    return sentiment, basis, positive, negative


# Ghi chú: Nội dung rõ ràng có thể sửa nhãn sao bấm nhầm; bằng chứng yếu chỉ được đánh dấu để rà soát.


def safe_date(value: str) -> date | None:
    """Đọc ngày ISO đầy đủ hoặc YYYY-MM-DD; trả None nếu không hợp lệ."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


# Ghi chú: Chấp nhận cả timestamp của App Store/Google Play và ngày của bài báo.


def in_period(value: str, start_date: date, end_date: date) -> bool:
    """Kiểm tra bản ghi có nằm trong kỳ phân tích hay không."""

    parsed = safe_date(value)
    return parsed is not None and start_date <= parsed <= end_date


# Ghi chú: Bản ghi thiếu ngày hoặc sai định dạng không được tự động đưa vào kỳ.


def iter_csv(path: Path) -> Iterator[dict[str, str]]:
    """Đọc CSV UTF-8 hoặc UTF-8 BOM theo từng dòng để tiết kiệm bộ nhớ."""

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


# Ghi chú: Đọc streaming phù hợp với file review hàng trăm nghìn dòng.


def iter_review_records(path: Path, start_date: date, end_date: date) -> Iterator[AnalyzedRecord]:
    """Chuẩn hóa và phân tích review từ Google Play và App Store."""

    for row in iter_csv(path):
        review_date = row.get("review_date", "")
        if not in_period(review_date, start_date, end_date):
            continue
        try:
            rating = int(float(row.get("rating", "0")))
        except ValueError:
            continue
        content = row.get("content", "").strip()
        sentiment, basis, positive, negative = review_sentiment(rating, content)
        yield AnalyzedRecord(
            entity=row.get("entity", "").strip(),
            source_code="S4",
            platform=row.get("platform", "").strip(),
            record_id=row.get("review_id", "").strip(),
            record_date=review_date,
            rating=str(rating),
            title="",
            text=content,
            sentiment=sentiment,
            sentiment_basis=basis,
            positive_terms=positive,
            negative_terms=negative,
            topic_hits=classify_topics(content),
        )


# Ghi chú: Một review là một lượt đề cập; không đếm phản hồi của nhà phát triển vào sentiment khách hàng.


def iter_press_records(path: Path, start_date: date, end_date: date) -> Iterator[AnalyzedRecord]:
    """Chuẩn hóa và phân tích bài báo, thông cáo và sự kiện đã crawl."""

    for row in iter_csv(path):
        published_date = row.get("published_date", "")
        if not in_period(published_date, start_date, end_date):
            continue
        title = row.get("title", "").strip()
        sapo = row.get("sapo", "").strip()
        content = row.get("content", "").strip()
        analysis_text = " ".join(part for part in (title, sapo, content[:5000]) if part)
        sentiment, positive, negative = classify_text_sentiment(analysis_text)
        yield AnalyzedRecord(
            entity=row.get("entity", "").strip(),
            source_code="S3",
            platform=row.get("source_domain", row.get("source_name", "")).strip(),
            record_id=row.get("content_hash", row.get("url", "")).strip(),
            record_date=published_date,
            rating="",
            title=title,
            text=sapo or content[:1000],
            sentiment=sentiment,
            sentiment_basis="rule_based_title_sapo_content",
            positive_terms=positive,
            negative_terms=negative,
            topic_hits=classify_topics(analysis_text),
            original_category=row.get("category", "").strip(),
            url=row.get("url", "").strip(),
        )


# Ghi chú: Chỉ dùng 5.000 ký tự đầu để giảm nhiễu menu và tin liên quan ở cuối trang báo.


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: Sequence[str]) -> None:
    """Ghi CSV UTF-8 BOM để Excel hiển thị đúng tiếng Việt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# Ghi chú: extrasaction='ignore' giúp bảng tổng hợp không lỗi vì trường nội bộ bổ sung.


def maturity_level(score: float) -> tuple[str, str]:
    """Quy đổi điểm phần trăm sang thang năm mức trong tài liệu phương pháp."""

    if score >= 100:
        return "Mức 5", "Dẫn dắt"
    if score >= 75:
        return "Mức 4", "Nâng cao"
    if score >= 50:
        return "Mức 3", "Hình thành"
    if score >= 25:
        return "Mức 2", "Bắt đầu"
    return "Mức 1", "Khởi động"


# Ghi chú: Mức 5 chỉ đạt khi điểm bằng 100%, đúng định nghĩa không có N hoặc T.


def process_records(
    records: Iterable[AnalyzedRecord],
    writer: csv.DictWriter,
    sentiment_counts: Counter[tuple[str, str, str, str]],
    source_counts: Counter[tuple[str, str, str]],
    monthly_counts: Counter[tuple[str, str, str, str]],
    topic_counts: Counter[tuple[str, str, str, str]],
    keyword_mentions: Counter[tuple[str, str, str, str, str]],
    keyword_occurrences: Counter[tuple[str, str, str, str]],
) -> int:
    """Ghi bản ghi chi tiết và cập nhật toàn bộ bộ đếm tổng hợp."""

    processed = 0
    for record in records:
        if record.entity not in ENTITIES:
            continue
        writer.writerow(record.to_csv_row())
        processed += 1
        sentiment_counts[(record.entity, record.source_code, record.platform, record.sentiment)] += 1
        source_counts[(record.entity, record.source_code, record.sentiment)] += 1
        parsed = safe_date(record.record_date)
        if parsed:
            monthly_counts[(record.entity, record.source_code, parsed.strftime("%Y-%m"), record.sentiment)] += 1

        topics = record.topic_hits or {"khac_chua_ro_tu_khoa": Counter()}
        for topic, hits in topics.items():
            topic_counts[(record.entity, record.source_code, topic, record.sentiment)] += 1
            for keyword, count in hits.items():
                keyword_mentions[(record.entity, record.source_code, topic, keyword, record.sentiment)] += 1
                keyword_occurrences[(record.entity, record.source_code, topic, keyword)] += count
    return processed


# Ghi chú: Mỗi bản ghi chỉ tăng mention_count một lần cho mỗi topic/từ khóa, dù từ đó lặp lại nhiều lần.


def build_sentiment_summary(
    counts: Counter[tuple[str, str, str, str]],
) -> list[dict[str, object]]:
    """Tạo bảng P N T theo ngân hàng, nguồn và nền tảng."""

    groups = sorted({key[:3] for key in counts})
    rows: list[dict[str, object]] = []
    for entity, source_code, platform in groups:
        positive = counts[(entity, source_code, platform, "Positive")]
        negative = counts[(entity, source_code, platform, "Negative")]
        neutral = counts[(entity, source_code, platform, "Neutral")]
        total = positive + negative + neutral
        rows.append(
            {
                "entity": entity,
                "source_code": source_code,
                "source_name": SOURCES[source_code],
                "platform": platform,
                "positive_count": positive,
                "negative_count": negative,
                "neutral_count": neutral,
                "total_mentions": total,
                "positive_rate_percent": round(positive / total * 100, 3) if total else "",
            }
        )
    return rows


# Ghi chú: Tỷ lệ trong bảng này là P/(P+N+T), không loại bỏ lượt trung tính khỏi mẫu số.


def build_source_scores(
    counts: Counter[tuple[str, str, str]],
) -> list[dict[str, object]]:
    """Tạo điểm S1 đến S4 và ghi rõ nguồn thiếu dữ liệu."""

    rows: list[dict[str, object]] = []
    for entity in ENTITIES:
        for source_code, source_name in SOURCES.items():
            positive = counts[(entity, source_code, "Positive")]
            negative = counts[(entity, source_code, "Negative")]
            neutral = counts[(entity, source_code, "Neutral")]
            total = positive + negative + neutral
            rows.append(
                {
                    "entity": entity,
                    "source_code": source_code,
                    "source_name": source_name,
                    "positive_count": positive,
                    "negative_count": negative,
                    "neutral_count": neutral,
                    "total_mentions": total,
                    "source_score_percent": round(positive / total * 100, 3) if total else "",
                    "data_status": "Đủ dữ liệu để tính" if total else "Không đủ dữ liệu",
                }
            )
    return rows


# Ghi chú: Nguồn không có lượt đề cập được để trống điểm, tuyệt đối không tự động gán 0%.


def build_overall_scores(source_rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Tính trung bình các nguồn có dữ liệu và nêu số nguồn thực tế được dùng."""

    grouped: dict[str, list[float]] = defaultdict(list)
    for row in source_rows:
        score = row["source_score_percent"]
        if score != "":
            grouped[str(row["entity"])].append(float(score))

    rows: list[dict[str, object]] = []
    for entity in ENTITIES:
        scores = grouped.get(entity, [])
        if not scores:
            rows.append(
                {
                    "entity": entity,
                    "overall_score_percent": "",
                    "available_source_count": 0,
                    "required_source_count": 4,
                    "maturity_level": "",
                    "level_name": "",
                    "comparison_status": "Không đủ dữ liệu",
                }
            )
            continue
        average = round(sum(scores) / len(scores), 3)
        level, level_name = maturity_level(average)
        rows.append(
            {
                "entity": entity,
                "overall_score_percent": average,
                "available_source_count": len(scores),
                "required_source_count": 4,
                "maturity_level": level,
                "level_name": level_name,
                "comparison_status": "Đủ 4 nguồn" if len(scores) == 4 else f"Tạm tính trên {len(scores)}/4 nguồn",
            }
        )
    return rows


# Ghi chú: Điểm tạm tính không được xem là so sánh chính thức khi chưa đủ bốn nguồn.


def build_monthly_summary(
    counts: Counter[tuple[str, str, str, str]],
) -> list[dict[str, object]]:
    """Tổng hợp P N T và điểm nguồn theo từng tháng."""

    groups = sorted({key[:3] for key in counts})
    rows: list[dict[str, object]] = []
    for entity, source_code, month in groups:
        positive = counts[(entity, source_code, month, "Positive")]
        negative = counts[(entity, source_code, month, "Negative")]
        neutral = counts[(entity, source_code, month, "Neutral")]
        total = positive + negative + neutral
        rows.append(
            {
                "entity": entity,
                "source_code": source_code,
                "source_name": SOURCES[source_code],
                "month": month,
                "positive_count": positive,
                "negative_count": negative,
                "neutral_count": neutral,
                "total_mentions": total,
                "positive_rate_percent": round(positive / total * 100, 3) if total else "",
            }
        )
    return rows


# Ghi chú: Bảng tháng dùng cùng công thức với điểm nguồn để có thể so sánh xu hướng.


def build_topic_summary(
    counts: Counter[tuple[str, str, str, str]],
) -> list[dict[str, object]]:
    """Tổng hợp số bản ghi nhắc đến từng nhóm chủ đề và sắc thái tương ứng."""

    groups = sorted({key[:3] for key in counts})
    rows: list[dict[str, object]] = []
    for entity, source_code, topic in groups:
        positive = counts[(entity, source_code, topic, "Positive")]
        negative = counts[(entity, source_code, topic, "Negative")]
        neutral = counts[(entity, source_code, topic, "Neutral")]
        rows.append(
            {
                "entity": entity,
                "source_code": source_code,
                "source_name": SOURCES[source_code],
                "topic": topic,
                "topic_label": TOPIC_LABELS[topic],
                "mention_count": positive + negative + neutral,
                "positive_count": positive,
                "negative_count": negative,
                "neutral_count": neutral,
            }
        )
    return rows


# Ghi chú: mention_count đếm số review/bài có nhắc topic, không cộng lặp từ trong cùng một bản ghi.


def build_keyword_summary(
    mentions: Counter[tuple[str, str, str, str, str]],
    occurrences: Counter[tuple[str, str, str, str]],
) -> list[dict[str, object]]:
    """Tổng hợp số bản ghi và tổng số lần xuất hiện của từng cụm từ."""

    groups = sorted({key[:4] for key in occurrences})
    rows: list[dict[str, object]] = []
    for entity, source_code, topic, keyword in groups:
        positive = mentions[(entity, source_code, topic, keyword, "Positive")]
        negative = mentions[(entity, source_code, topic, keyword, "Negative")]
        neutral = mentions[(entity, source_code, topic, keyword, "Neutral")]
        rows.append(
            {
                "entity": entity,
                "source_code": source_code,
                "source_name": SOURCES[source_code],
                "topic": topic,
                "topic_label": TOPIC_LABELS[topic],
                "keyword": keyword,
                "mention_count": positive + negative + neutral,
                "occurrence_count": occurrences[(entity, source_code, topic, keyword)],
                "positive_count": positive,
                "negative_count": negative,
                "neutral_count": neutral,
            }
        )
    return rows


# Ghi chú: occurrence_count cho biết cụm từ lặp bao nhiêu lần; mention_count cho biết xuất hiện trong bao nhiêu bản ghi.


def parse_args() -> argparse.Namespace:
    """Khai báo tham số dòng lệnh với đường dẫn mặc định của dự án."""

    parser = argparse.ArgumentParser(description="Phân tích text mining chuyển đổi số theo P, N, T")
    parser.add_argument("--reviews", type=Path, default=Path("output/raw/app_reviews/reviews_2025_to_now.csv"))
    parser.add_argument("--press-events", type=Path, default=Path("output/raw/press_1/press_events_2025_to_now.csv"))
    parser.add_argument("--output", type=Path, default=Path("output/legacy/text_mining"))
    parser.add_argument("--start-date", type=parse_date, default=date(2025, 1, 1))
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("start-date không được sau end-date")
    return args


# Ghi chú: Nếu file press-events chưa có, chương trình vẫn phân tích review và ghi S3 là không đủ dữ liệu.


def run(args: argparse.Namespace) -> None:
    """Chạy phân tích, ghi các bảng chi tiết, tổng hợp và metadata."""

    args.output.mkdir(parents=True, exist_ok=True)
    sentiment_counts: Counter[tuple[str, str, str, str]] = Counter()
    source_counts: Counter[tuple[str, str, str]] = Counter()
    monthly_counts: Counter[tuple[str, str, str, str]] = Counter()
    topic_counts: Counter[tuple[str, str, str, str]] = Counter()
    keyword_mentions: Counter[tuple[str, str, str, str, str]] = Counter()
    keyword_occurrences: Counter[tuple[str, str, str, str]] = Counter()
    input_status: dict[str, dict[str, object]] = {}

    analyzed_path = args.output / "text_mentions_analyzed.csv"
    with analyzed_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANALYZED_FIELDS)
        writer.writeheader()

        if args.reviews.exists():
            count = process_records(
                iter_review_records(args.reviews, args.start_date, args.end_date),
                writer,
                sentiment_counts,
                source_counts,
                monthly_counts,
                topic_counts,
                keyword_mentions,
                keyword_occurrences,
            )
            input_status["reviews"] = {"path": str(args.reviews.resolve()), "rows_used": count}
            print(f"Đã phân tích {count:,} review")
        else:
            input_status["reviews"] = {"path": str(args.reviews), "rows_used": 0, "status": "Không tìm thấy file"}
            print(f"Cảnh báo: không tìm thấy {args.reviews}")

        if args.press_events.exists():
            count = process_records(
                iter_press_records(args.press_events, args.start_date, args.end_date),
                writer,
                sentiment_counts,
                source_counts,
                monthly_counts,
                topic_counts,
                keyword_mentions,
                keyword_occurrences,
            )
            input_status["press_events"] = {"path": str(args.press_events.resolve()), "rows_used": count}
            print(f"Đã phân tích {count:,} bài báo/sự kiện")
        else:
            input_status["press_events"] = {
                "path": str(args.press_events),
                "rows_used": 0,
                "status": "Không tìm thấy file",
            }
            print(f"Cảnh báo: không tìm thấy {args.press_events}")

    sentiment_rows = build_sentiment_summary(sentiment_counts)
    source_rows = build_source_scores(source_counts)
    overall_rows = build_overall_scores(source_rows)
    monthly_rows = build_monthly_summary(monthly_counts)
    topic_rows = build_topic_summary(topic_counts)
    keyword_rows = build_keyword_summary(keyword_mentions, keyword_occurrences)

    write_csv(
        args.output / "sentiment_summary.csv",
        sentiment_rows,
        ("entity", "source_code", "source_name", "platform", "positive_count", "negative_count", "neutral_count", "total_mentions", "positive_rate_percent"),
    )
    write_csv(
        args.output / "source_scores.csv",
        source_rows,
        ("entity", "source_code", "source_name", "positive_count", "negative_count", "neutral_count", "total_mentions", "source_score_percent", "data_status"),
    )
    write_csv(
        args.output / "overall_scores.csv",
        overall_rows,
        ("entity", "overall_score_percent", "available_source_count", "required_source_count", "maturity_level", "level_name", "comparison_status"),
    )
    write_csv(
        args.output / "monthly_sentiment.csv",
        monthly_rows,
        ("entity", "source_code", "source_name", "month", "positive_count", "negative_count", "neutral_count", "total_mentions", "positive_rate_percent"),
    )
    write_csv(
        args.output / "topic_summary.csv",
        topic_rows,
        ("entity", "source_code", "source_name", "topic", "topic_label", "mention_count", "positive_count", "negative_count", "neutral_count"),
    )
    write_csv(
        args.output / "keyword_summary.csv",
        keyword_rows,
        ("entity", "source_code", "source_name", "topic", "topic_label", "keyword", "mention_count", "occurrence_count", "positive_count", "negative_count", "neutral_count"),
    )

    metadata = {
        "method": "P / (P + N + T) * 100",
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "entities": list(ENTITIES),
        "input_status": input_status,
        "sentiment_rules": {
            "app_reviews": "mô hình lai số sao và nội dung; nội dung mạnh có thể sửa nhãn sao bấm nhầm",
            "press_events": "rule-based trên tiêu đề, sapo và 5.000 ký tự đầu nội dung",
        },
        "topic_count_rule": "mention_count đếm tối đa một lần mỗi bản ghi; occurrence_count đếm mọi lần lặp",
        "overall_note": "Điểm tổng thể thiếu nguồn là tạm tính trên các nguồn có dữ liệu, không gán nguồn thiếu bằng 0%.",
    }
    (args.output / "analysis_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Hoàn tất. Kết quả: {args.output.resolve()}")


# Ghi chú: Mọi file tổng hợp được tái tạo từ đầu để tránh cộng trùng giữa các lần chạy.


def main() -> None:
    """Điểm vào chương trình."""

    configure_console_utf8()
    run(parse_args())


# Ghi chú: Giữ main ngắn để các hàm phân loại có thể import và kiểm thử độc lập.


if __name__ == "__main__":
    main()
