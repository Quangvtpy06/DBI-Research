"""
Bước 1: Thu thập báo chí / giải thưởng / phát biểu về chuyển đổi số của 5 ngân hàng.
Cài: pip install feedparser requests beautifulsoup4 pandas trafilatura googlenewsdecoder
Output: data/raw_news.csv  (bank, date, source, type, title, url, text)
"""
import re
import time
import urllib.parse
from pathlib import Path

import feedparser
import pandas as pd

# ---- 1. CẤU HÌNH ---------------------------------------------------------
BANKS = {
    # VNG = Tập đoàn VNG (mã VNZ, UPCoM; có ZaloPay).
    # -> KHÔNG dùng alias "VNG" trần, để tránh lẫn bài của công ty du lịch.
    "VNG": ["Tập đoàn VNG", "VNZ", "ZaloPay", "Zalo Pay"],
    "VPB": ["VPBank", "VPBank NEO"],
    "VCB": ["Vietcombank", "VCB Digibank"],
    "HDB": ["HDBank"],
    "ACB": ["ACB", "Ngân hàng Á Châu", "ACB ONE"],
}

# (loại, cụm từ ghép vào query)
TOPICS = [
    ("press",  "chuyển đổi số"),
    ("press",  "ngân hàng số AI"),
    ("award",  "giải thưởng ngân hàng số"),
    ("award",  "Best Digital Bank"),
    ("speech", "Vietnam Banking Forum"),
    ("speech", "Giám đốc Khối Ngân hàng số"),
    ("speech", "CIO diễn đàn chuyển đổi số"),
]

YEARS = range(2025, 2027)          # chia theo năm vì mỗi query RSS chỉ trả ~100 bài
SLEEP = 1.5                        # giây, tránh bị chặn
OUT = Path(__file__).resolve().parents[2] / "output/raw/press_2/raw_news.csv"

AWARD_PAT = re.compile(r"giải thưởng|giải|vinh danh|best|award|top \d+|xuất sắc", re.I)
SPEECH_PAT = re.compile(r"diễn đàn|forum|phát biểu|chia sẻ|tham luận|hội thảo|CIO|giám đốc khối", re.I)


# ---- 2. HÀM PHỤ ----------------------------------------------------------
def rss_url(query: str, year: int) -> str:
    q = f'{query} after:{year}-01-01 before:{year + 1}-01-01'
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
            + "&hl=vi&gl=VN&ceid=VN:vi")


def classify(title: str, default: str) -> str:
    """Ưu tiên nhận diện theo tiêu đề; nếu không rõ thì dùng loại của query."""
    if AWARD_PAT.search(title):
        return "award"
    if SPEECH_PAT.search(title):
        return "speech"
    return default


def mentions_bank(title: str, summary: str, aliases: list[str]) -> bool:
    """Lọc bài không thực sự nói về ngân hàng đó (alias viết tắt ngắn phải khớp nguyên từ)."""
    text = f"{title} {summary}"
    for a in aliases:
        if re.search(rf"(?<!\w){re.escape(a)}(?!\w)", text, re.I):
            return True
    return False


# ---- 3. THU THẬP ---------------------------------------------------------
def collect() -> pd.DataFrame:
    rows = []
    for bank, aliases in BANKS.items():
        for default_type, topic in TOPICS:
            for alias in aliases:
                for year in YEARS:
                    url = rss_url(f'"{alias}" {topic}', year)
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        title = e.get("title", "")
                        summary = re.sub(r"<[^>]+>", " ", e.get("summary", ""))
                        if not mentions_bank(title, summary, aliases):
                            continue
                        rows.append({
                            "bank": bank,
                            "date": pd.to_datetime(e.get("published"), errors="coerce"),
                            "source": (e.get("source") or {}).get("title", ""),
                            "type": classify(title, default_type),
                            "title": title.strip(),
                            "url": e.get("link", ""),
                            "text": "",
                        })
                    time.sleep(SLEEP)
            print(f"[{bank}] xong topic: {topic} ({len(rows)} dòng)")
    return pd.DataFrame(rows)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_key"] = df["title"].str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
    df = df.sort_values("date").drop_duplicates(["bank", "_key"], keep="first")
    return df.drop(columns="_key").reset_index(drop=True)


# ---- 4. LẤY NỘI DUNG BÀI (tùy chọn, chạy sau khi có danh sách) -------------
def fetch_fulltext(df: pd.DataFrame, limit: int | None = None) -> pd.DataFrame:
    from enrich_fulltext import choose, enrich

    selected = choose(df.head(limit).to_dict('records') if limit else df.to_dict('records'), len(df))
    result = pd.DataFrame(enrich(selected, OUT.parents[2] / 'processed/press_2_fulltext'))
    return result


if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enrich-existing', action='store_true', help='Bổ sung toàn văn từ raw_news.csv, không tìm RSS lại')
    parser.add_argument('--skip-fulltext', action='store_true', help='Chỉ lấy danh sách; mặc định tự lấy toàn văn')
    args = parser.parse_args()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if args.enrich_existing:
        df = pd.read_csv(OUT).fillna('')
    else:
        df = dedupe(collect())
        df.to_csv(OUT, index=False, encoding="utf-8-sig")
    if not args.skip_fulltext:
        enriched = fetch_fulltext(df)
        enriched.to_csv(OUT.with_name('raw_news_enriched.csv'), index=False, encoding='utf-8-sig')
        print(enriched.groupby(['ticker', 'fetch_status']).size())
