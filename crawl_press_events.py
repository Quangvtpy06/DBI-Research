"""Thu thập tin báo chí, giải thưởng và sự kiện ngân hàng số từ 2025 đến nay.

Phạm vi cố định: ZaloPay, VPBank, VCB (Vietcombank), HDBank và ACB.

Thiết kế tham khảo dự án MIT ``Tumiqa/vn-annual-report-miner``:
- tìm kiếm đa nguồn và website chính thức;
- dùng HTTP session có retry/connection pooling;
- trích toàn văn bằng Trafilatura, BeautifulSoup làm phương án dự phòng;
- lọc ngày, xác nhận đúng doanh nghiệp, phân loại và loại trùng.

Chạy:
    python crawl_press_events.py --output output/raw/press_1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import json
import logging
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, quote_plus, unquote, urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import trafilatura
except ImportError:  # Trafilatura là lớp tăng chất lượng, BeautifulSoup vẫn chạy độc lập.
    trafilatura = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # Có fallback thư viện chuẩn nếu môi trường chưa cài BeautifulSoup.
    BeautifulSoup = None


REFERENCE_REPOSITORY = "https://github.com/Tumiqa/vn-annual-report-miner"


@dataclass(frozen=True)
class EntityConfig:
    """Thông tin nhận diện một đơn vị trong phạm vi nghiên cứu."""

    entity: str
    primary_name: str
    ticker: str
    aliases: tuple[str, ...]
    official_domain: str


# Ghi chú: Alias dài được ưu tiên để tránh nhầm ticker ngắn với tổ chức khác.


@dataclass(frozen=True)
class Candidate:
    """Một liên kết ứng viên thu được từ RSS tìm kiếm."""

    entity: str
    category_hint: str
    query: str
    search_channel: str
    title: str
    url: str
    snippet: str
    published_date: str
    source_name: str


# Ghi chú: Candidate chỉ là đầu vào; bài viết chỉ được giữ sau bước xác nhận nội dung.


ENTITIES: tuple[EntityConfig, ...] = (
    EntityConfig(
        "ZaloPay",
        "ZaloPay",
        "ZALOPAY",
        ("ZaloPay", "Ví ZaloPay", "Công ty Cổ phần ZION", "ZION"),
        "zalopay.vn",
    ),
    EntityConfig(
        "VPBank",
        "VPBank",
        "VPB",
        ("VPBank", "Ngân hàng Việt Nam Thịnh Vượng", "Ngân hàng TMCP Việt Nam Thịnh Vượng"),
        "vpbank.com.vn",
    ),
    EntityConfig(
        "VCB",
        "Vietcombank",
        "VCB",
        ("Vietcombank", "Ngân hàng Ngoại thương Việt Nam", "Ngân hàng TMCP Ngoại thương Việt Nam"),
        "vietcombank.com.vn",
    ),
    EntityConfig(
        "HDBank",
        "HDBank",
        "HDB",
        ("HDBank", "Ngân hàng Phát triển Thành phố Hồ Chí Minh", "Ngân hàng TMCP Phát triển TP.HCM"),
        "hdbank.com.vn",
    ),
    EntityConfig(
        "ACB",
        "ACB",
        "ACB",
        ("Ngân hàng Á Châu", "Ngân hàng TMCP Á Châu", "Asia Commercial Bank", "ACB"),
        "acb.com.vn",
    ),
)

CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "giai_thuong_ngan_hang_so": (
        "giải thưởng",
        "vinh danh",
        "được trao giải",
        "award",
        "tốt nhất",
        "xuất sắc",
        "bank of the year",
        "digital bank of the year",
        "ngân hàng bán lẻ số",
        "ứng dụng xuất sắc",
    ),
    "su_kien_bai_phat_bieu": (
        "diễn đàn",
        "hội thảo",
        "tọa đàm",
        "forum",
        "phát biểu",
        "tham luận",
        "chia sẻ tại",
        "vietnam banking forum",
        "banking vietnam",
        "giám đốc khối ngân hàng số",
        "giám đốc công nghệ",
        "chief information officer",
        "cio",
    ),
    "thong_cao_tin_chuyen_doi_so": (
        "thông cáo báo chí",
        "công bố",
        "ra mắt",
        "giới thiệu",
        "ký kết",
        "hợp tác",
        "triển khai",
        "nâng cấp",
        "cải tiến",
        "cải thiện",
        "đổi mới",
        "tăng cường",
        "dẫn đầu",
        "thành công",
        "chính thức",
    ),
    "su_co_rui_ro_phan_hoi_tieu_cuc": (
        "sự cố",
        "gián đoạn",
        "bị lỗi",
        "lỗi ứng dụng",
        "không thể giao dịch",
        "không giao dịch được",
        "mất tiền",
        "trừ tiền",
        "khóa tài khoản",
        "lộ dữ liệu",
        "rò rỉ dữ liệu",
        "tấn công mạng",
        "lừa đảo",
        "gian lận",
        "mạo danh",
        "khiếu nại",
        "phản ánh",
        "bức xúc",
        "cảnh báo",
        "xử phạt",
        "vi phạm",
        "rủi ro",
    ),
}

DIGITAL_TERMS: tuple[str, ...] = (
    "ngân hàng số",
    "digital banking",
    "chuyển đổi số",
    "công nghệ số",
    "ứng dụng ngân hàng",
    "mobile banking",
    "app ngân hàng",
    "bảo mật",
    "an ninh mạng",
    "sinh trắc học",
    "trí tuệ nhân tạo",
    "artificial intelligence",
    "dữ liệu lớn",
    "big data",
    "điện toán đám mây",
    "cloud",
    "core banking",
    "open banking",
    "thanh toán số",
    "trải nghiệm số",
    "hệ sinh thái số",
    "fintech",
    "AI",
    "internet banking",
    "dịch vụ trực tuyến",
    "giao dịch trực tuyến",
    "lỗi ứng dụng",
    "gián đoạn giao dịch",
    "không giao dịch được",
    "OTP",
    "eKYC",
    "VNeID",
    "QR code",
    "công nghệ",
    "ứng dụng",
    "nền tảng",
    "hệ thống số",
    "dịch vụ số",
    "trực tuyến",
    "số hóa",
)

EXPERIENCE_TERMS: tuple[str, ...] = (
    "trải nghiệm người dùng",
    "trải nghiệm khách hàng",
    "tối ưu trải nghiệm",
    "giao diện",
    "UI",
    "UX",
    "dễ sử dụng",
    "tiện lợi",
    "nhanh",
    "mượt",
    "chậm",
    "lag",
    "treo",
    "crash",
    "đăng nhập",
    "chuyển tiền",
    "giao dịch",
)

TECH_SCOPE_TERMS: tuple[str, ...] = tuple(dict.fromkeys((*DIGITAL_TERMS, *EXPERIENCE_TERMS)))
CATEGORY_TERMS["cong_nghe_trai_nghiem_so"] = TECH_SCOPE_TERMS

TRUSTED_NEWS_DOMAINS: tuple[str, ...] = (
    "baochinhphu.vn",
    "chinhphu.vn",
    "sbv.gov.vn",
    "tapchinganhang.gov.vn",
    "thoibaonganhang.vn",
    "nhandan.vn",
    "qdnd.vn",
    "vtv.vn",
    "vov.vn",
    "vnexpress.net",
    "vietnamnet.vn",
    "tuoitre.vn",
    "thanhnien.vn",
    "dantri.com.vn",
    "laodong.vn",
    "nld.com.vn",
    "sggp.org.vn",
    "vneconomy.vn",
    "baodautu.vn",
    "tinnhanhchungkhoan.vn",
    "diendandoanhnghiep.vn",
    "theleader.vn",
    "vietnamfinance.vn",
    "vietstock.vn",
    "cafef.vn",
    "vietnamplus.vn",
    "baotintuc.vn",
    "plo.vn",
    "tienphong.vn",
    "cand.com.vn",
    "kinhtedothi.vn",
    "vnbusiness.vn",
    "vir.com.vn",
    "ictvietnam.vn",
    "antoanthongtin.vn",
    "doanhnhansaigon.vn",
)

ARTICLE_FIELDS: tuple[str, ...] = (
    "entity",
    "ticker",
    "category",
    "title",
    "published_date",
    "published_year",
    "source_name",
    "source_domain",
    "url",
    "official_source",
    "author",
    "sapo",
    "content",
    "word_count",
    "matched_category_terms",
    "matched_digital_terms",
    "matched_entity_aliases",
    "leadership_role_terms",
    "relevance_score",
    "extraction_status",
    "search_channel",
    "search_query",
    "content_hash",
    "collected_at_utc",
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.7,en;q=0.6",
}


def configure_console_utf8() -> None:
    """Ưu tiên UTF-8 cho log tiếng Việt trên Windows."""

    for stream in (getattr(__import__("sys"), "stdout"), getattr(__import__("sys"), "stderr")):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


# Ghi chú: Hàm chỉ đổi cách hiển thị terminal, không làm thay đổi nội dung CSV.


def build_session() -> requests.Session:
    """Tạo HTTP session dùng lại kết nối và tự retry lỗi tạm thời."""

    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET",)),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=30)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session


# Ghi chú: Connection pooling giảm thời gian khi phải đọc nhiều bài từ cùng một tòa soạn.


def normalize_text(value: str) -> str:
    """Chuẩn hóa chữ thường, bỏ dấu và khoảng trắng để so khớp ổn định."""

    decomposed = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_marks.lower()).strip()


# Ghi chú: Dữ liệu xuất vẫn giữ nguyên tiếng Việt; bản không dấu chỉ dùng nội bộ.


def parse_date(value: str) -> date:
    """Đọc ngày ở định dạng YYYY-MM-DD."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Ngày phải có định dạng YYYY-MM-DD") from exc


# Ghi chú: Kiểu date giúp so sánh biên thời gian mà không phụ thuộc múi giờ nguồn báo.


def parse_any_date(value: str) -> str:
    """Chuyển các dạng ngày phổ biến về YYYY-MM-DD; trả rỗng nếu không chắc chắn."""

    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass

    patterns = (
        (r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", (1, 2, 3)),
        (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", (3, 2, 1)),
    )
    for pattern, order in patterns:
        match = re.search(pattern, raw)
        if not match:
            continue
        parts = match.groups()
        try:
            year, month, day = (int(parts[index - 1]) for index in order)
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    return ""


# Ghi chú: Không suy đoán năm nếu trang không cung cấp bằng chứng ngày rõ ràng.


def canonical_url(url: str) -> str:
    """Bỏ tham số theo dõi và fragment để phục vụ loại trùng."""

    parsed = urlparse((url or "").strip())
    clean_path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), clean_path, "", "", ""))


# Ghi chú: URL gốc vẫn được lưu; canonical URL chỉ dùng làm khóa so sánh.


def unwrap_bing_url(url: str) -> str:
    """Lấy URL nhà xuất bản từ liên kết chuyển tiếp của Bing News."""

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    target = query.get("url", [""])[0]
    return unquote(target) if target.startswith(("http://", "https://")) else url


# Ghi chú: Giải URL tại chỗ giúp crawler đọc thẳng bài báo thay vì trang chuyển tiếp Bing.


def rss_items(session: requests.Session, url: str, timeout: int) -> list[dict[str, str]]:
    """Tải một RSS feed và trả danh sách trường cơ bản của từng item."""

    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items: list[dict[str, str]] = []
    for node in root.findall(".//item"):
        source_node = node.find("source")
        items.append(
            {
                "title": (node.findtext("title") or "").strip(),
                "link": (node.findtext("link") or "").strip(),
                "description": (node.findtext("description") or "").strip(),
                "pub_date": (node.findtext("pubDate") or "").strip(),
                "source": ((source_node.text or "").strip() if source_node is not None else ""),
            }
        )
    return items


# Ghi chú: Chỉ dùng thư viện XML chuẩn, không cần thêm feedparser.


def strip_html(value: str) -> str:
    """Chuyển một đoạn HTML ngắn thành văn bản bằng thư viện chuẩn."""

    cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", value or "")
    cleaned = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", html_lib.unescape(cleaned)).strip()


# Ghi chú: Hàm fallback giúp script vẫn chạy khi pip chưa cài BeautifulSoup/Trafilatura.


def regex_meta_content(html: str, key: str) -> str:
    """Đọc content của thẻ meta bằng regex cho chế độ không có BeautifulSoup."""

    escaped = re.escape(key)
    patterns = (
        rf'<meta[^>]+(?:name|property|itemprop)=["\']{escaped}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property|itemprop)=["\']{escaped}["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I)
        if match:
            return html_lib.unescape(match.group(1)).strip()
    return ""


# Ghi chú: Chỉ dùng cho metadata phổ biến; BeautifulSoup vẫn là lựa chọn chính khi có sẵn.


def extract_page_stdlib(html: str) -> dict[str, Any]:
    """Trích xuất tối thiểu bằng regex/HTML unescape khi thiếu thư viện ngoài."""

    title = regex_meta_content(html, "og:title") or regex_meta_content(html, "twitter:title")
    if not title:
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
        title = strip_html(title_match.group(1)) if title_match else ""
    sapo = regex_meta_content(html, "og:description") or regex_meta_content(html, "description")
    author = regex_meta_content(html, "author") or regex_meta_content(html, "article:author")
    raw_date = (
        regex_meta_content(html, "article:published_time")
        or regex_meta_content(html, "datePublished")
        or regex_meta_content(html, "pubdate")
    )
    return {
        "title": title,
        "published_date": parse_any_date(raw_date),
        "author": author,
        "sapo": sapo,
        "content": strip_html(html),
    }


# Ghi chú: Chế độ chuẩn vẫn giữ được schema đầu ra, dù khả năng loại menu kém hơn Trafilatura.


def build_search_specs(entity: EntityConfig) -> list[tuple[str, str, str]]:
    """Tạo truy vấn Bing News và Bing Web cho bốn nhóm thông tin cần theo dõi."""

    category_queries = {
        "giai_thuong_ngan_hang_so": (
            "giải thưởng ngân hàng số ứng dụng bảo mật",
            "vinh danh công nghệ số tốt nhất",
        ),
        "su_kien_bai_phat_bieu": (
            "diễn đàn hội thảo ngân hàng số",
            "phát biểu CIO lãnh đạo chuyển đổi số",
        ),
        "thong_cao_tin_chuyen_doi_so": (
            "ra mắt hợp tác công nghệ ngân hàng số",
            "thông cáo báo chí chuyển đổi số",
        ),
        "su_co_rui_ro_phan_hoi_tieu_cuc": (
            "sự cố lỗi ứng dụng ngân hàng số gián đoạn giao dịch",
            "cảnh báo lừa đảo mất tiền bảo mật dữ liệu",
            "khiếu nại xử phạt dịch vụ ngân hàng số",
        ),
        "cong_nghe_trai_nghiem_so": (
            "ứng dụng ngân hàng số trải nghiệm người dùng",
            "AI cloud core banking bảo mật sinh trắc học",
            "mobile banking giao dịch trực tuyến QR OTP eKYC",
        ),
    }
    specs: list[tuple[str, str, str]] = []
    for category, phrases in category_queries.items():
        for phrase in phrases:
            specs.append((category, "bing_news", f'{entity.primary_name} {phrase}'))
        specs.append(
            (
                category,
                "bing_web",
                f'site:{entity.official_domain} {entity.primary_name} {phrases[0]}',
            )
        )
    return specs


# Ghi chú: Truy vấn ngắn, tự nhiên cho độ bao phủ Bing tốt hơn biểu thức OR lồng nhau.


def hostname(url: str) -> str:
    """Lấy hostname chữ thường và bỏ tiền tố www từ một URL."""

    return (urlparse(url).hostname or "").lower().removeprefix("www.")


# Ghi chú: Chỉ dùng hostname, không dựa vào tên nguồn do RSS tự khai báo.


def domain_matches(host: str, allowed_domain: str) -> bool:
    """Kiểm tra hostname là đúng miền cho phép hoặc một subdomain của miền đó."""

    clean_host = host.lower().strip(".")
    clean_allowed = allowed_domain.lower().strip(".")
    return clean_host == clean_allowed or clean_host.endswith(f".{clean_allowed}")


# Ghi chú: So khớp theo ranh giới dấu chấm tránh miền giả dạng như fake-vpbank.com.vn.


def is_trusted_source(url: str, entity: EntityConfig) -> bool:
    """Chỉ chấp nhận báo thuộc danh sách uy tín hoặc website chính thức của ngân hàng."""

    host = hostname(url)
    allowed_domains = (entity.official_domain, *TRUSTED_NEWS_DOMAINS)
    return any(domain_matches(host, domain) for domain in allowed_domains)


# Ghi chú: MSN, Báo Mới, blog và website không nằm trong danh sách sẽ bị loại trước khi tải bài.


def prefilter_candidate(candidate: Candidate, entity: EntityConfig) -> tuple[bool, str]:
    """Lọc nhanh URL và metadata RSS trước khi gửi yêu cầu tải toàn văn."""

    if not is_trusted_source(candidate.url, entity):
        return False, "nguon_khong_duoc_phep"

    headline_text = "\n".join((candidate.title, candidate.snippet))
    official_page = domain_matches(hostname(candidate.url), entity.official_domain)
    if not official_page and not confirm_entity(entity, headline_text):
        return False, "khong_xac_nhan_duoc_ngan_hang"

    if not matched_terms(headline_text, TECH_SCOPE_TERMS):
        return False, "thieu_tu_khoa_cong_nghe_trai_nghiem"
    return True, "giu_lai"


# Ghi chú: Sentiment chưa bị ép ở bước này; tích cực, tiêu cực và trung tính được phân loại sau khi đọc bài.


def search_candidates(
    session: requests.Session,
    entity: EntityConfig,
    max_results_per_query: int,
    timeout: int,
) -> tuple[list[Candidate], list[dict[str, str]]]:
    """Tìm các liên kết ứng viên cho một đơn vị qua RSS của Bing."""

    candidates: list[Candidate] = []
    errors: list[dict[str, str]] = []
    rejected: Counter[str] = Counter()
    for category, channel, query in build_search_specs(entity):
        encoded = quote_plus(query)
        if channel == "bing_news":
            search_url = f"https://www.bing.com/news/search?q={encoded}&format=RSS&mkt=vi-VN"
        else:
            search_url = f"https://www.bing.com/search?q={encoded}&format=rss&mkt=vi-VN"
        try:
            items = rss_items(session, search_url, timeout)
        except Exception as exc:  # noqa: BLE001 - lỗi được ghi riêng để phiên crawl vẫn tiếp tục.
            errors.append(
                {
                    "entity": entity.entity,
                    "stage": "search",
                    "source": channel,
                    "url": search_url,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue

        for item in items[:max_results_per_query]:
            article_url = unwrap_bing_url(item["link"])
            if not article_url.startswith(("http://", "https://")):
                continue
            snippet = (
                BeautifulSoup(item["description"], "html.parser").get_text(" ", strip=True)
                if BeautifulSoup is not None
                else strip_html(item["description"])
            )
            source_name = item["source"] or urlparse(article_url).netloc
            candidate = Candidate(
                entity=entity.entity,
                category_hint=category,
                query=query,
                search_channel=channel,
                title=item["title"],
                url=article_url,
                snippet=snippet,
                published_date=parse_any_date(item["pub_date"]),
                source_name=source_name,
            )
            keep, reason = prefilter_candidate(candidate, entity)
            if keep:
                candidates.append(candidate)
            else:
                rejected[reason] += 1
    logging.info(
        "%s: lọc RSS giữ %s link, loại %s link (%s)",
        entity.entity,
        len(candidates),
        sum(rejected.values()),
        ", ".join(f"{reason}={count}" for reason, count in sorted(rejected.items())) or "không có",
    )
    return candidates, errors


# Ghi chú: Ngày RSS chỉ là dự phòng; ngày trong trang bài viết được ưu tiên nếu tìm thấy.


def extract_page(html: str, url: str) -> dict[str, Any]:
    """Trích title, ngày, tác giả, sapo và toàn văn sạch từ HTML."""

    if BeautifulSoup is None:
        return extract_page_stdlib(html)

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(("script", "style", "noscript", "iframe", "svg", "form")):
        tag.decompose()

    def meta_content(*keys: tuple[str, str]) -> str:
        for attr, value in keys:
            node = soup.find("meta", attrs={attr: value})
            if node and node.get("content"):
                return str(node["content"]).strip()
        return ""

    title = meta_content(("property", "og:title"), ("name", "twitter:title"))
    if not title:
        heading = soup.find("h1")
        title = heading.get_text(" ", strip=True) if heading else ""
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    sapo = meta_content(("property", "og:description"), ("name", "description"))
    author = meta_content(("name", "author"), ("property", "article:author"))
    raw_date = meta_content(
        ("property", "article:published_time"),
        ("name", "pubdate"),
        ("name", "date"),
        ("itemprop", "datePublished"),
    )
    if not raw_date:
        time_node = soup.find("time")
        if time_node:
            raw_date = str(time_node.get("datetime") or time_node.get_text(" ", strip=True))

    body_text = ""
    if trafilatura is not None:
        try:
            body_text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            ) or ""
        except Exception:  # noqa: BLE001 - tiếp tục bằng BeautifulSoup.
            body_text = ""

    if len(body_text) < 120:
        container = soup.find("article") or soup.find("main") or soup.body or soup
        paragraphs = [
            node.get_text(" ", strip=True)
            for node in container.find_all(("p", "h2", "h3", "li", "blockquote"))
            if len(node.get_text(" ", strip=True)) >= 25
        ]
        body_text = "\n\n".join(paragraphs)

    body_text = re.sub(r"[ \t]+", " ", body_text)
    body_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()
    return {
        "title": title.strip(),
        "published_date": parse_any_date(raw_date),
        "author": author.strip(),
        "sapo": sapo.strip(),
        "content": body_text,
    }


# Ghi chú: Trafilatura tăng chất lượng; fallback BeautifulSoup giúp script không phụ thuộc một bộ trích xuất.


def matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    """Trả danh sách từ/cụm từ thực sự xuất hiện trong văn bản."""

    normalized = normalize_text(text)
    matches: list[str] = []
    for term in terms:
        normalized_term = normalize_text(term)
        found = (
            bool(re.search(rf"\b{re.escape(normalized_term)}\b", normalized))
            if len(normalized_term) <= 3
            else normalized_term in normalized
        )
        if found:
            matches.append(term)
    return matches


# Ghi chú: Kết quả match được lưu ra CSV để người đọc kiểm tra lý do phân loại.


def confirm_entity(entity: EntityConfig, text: str) -> list[str]:
    """Xác nhận bài có nhắc đúng đơn vị, hạn chế nhầm ticker hoặc công ty chứng khoán."""

    normalized = normalize_text(text)
    aliases = [alias for alias in entity.aliases if normalize_text(alias) in normalized]
    if entity.entity == "VPBank" and "vpbanks" in normalized and "vpbank " not in normalized:
        return []
    if entity.entity == "VCB" and not any(
        marker in normalized for marker in ("vietcombank", "ngan hang ngoai thuong")
    ):
        return []
    if entity.entity == "ACB" and "acb" in normalized and not any(
        marker in normalized
        for marker in ("ngan hang", "bank", "acb one", "asia commercial bank", "ngan hang a chau")
    ):
        return []
    return aliases


# Ghi chú: VCB và ACB là viết tắt dễ trùng nên bắt buộc có tín hiệu tên ngân hàng đi kèm.


def classify_article(
    headline_text: str,
    body_text: str,
    category_hint: str,
) -> tuple[str, list[str], list[str], list[str], int]:
    """Phân loại bài và tính điểm liên quan dựa trên dấu vết có thể giải thích."""

    headline_category_matches = {
        category: matched_terms(headline_text, terms) for category, terms in CATEGORY_TERMS.items()
    }
    body_category_matches = {
        category: matched_terms(body_text, terms) for category, terms in CATEGORY_TERMS.items()
    }
    headline_digital = matched_terms(headline_text, TECH_SCOPE_TERMS)
    body_digital = matched_terms(body_text, TECH_SCOPE_TERMS)
    role_terms = matched_terms(
        headline_text + "\n" + body_text,
        (
            "giám đốc khối ngân hàng số",
            "giám đốc công nghệ",
            "chief information officer",
            "cio",
            "chief digital officer",
            "cdo",
            "giám đốc chuyển đổi số",
        ),
    )
    ranked = sorted(
        CATEGORY_TERMS,
        key=lambda key: (
            len(headline_category_matches[key]) * 3 + len(body_category_matches[key]),
            key == category_hint,
        ),
        reverse=True,
    )
    category = ranked[0] if ranked else category_hint
    chosen_matches = list(
        dict.fromkeys(headline_category_matches.get(category, []) + body_category_matches.get(category, []))
    )
    digital_matches = list(dict.fromkeys(headline_digital + body_digital))
    score = (
        min(6, len(headline_category_matches.get(category, [])) * 3)
        + min(3, len(body_category_matches.get(category, [])))
        + min(4, len(headline_digital) * 2)
        + min(2, len(body_digital))
    )
    if category == category_hint and headline_category_matches.get(category):
        score += 1
    if category == "su_kien_bai_phat_bieu" and role_terms:
        score += 2

    # Không cho nội dung điều hướng/footer tự tạo kết quả dương tính giả.
    has_headline_category = bool(headline_category_matches.get(category))
    has_headline_digital = bool(headline_digital)
    if not has_headline_category and not has_headline_digital and not role_terms:
        score = 0
    if category == "su_kien_bai_phat_bieu":
        if not has_headline_category or not (has_headline_digital or role_terms):
            score = min(score, 3)
    if category == "giai_thuong_ngan_hang_so" and not has_headline_category:
        score = min(score, 3)
    if category == "thong_cao_tin_chuyen_doi_so":
        if not (has_headline_category and has_headline_digital) and len(body_digital) < 2:
            score = min(score, 3)
    if category == "su_co_rui_ro_phan_hoi_tieu_cuc" and not has_headline_category:
        score = min(score, 3)
    return category, chosen_matches, digital_matches, role_terms, score


# Ghi chú: Tin tiêu cực phải có dấu hiệu sự cố/rủi ro ngay ở tiêu đề hoặc sapo để giảm nhiễu từ cuối trang.


def fetch_candidate(
    session: requests.Session,
    candidate: Candidate,
    entity: EntityConfig,
    start_date: date,
    end_date: date,
    timeout: int,
    min_relevance_score: int,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """Tải, xác nhận và chuẩn hóa một bài viết ứng viên."""

    page: dict[str, Any] = {}
    fetch_error: Exception | None = None
    try:
        response = session.get(candidate.url, timeout=timeout)
        response.raise_for_status()
        page = extract_page(response.text, response.url)
        final_url = response.url
    except Exception as exc:  # noqa: BLE001 - vẫn có thể dùng metadata RSS.
        fetch_error = exc
        final_url = candidate.url

    if not is_trusted_source(final_url, entity):
        return None, None

    title = str(page.get("title") or candidate.title).strip()
    content = str(page.get("content") or "").strip()
    sapo = str(page.get("sapo") or candidate.snippet).strip()
    published_date = str(page.get("published_date") or candidate.published_date).strip()
    parsed_published = parse_date(published_date) if published_date else None
    if not parsed_published or not (start_date <= parsed_published <= end_date):
        return None, None

    headline_text = "\n".join((title, sapo))
    body_text = content[:6000]
    combined = "\n".join((headline_text, body_text))
    entity_matches = confirm_entity(entity, combined)
    if not entity_matches and domain_matches(hostname(final_url), entity.official_domain):
        entity_matches = [f"official:{entity.official_domain}"]
    if not entity_matches:
        return None, None

    category, category_matches, digital_matches, role_terms, score = classify_article(
        headline_text, body_text, candidate.category_hint
    )
    if not category_matches or not digital_matches or score < min_relevance_score:
        return None, None

    clean_url = canonical_url(final_url)
    source_domain = hostname(clean_url)
    content_for_hash = normalize_text(title + "\n" + (content[:3000] or sapo))
    row: dict[str, Any] = {
        "entity": entity.entity,
        "ticker": entity.ticker,
        "category": category,
        "title": title,
        "published_date": published_date,
        "published_year": parsed_published.year,
        "source_name": candidate.source_name,
        "source_domain": source_domain,
        "url": clean_url,
        "official_source": domain_matches(source_domain, entity.official_domain),
        "author": str(page.get("author") or ""),
        "sapo": sapo,
        "content": content,
        "word_count": len(content.split()),
        "matched_category_terms": " | ".join(category_matches),
        "matched_digital_terms": " | ".join(digital_matches),
        "matched_entity_aliases": " | ".join(entity_matches),
        "leadership_role_terms": " | ".join(role_terms),
        "relevance_score": score,
        "extraction_status": "full_text" if content else "metadata_only",
        "search_channel": candidate.search_channel,
        "search_query": candidate.query,
        "content_hash": hashlib.sha256(content_for_hash.encode("utf-8")).hexdigest(),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    error = None
    if fetch_error is not None:
        error = {
            "entity": entity.entity,
            "stage": "fetch_article_metadata_kept",
            "source": candidate.source_name,
            "url": candidate.url,
            "error_type": type(fetch_error).__name__,
            "message": str(fetch_error),
        }
    return row, error


# Ghi chú: Khi trang chặn bot, metadata RSS đạt đủ điều kiện vẫn được giữ và đánh dấu metadata_only.


def title_key(title: str) -> str:
    """Tạo khóa tiêu đề để loại trùng bài đăng lại giữa nhiều nguồn."""

    normalized = normalize_text(title)
    normalized = re.sub(r"\b(vietnamnet|cafef|cafebiz|vneconomy|vnexpress)\b", "", normalized)
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


# Ghi chú: Khóa tiêu đề không thay thế tiêu đề gốc được lưu trong dữ liệu.


def deduplicate_articles(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Loại trùng theo URL, hash nội dung và tiêu đề trong cùng một đơn vị."""

    selected: dict[tuple[str, str], dict[str, Any]] = {}
    seen_urls: set[tuple[str, str]] = set()
    seen_hashes: set[tuple[str, str]] = set()
    for row in sorted(rows, key=lambda item: (item["entity"], item["published_date"]), reverse=True):
        entity = str(row["entity"])
        url_key = (entity, canonical_url(str(row["url"])))
        hash_key = (entity, str(row["content_hash"]))
        name_key = (entity, title_key(str(row["title"])))
        if url_key in seen_urls or hash_key in seen_hashes:
            continue
        existing = selected.get(name_key)
        if existing:
            if int(row["word_count"]) > int(existing["word_count"]):
                selected[name_key] = row
            continue
        selected[name_key] = row
        seen_urls.add(url_key)
        seen_hashes.add(hash_key)
    return sorted(selected.values(), key=lambda item: (item["entity"], item["published_date"]), reverse=True)


# Ghi chú: Khi trùng tiêu đề, bản có toàn văn dài hơn được ưu tiên.


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> None:
    """Ghi CSV UTF-8 BOM để Excel mở tiếng Việt đúng dấu."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# Ghi chú: extrasaction=ignore cho phép bổ sung trường nội bộ mà không phá schema đầu ra.


def build_summary(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tổng hợp số bài theo đơn vị và nhóm nội dung."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["entity"])].append(row)
    summary: list[dict[str, Any]] = []
    for entity in (item.entity for item in ENTITIES):
        entity_rows = grouped.get(entity, [])
        categories = Counter(str(row["category"]) for row in entity_rows)
        summary.append(
            {
                "entity": entity,
                "total_articles": len(entity_rows),
                "award_articles": categories["giai_thuong_ngan_hang_so"],
                "event_speech_articles": categories["su_kien_bai_phat_bieu"],
                "press_digital_articles": categories["thong_cao_tin_chuyen_doi_so"],
                "negative_risk_articles": categories["su_co_rui_ro_phan_hoi_tieu_cuc"],
                "technology_experience_articles": categories["cong_nghe_trai_nghiem_so"],
                "official_source_articles": sum(bool(row["official_source"]) for row in entity_rows),
                "full_text_articles": sum(row["extraction_status"] == "full_text" for row in entity_rows),
                "first_published_date": min((row["published_date"] for row in entity_rows), default=""),
                "last_published_date": max((row["published_date"] for row in entity_rows), default=""),
            }
        )
    return summary


# Ghi chú: Bảng summary phục vụ so sánh nhanh, còn bài gốc vẫn nằm trong file chi tiết.


def crawl_entity(
    session: requests.Session,
    entity: EntityConfig,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Điều phối tìm kiếm và trích xuất song song cho một đơn vị."""

    candidates, errors = search_candidates(
        session, entity, args.max_results_per_query, args.timeout_seconds
    )
    unique_candidates: dict[str, Candidate] = {}
    for candidate in candidates:
        unique_candidates.setdefault(canonical_url(candidate.url), candidate)
    logging.info("%s: tìm thấy %s URL ứng viên", entity.entity, len(unique_candidates))

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                fetch_candidate,
                session,
                candidate,
                entity,
                args.start_date,
                args.end_date,
                args.timeout_seconds,
                args.min_relevance_score,
            ): candidate
            for candidate in unique_candidates.values()
        }
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                row, error = future.result()
            except Exception as exc:  # noqa: BLE001 - giữ các bài khác khi một worker lỗi.
                errors.append(
                    {
                        "entity": entity.entity,
                        "stage": "process_article",
                        "source": candidate.source_name,
                        "url": candidate.url,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                continue
            if error:
                errors.append(error)
            if row:
                rows.append(row)

    rows = deduplicate_articles(rows)
    if args.max_articles_per_entity > 0:
        rows = rows[: args.max_articles_per_entity]
    logging.info("%s: giữ lại %s bài phù hợp", entity.entity, len(rows))
    return rows, errors


# Ghi chú: Giới hạn được áp dụng sau lọc để không hy sinh chất lượng vì thứ tự link tìm thấy.


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Đọc tham số dòng lệnh và kiểm tra phạm vi hợp lệ."""

    parser = argparse.ArgumentParser(
        description="Crawl tin giải thưởng, sự kiện/lãnh đạo và chuyển đổi số của 5 ngân hàng."
    )
    parser.add_argument("--start-date", type=parse_date, default=date(2025, 1, 1))
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    parser.add_argument("--output", type=Path, default=Path("output/raw/press_1"))
    parser.add_argument("--max-results-per-query", type=int, default=30)
    parser.add_argument("--max-articles-per-entity", type=int, default=150)
    parser.add_argument("--min-relevance-score", type=int, default=4)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    args = parser.parse_args(argv)
    if args.start_date > args.end_date:
        parser.error("start-date phải nhỏ hơn hoặc bằng end-date")
    if args.max_results_per_query <= 0 or args.workers <= 0 or args.timeout_seconds <= 0:
        parser.error("Các giới hạn tìm kiếm, workers và timeout phải lớn hơn 0")
    if args.min_relevance_score < 1:
        parser.error("min-relevance-score phải từ 1 trở lên")
    return args


# Ghi chú: Mặc định chạy dữ liệu thật từ 01/01/2025 đến ngày hiện tại.


def run(args: argparse.Namespace) -> None:
    """Chạy toàn bộ crawler và xuất dữ liệu, tổng hợp, lỗi và metadata."""

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session = build_session()
    all_rows: list[dict[str, Any]] = []
    all_errors: list[dict[str, str]] = []

    for entity in ENTITIES:
        logging.info("Đang xử lý %s", entity.entity)
        rows, errors = crawl_entity(session, entity, args)
        all_rows.extend(rows)
        all_errors.extend(errors)
        write_csv(output_dir / "checkpoints" / f"{entity.entity.lower()}_articles.csv", rows, ARTICLE_FIELDS)
        time.sleep(0.5)

    clean_rows = deduplicate_articles(all_rows)
    summary_rows = build_summary(clean_rows)
    error_fields = ("entity", "stage", "source", "url", "error_type", "message")
    summary_fields = (
        "entity",
        "total_articles",
        "award_articles",
        "event_speech_articles",
        "press_digital_articles",
        "negative_risk_articles",
        "technology_experience_articles",
        "official_source_articles",
        "full_text_articles",
        "first_published_date",
        "last_published_date",
    )
    write_csv(output_dir / "press_events_2025_to_now.csv", clean_rows, ARTICLE_FIELDS)
    write_csv(output_dir / "entity_summary.csv", summary_rows, summary_fields)
    write_csv(output_dir / "crawl_errors.csv", all_errors, error_fields)

    metadata = {
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_repository": REFERENCE_REPOSITORY,
        "article_rows": len(clean_rows),
        "error_rows": len(all_errors),
        "parameters": {
            "max_results_per_query": args.max_results_per_query,
            "max_articles_per_entity": args.max_articles_per_entity,
            "min_relevance_score": args.min_relevance_score,
            "workers": args.workers,
            "timeout_seconds": args.timeout_seconds,
        },
        "entities": [asdict(entity) for entity in ENTITIES],
        "trusted_news_domains": list(TRUSTED_NEWS_DOMAINS),
        "method_note": (
            "Search results are candidates, not a complete census of the web. "
            "Only official bank websites and allowlisted news domains are accepted. "
            "RSS title/summary must identify the entity and contain at least one technology "
            "or digital-user-experience term before the article page is fetched."
        ),
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info("Hoàn tất: %s bài, %s lỗi", len(clean_rows), len(all_errors))


# Ghi chú: Metadata lưu tham số để nhóm có thể tái lập và giải thích giới hạn phương pháp.


def main() -> None:
    """Điểm vào chương trình."""

    configure_console_utf8()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run(parse_args())


# Ghi chú: Giữ main nhỏ để file dễ kiểm thử và tái sử dụng trong notebook.


if __name__ == "__main__":
    main()
