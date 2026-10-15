"""Thu thập chỉ số và review ứng dụng tài chính trên Google Play/App Store.

Phạm vi mặc định:
- Ứng dụng: ZaloPay, VPBank NEO, VCB Digibank, HDBank, ACB ONE.
- Thời gian review: từ 2025-01-01 đến ngày chạy.
- Thị trường/ngôn ngữ: Việt Nam (vn/vi).

Chạy:
    python crawl_app_reviews.py --output output/raw/app_reviews
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình định danh của một ứng dụng trên hai kho."""

    entity: str
    google_id: str
    apple_id: str
    apple_slug: str


# Ghi chú: Dataclass giữ cấu hình tập trung, tránh rải app ID ở nhiều hàm.


APPS: tuple[AppConfig, ...] = (
    AppConfig("ZaloPay", "vn.com.vng.zalopay", "1112407590", "zalopay-thanh-toan-tai-chinh"),
    AppConfig("VPBank", "com.vnpay.vpbankonline", "1209349510", "vpbank-neo"),
    AppConfig("VCB", "com.VCB", "561433133", "vcb-digibank"),
    AppConfig("HDBank", "com.vnpay.hdbank", "1461658565", "hdbank"),
    AppConfig("ACB", "mobile.acb.com.vn", "950141024", "acb-one"),
)

REVIEW_FIELDS = (
    "entity",
    "platform",
    "app_id",
    "review_id",
    "user_name",
    "rating",
    "content",
    "review_date",
    "developer_reply",
    "reply_date",
    "app_version",
    "thumbs_up_count",
    "sentiment",
    "topics",
)

NEGATIVE_TOPICS = {
    "dang_nhap": ("dang nhap", "login", "mat khau", "khoa tai khoan"),
    "otp_xac_thuc": ("otp", "smart otp", "xac thuc", "sinh trac hoc", "face id", "nfc"),
    "chuyen_tien_giao_dich": ("chuyen tien", "giao dich", "thanh toan", "quet qr", "tru tien"),
    "crash_lag_bao_tri": ("crash", "lag", "treo", "loi he thong", "bao tri", "khong vao duoc"),
    "cap_nhat_phien_ban": ("cap nhat", "update", "phien ban"),
    "ui_ux": ("giao dien", "kho dung", "bat tien", "roi mat", "phuc tap"),
    "cskh": ("cskh", "cham soc khach hang", "hotline", "tong dai", "ho tro"),
    "phi_lai_suat": ("phi", "lai suat", "thu phi"),
    "bao_mat_lua_dao": ("bao mat", "lua dao", "hack", "lo thong tin"),
    "the_atm": ("the atm", "the tin dung", "the ghi no", "khoa the"),
    "tiet_kiem_vay": ("tiet kiem", "vay", "khoan vay", "giai ngan"),
}

POSITIVE_TOPICS = {
    "nhanh_on_dinh": ("nhanh", "muot", "on dinh", "tot"),
    "tien_loi_de_dung": ("tien loi", "de dung", "thuan tien", "de su dung"),
    "bao_mat_tin_cay": ("bao mat", "an toan", "tin cay", "yen tam"),
    "cskh_tot": ("ho tro tot", "nhiet tinh", "tan tam", "phan hoi nhanh"),
}


def configure_console_utf8() -> None:
    """Ưu tiên UTF-8 cho log/trợ giúp tiếng Việt trên Windows."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


# Ghi chú: Hàm này chỉ đổi encoding hiển thị, không sửa dữ liệu hoặc locale hệ thống.


def parse_date(value: str) -> date:
    """Chuyển chuỗi YYYY-MM-DD thành date và báo lỗi rõ ràng."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Ngày phải có định dạng YYYY-MM-DD") from exc


# Ghi chú: Hàm này được dùng trực tiếp bởi argparse để chặn ngày nhập sai ngay từ đầu.


def to_utc_datetime(value: Any) -> datetime | None:
    """Chuẩn hóa datetime/string/timestamp về datetime có múi giờ UTC."""

    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    return None


# Ghi chú: Giữ cùng chuẩn UTC giúp lọc ngày nhất quán giữa Google Play và Apple.


def iso_datetime(value: Any) -> str:
    """Đổi giá trị thời gian về chuỗi ISO 8601; trả rỗng nếu không hợp lệ."""

    parsed = to_utc_datetime(value)
    return parsed.isoformat() if parsed else ""


# Ghi chú: Chuỗi ISO 8601 dễ sắp xếp, nhập Excel và kiểm tra nguồn dữ liệu.


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt và đưa văn bản về chữ thường."""

    normalized = unicodedata.normalize("NFD", text or "")
    no_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return no_marks.replace("đ", "d").replace("Đ", "D").lower()


# Ghi chú: Chuẩn hóa này giúp từ khóa có dấu/không dấu được đối chiếu như nhau.


def keyword_present(text: str, keyword: str) -> bool:
    """Tìm từ khóa theo ranh giới từ để hạn chế match nhầm chuỗi con."""

    pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
    return re.search(pattern, text) is not None


# Ghi chú: Word-boundary tự viết phù hợp hơn \b khi dữ liệu đã được bỏ dấu.


def classify_sentiment(rating: int) -> str:
    """Gán sentiment theo quy tắc 1–2 tiêu cực, 3 trung lập, 4–5 tích cực."""

    if rating <= 2:
        return "Negative"
    if rating == 3:
        return "Neutral"
    return "Positive"


# Ghi chú: Đây là rule-based sentiment theo rating, không phải NLP theo nội dung.


def classify_topics(content: str, sentiment: str) -> str:
    """Gán một hoặc nhiều topic theo từ khóa và sentiment đã xác định."""

    normalized = strip_accents(content)
    topic_map = NEGATIVE_TOPICS if sentiment == "Negative" else POSITIVE_TOPICS
    matches = [
        topic
        for topic, keywords in topic_map.items()
        if any(keyword_present(normalized, keyword) for keyword in keywords)
    ]
    if matches:
        return ";".join(matches)
    if sentiment == "Negative":
        return "che_khac_chua_ro_tu_khoa"
    if sentiment == "Positive":
        return "khen_khac_chua_ro_tu_khoa"
    return "trung_lap_chua_ro_tu_khoa"


# Ghi chú: Review tích cực không nhận topic chê và ngược lại, giảm gán nhãn trái ngữ cảnh.


def enrich_review(row: dict[str, Any]) -> dict[str, Any]:
    """Bổ sung sentiment và topic vào một review đã chuẩn hóa."""

    rating = int(row["rating"])
    sentiment = classify_sentiment(rating)
    return {**row, "rating": rating, "sentiment": sentiment, "topics": classify_topics(row["content"], sentiment)}


# Ghi chú: Tách enrichment khỏi crawler để dễ kiểm thử và thay mô hình phân loại sau này.


def google_play_url(app_id: str) -> str:
    """Tạo URL Google Play chính thức cho một package ID."""

    return f"https://play.google.com/store/apps/details?id={app_id}&hl=vi&gl=VN"


# Ghi chú: URL được lưu cùng dữ liệu để người chấm có thể kiểm tra nguồn.


def apple_store_url(config: AppConfig) -> str:
    """Tạo URL App Store Việt Nam từ slug và Apple ID."""

    return f"https://apps.apple.com/vn/app/{config.apple_slug}/id{config.apple_id}"


# Ghi chú: Slug chỉ giúp URL dễ đọc; Apple ID mới là định danh chính.


def fetch_google_metadata(config: AppConfig) -> dict[str, Any]:
    """Lấy chỉ số hiện tại của ứng dụng trên Google Play."""

    from google_play_scraper import app

    payload = app(config.google_id, lang="vi", country="vn")
    return {
        "entity": config.entity,
        "platform": "Google Play",
        "app_id": config.google_id,
        "app_name": payload.get("title", ""),
        "app_url": google_play_url(config.google_id),
        "installs_display": payload.get("installs", ""),
        "min_installs": payload.get("minInstalls", ""),
        "real_installs": payload.get("realInstalls", ""),
        "store_review_count": payload.get("reviews", ""),
        "store_rating_count": payload.get("ratings", ""),
        "store_rating_average": payload.get("score", ""),
        "version": payload.get("version", ""),
        "last_updated": iso_datetime(payload.get("updated")),
        "metadata_as_of": datetime.now(timezone.utc).isoformat(),
        "note": "Chỉ số cài đặt là số/dải hiện tại của kho, không lọc riêng theo giai đoạn review.",
    }


# Ghi chú: Google Play công khai chỉ số cài đặt; cần phân biệt với review thu thập trong kỳ.


def request_json(url: str, timeout: int = 30, attempts: int = 3) -> dict[str, Any]:
    """Gọi HTTP GET và retry ngắn cho endpoint JSON công khai."""

    import requests

    headers = {"User-Agent": "Mozilla/5.0 (compatible; AcademicReviewCollector/1.0)"}
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - cần giữ crawler chạy khi một nguồn lỗi.
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Không lấy được dữ liệu sau {attempts} lần: {url}") from last_error


# Ghi chú: Retry nằm ở tầng HTTP để cả metadata và RSS Apple dùng chung một chính sách.


def fetch_apple_metadata(config: AppConfig) -> dict[str, Any]:
    """Lấy rating/review hiện tại của ứng dụng từ iTunes Lookup API."""

    url = f"https://itunes.apple.com/lookup?id={config.apple_id}&country=vn"
    payload = request_json(url)
    results = payload.get("results", [])
    if not results:
        raise RuntimeError(f"Không tìm thấy Apple ID {config.apple_id}")
    item = results[0]
    return {
        "entity": config.entity,
        "platform": "Apple App Store",
        "app_id": config.apple_id,
        "app_name": item.get("trackName", ""),
        "app_url": item.get("trackViewUrl") or apple_store_url(config),
        "installs_display": "Không công bố",
        "min_installs": "",
        "real_installs": "",
        "store_review_count": "",
        "store_rating_count": item.get("userRatingCount", ""),
        "store_rating_average": item.get("averageUserRating", ""),
        "version": item.get("version", ""),
        "last_updated": iso_datetime(item.get("currentVersionReleaseDate")),
        "metadata_as_of": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Apple không công khai lượt tải xuống hoặc tổng số review có nội dung. "
            "userRatingCount được lưu riêng là tổng lượt rating."
        ),
    }


# Ghi chú: iTunes Lookup API cho rating nhưng không cung cấp download count.


def crawl_google_reviews(
    config: AppConfig,
    start_date: date,
    end_date: date,
    max_reviews: int,
    sleep_seconds: float,
) -> list[dict[str, Any]]:
    """Crawl review Google Play theo thứ tự mới nhất và dừng khi vượt mốc ngày."""

    from google_play_scraper import Sort, reviews

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    continuation_token = None

    while len(collected) < max_reviews:
        batch, continuation_token = reviews(
            config.google_id,
            lang="vi",
            country="vn",
            sort=Sort.NEWEST,
            count=min(4_500, max_reviews - len(collected)),
            continuation_token=continuation_token,
        )
        if not batch:
            break

        reached_old_reviews = False
        for item in batch:
            review_dt = to_utc_datetime(item.get("at"))
            if not review_dt:
                continue
            if review_dt.date() < start_date:
                reached_old_reviews = True
                continue
            if review_dt.date() > end_date:
                continue

            review_id = str(item.get("reviewId") or "")
            if review_id and review_id in seen_ids:
                continue
            seen_ids.add(review_id)

            collected.append(
                enrich_review(
                    {
                        "entity": config.entity,
                        "platform": "Google Play",
                        "app_id": config.google_id,
                        "review_id": review_id,
                        "user_name": item.get("userName", ""),
                        "rating": item.get("score", 0),
                        "content": item.get("content", "") or "",
                        "review_date": review_dt.isoformat(),
                        "developer_reply": item.get("replyContent", "") or "",
                        "reply_date": iso_datetime(item.get("repliedAt")),
                        "app_version": item.get("reviewCreatedVersion", "") or "",
                        "thumbs_up_count": item.get("thumbsUpCount", 0) or 0,
                    }
                )
            )

        oldest_date = min(
            (to_utc_datetime(item.get("at")).date() for item in batch if to_utc_datetime(item.get("at"))),
            default=None,
        )
        logging.info(
            "%s - Google Play: đã quét %s review, mốc cũ nhất %s",
            config.entity,
            len(collected),
            oldest_date or "không xác định",
        )

        if reached_old_reviews or continuation_token is None:
            break
        time.sleep(sleep_seconds)

    return collected[:max_reviews]


# Ghi chú: Batch 4.500 giảm số lần gọi mạng; gặp review cũ hơn 01/01/2025 thì dừng phân trang.


def apple_rss_value(item: dict[str, Any], key: str) -> str:
    """Đọc giá trị label từ cấu trúc RSS JSON của Apple."""

    value = item.get(key, {})
    return str(value.get("label", "")) if isinstance(value, dict) else ""


# Ghi chú: RSS Apple bọc phần lớn trường dữ liệu trong object có khóa label.


def crawl_apple_reviews(
    config: AppConfig,
    start_date: date,
    end_date: date,
    max_reviews: int,
    sleep_seconds: float,
) -> list[dict[str, Any]]:
    """Crawl tối đa 10 trang RSS review mới nhất của Apple App Store Việt Nam."""

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    successful_pages = 0
    failed_pages = 0

    for page in range(1, 11):
        if len(collected) >= max_reviews:
            break
        urls = (
            (
                f"https://itunes.apple.com/vn/rss/customerreviews/page={page}/"
                f"id={config.apple_id}/sortby=mostrecent/json"
            ),
            (
                f"https://itunes.apple.com/vn/rss/customerreviews/"
                f"id={config.apple_id}/sortBy=mostRecent/page={page}/json"
            ),
        )

        review_entries: list[dict[str, Any]] = []
        page_succeeded = False
        for url in urls:
            try:
                payload = request_json(url, timeout=10, attempts=2)
                page_succeeded = True
            except RuntimeError:
                continue

            entries = payload.get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
            review_entries = [entry for entry in entries if "im:rating" in entry]
            if review_entries:
                break

        if page_succeeded:
            successful_pages += 1
        else:
            failed_pages += 1
            logging.warning("%s - Apple App Store: không tải được trang %s", config.entity, page)
            continue

        # Apple RSS đôi khi có trang rỗng xen giữa các trang có dữ liệu, nên vẫn quét đủ 10 trang.
        if not review_entries:
            continue

        reached_old_reviews = False
        for item in review_entries:
            review_dt = to_utc_datetime(apple_rss_value(item, "updated"))
            if not review_dt:
                continue
            if review_dt.date() < start_date:
                reached_old_reviews = True
                continue
            if review_dt.date() > end_date:
                continue

            review_id = apple_rss_value(item, "id")
            if review_id and review_id in seen_ids:
                continue
            seen_ids.add(review_id)
            author = item.get("author", {}).get("name", {}).get("label", "")

            collected.append(
                enrich_review(
                    {
                        "entity": config.entity,
                        "platform": "Apple App Store",
                        "app_id": config.apple_id,
                        "review_id": review_id,
                        "user_name": author,
                        "rating": int(apple_rss_value(item, "im:rating") or 0),
                        "content": apple_rss_value(item, "content"),
                        "review_date": review_dt.isoformat(),
                        "developer_reply": "",
                        "reply_date": "",
                        "app_version": apple_rss_value(item, "im:version"),
                        "thumbs_up_count": 0,
                    }
                )
            )

        time.sleep(sleep_seconds)

    if successful_pages == 0:
        raise RuntimeError(f"Không tải được trang Apple RSS nào cho {config.entity}")

    logging.info(
        "%s - Apple App Store: quét %s trang thành công, %s trang lỗi",
        config.entity,
        successful_pages,
        failed_pages,
    )

    return collected[:max_reviews]


# Ghi chú: Quét đủ 10 trang vì RSS Apple có thể trả trang rỗng xen kẽ; tối đa khoảng 500 review/app.


def deduplicate_reviews(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Loại trùng theo platform, app_id và review_id; giữ bản ghi đầu tiên."""

    unique_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (str(row["platform"]), str(row["app_id"]), str(row["review_id"]))
        if row["review_id"] and key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


# Ghi chú: Không gộp review thiếu ID vì không đủ bằng chứng chúng là cùng một bản ghi.


def build_period_summary(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tổng hợp số review, điểm trung bình và tỷ lệ sentiment theo app/kho."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["entity"]), str(row["platform"]))].append(row)

    summary: list[dict[str, Any]] = []
    for (entity, platform), items in sorted(grouped.items()):
        count = len(items)
        ratings = [int(item["rating"]) for item in items]
        sentiment_counts = defaultdict(int)
        for item in items:
            sentiment_counts[str(item["sentiment"])] += 1
        summary.append(
            {
                "entity": entity,
                "platform": platform,
                "collected_review_count": count,
                "period_average_rating": round(sum(ratings) / count, 3) if count else "",
                "negative_count": sentiment_counts["Negative"],
                "neutral_count": sentiment_counts["Neutral"],
                "positive_count": sentiment_counts["Positive"],
                "negative_rate": round(sentiment_counts["Negative"] / count, 4) if count else "",
                "positive_rate": round(sentiment_counts["Positive"] / count, 4) if count else "",
            }
        )
    return summary


# Ghi chú: Điểm trung bình trong kỳ được tính từ review đã crawl, không thay cho điểm lifetime của store.


def build_monthly_trend(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tổng hợp số review và điểm trung bình theo tháng."""

    grouped: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for row in rows:
        review_dt = to_utc_datetime(row["review_date"])
        if review_dt:
            month = review_dt.strftime("%Y-%m")
            grouped[(str(row["entity"]), str(row["platform"]), month)].append(int(row["rating"]))

    return [
        {
            "entity": entity,
            "platform": platform,
            "month": month,
            "review_count": len(ratings),
            "average_rating": round(sum(ratings) / len(ratings), 3),
        }
        for (entity, platform, month), ratings in sorted(grouped.items())
    ]


# Ghi chú: Bảng tháng dùng để nhận diện biến động sau các lần cập nhật ứng dụng.


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    """Ghi CSV UTF-8 BOM để mở tiếng Việt đúng trong Excel."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# Ghi chú: utf-8-sig tránh lỗi font tiếng Việt khi mở CSV bằng Excel trên Windows.


def checkpoint_path(output_dir: Path, entity: str, platform: str) -> Path:
    """Tạo tên file checkpoint an toàn từ tên app và nền tảng."""

    safe_name = re.sub(r"[^a-z0-9]+", "_", strip_accents(f"{entity}_{platform}")).strip("_")
    return output_dir / "checkpoints" / f"{safe_name}.csv"


# Ghi chú: Mỗi app/kho có checkpoint riêng để vẫn giữ dữ liệu nếu lượt sau gặp lỗi.


def record_error(errors: list[dict[str, Any]], config: AppConfig, platform: str, stage: str, exc: Exception) -> None:
    """Chuẩn hóa thông tin lỗi để xuất thành bảng kiểm tra."""

    errors.append(
        {
            "entity": config.entity,
            "platform": platform,
            "stage": stage,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
    )


# Ghi chú: Crawler tiếp tục với app khác thay vì mất toàn bộ phiên chạy vì một nguồn lỗi.


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Đọc tham số dòng lệnh và đặt giới hạn crawl an toàn."""

    parser = argparse.ArgumentParser(description="Crawl review 5 ứng dụng tài chính tại Việt Nam.")
    parser.add_argument("--start-date", type=parse_date, default=date(2025, 1, 1))
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    parser.add_argument("--max-google-reviews", type=int, default=1_000_000)
    parser.add_argument("--max-apple-reviews", type=int, default=500)
    parser.add_argument("--sleep-seconds", type=float, default=1.5)
    parser.add_argument("--output", type=Path, default=Path("output/raw/app_reviews"))
    args = parser.parse_args(argv)
    if args.start_date > args.end_date:
        parser.error("start-date phải nhỏ hơn hoặc bằng end-date")
    if args.max_google_reviews <= 0 or args.max_apple_reviews <= 0:
        parser.error("Giới hạn review phải lớn hơn 0")
    return args


# Ghi chú: Có thể truyền end-date cố định để tái lập đúng cùng một kỳ dữ liệu khi nộp bài.


def run(args: argparse.Namespace) -> None:
    """Điều phối lấy metadata, crawl review, checkpoint và xuất các bảng CSV."""

    output_dir: Path = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_rows: list[dict[str, Any]] = []
    all_reviews: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for config in APPS:
        logging.info("Đang xử lý %s", config.entity)

        for platform, fetcher in (
            ("Google Play", fetch_google_metadata),
            ("Apple App Store", fetch_apple_metadata),
        ):
            try:
                metadata_rows.append(fetcher(config))
            except Exception as exc:  # noqa: BLE001
                logging.exception("Lỗi metadata %s - %s", config.entity, platform)
                record_error(errors, config, platform, "metadata", exc)

        crawlers = (
            ("Google Play", crawl_google_reviews, args.max_google_reviews),
            ("Apple App Store", crawl_apple_reviews, args.max_apple_reviews),
        )
        for platform, crawler, limit in crawlers:
            try:
                rows = crawler(config, args.start_date, args.end_date, limit, args.sleep_seconds)
                all_reviews.extend(rows)
                write_csv(checkpoint_path(output_dir, config.entity, platform), rows, REVIEW_FIELDS)
                logging.info("%s - %s: %s review", config.entity, platform, len(rows))
            except Exception as exc:  # noqa: BLE001
                logging.exception("Lỗi review %s - %s", config.entity, platform)
                record_error(errors, config, platform, "reviews", exc)

    clean_reviews = deduplicate_reviews(all_reviews)
    summary_rows = build_period_summary(clean_reviews)
    monthly_rows = build_monthly_trend(clean_reviews)

    metadata_fields = (
        "entity",
        "platform",
        "app_id",
        "app_name",
        "app_url",
        "installs_display",
        "min_installs",
        "real_installs",
        "store_review_count",
        "store_rating_count",
        "store_rating_average",
        "version",
        "last_updated",
        "metadata_as_of",
        "note",
    )
    summary_fields = (
        "entity",
        "platform",
        "collected_review_count",
        "period_average_rating",
        "negative_count",
        "neutral_count",
        "positive_count",
        "negative_rate",
        "positive_rate",
    )
    monthly_fields = ("entity", "platform", "month", "review_count", "average_rating")
    error_fields = ("entity", "platform", "stage", "error_type", "message")

    write_csv(output_dir / "store_metrics.csv", metadata_rows, metadata_fields)
    write_csv(output_dir / "reviews_2025_to_now.csv", clean_reviews, REVIEW_FIELDS)
    write_csv(output_dir / "period_summary.csv", summary_rows, summary_fields)
    write_csv(output_dir / "monthly_trend.csv", monthly_rows, monthly_fields)
    write_csv(output_dir / "crawl_errors.csv", errors, error_fields)

    run_metadata = {
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "max_google_reviews_per_app": args.max_google_reviews,
        "max_apple_reviews_per_app": args.max_apple_reviews,
        "review_rows": len(clean_reviews),
        "error_rows": len(errors),
        "apps": [asdict(config) for config in APPS],
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# Ghi chú: Hàm run tạo cả dữ liệu thô, bảng tổng hợp, xu hướng tháng, lỗi và metadata phiên chạy.


def main() -> None:
    """Điểm vào chương trình."""

    configure_console_utf8()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run(parse_args())


# Ghi chú: Giữ main ngắn để toàn bộ logic có thể import và kiểm thử độc lập.


if __name__ == "__main__":
    main()
