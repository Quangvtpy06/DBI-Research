"""
Bước 2: Làm sạch + quét từ khóa công nghệ.
Input : data/raw_news.csv  (từ collect.py)
Output: data/clean_news.csv, data/keyword_by_article.csv,
        data/summary_by_ticker.csv, data/summary_by_ticker_type.csv, data/heatmap.png
Cài   : pip install pandas matplotlib
"""
import re
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

D = Path(__file__).resolve().parents[2] / "output/raw/press_2"
RAW = D / "raw_news.csv"

# ---- 1. TỪ ĐIỂN TỪ KHÓA --------------------------------------------------
# (regex, phân biệt hoa/thường). Viết tắt ngắn phải case-sensitive + nguyên từ,
# vì "ai" (tiếng Việt = "who") sẽ khớp nhầm nếu không phân biệt hoa/thường.
KW = {
    "AI/ML": [
        (r"\bAI\b", True), (r"\bGenAI\b", True), (r"\bML\b", True),
        (r"trí tuệ nhân tạo", False), (r"machine learning", False),
        (r"học máy", False), (r"chatbot", False), (r"generative ai", False),
        (r"trợ lý ảo", False),
    ],
    "Cloud": [
        (r"\bcloud\b", False), (r"điện toán đám mây", False), (r"đám mây", False),
    ],
    "Data": [
        (r"big data", False), (r"dữ liệu lớn", False), (r"data analytics", False),
        (r"phân tích dữ liệu", False), (r"data lake", False), (r"kho dữ liệu", False),
    ],
    "Open banking/API": [
        (r"\bAPI\b", True), (r"open banking", False), (r"ngân hàng mở", False),
        (r"open api", False), (r"hệ sinh thái số", False),
    ],
    "Bảo mật/Định danh": [
        (r"\beKYC\b", False), (r"sinh trắc học", False), (r"biometric", False),
        (r"an ninh mạng", False), (r"bảo mật", False), (r"xác thực", False),
        (r"định danh điện tử", False), (r"chống gian lận", False),
    ],
    "Blockchain": [
        (r"blockchain", False), (r"token hóa", False), (r"tài sản mã hóa", False),
    ],
    "Nền tảng số": [
        (r"core banking", False), (r"super app", False), (r"mobile banking", False),
        (r"ngân hàng số", False), (r"ngân hàng lõi", False), (r"ví điện tử", False),
        (r"\bapp\b", False), (r"ứng dụng ngân hàng", False),
    ],
    "Tự động hóa": [
        (r"\bRPA\b", True), (r"tự động hóa", False), (r"automation", False),
    ],
}
COMPILED = {
    g: [(re.compile(p, 0 if cs else re.I), p) for p, cs in pats] for g, pats in KW.items()
}


# ---- 2. LÀM SẠCH ---------------------------------------------------------
def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s))
    return re.sub(r"\s+", " ", s).strip()


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["title"] = df["title"].fillna("").map(norm)
    # Google News hay thêm " - Tên báo" cuối tiêu đề: tách ra để không tính vào nội dung
    df["title"] = df["title"].str.replace(r"\s+-\s+[^-]{2,40}$", "", regex=True)
    df["text"] = df["text"].fillna("").map(norm)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df[df["title"].str.len() > 10]
    df = df.drop_duplicates(["ticker", "url"]).drop_duplicates(["ticker", "title"])
    # nội dung để quét: tiêu đề + text (nếu chưa chạy fetch_fulltext thì chỉ có tiêu đề)
    df["content"] = (df["title"] + ". " + df["text"]).str.strip()
    df["n_words"] = df["content"].str.split().str.len()
    df["has_fulltext"] = (df["text"].str.len() >= 600) & (df["text"].str.split().str.len() >= 100)
    if 'fetch_status' in df.columns:
        df["has_fulltext"] &= df['fetch_status'].eq('success')
    return df.reset_index(drop=True)


# ---- 3. ĐẾM TỪ KHÓA ------------------------------------------------------
def count_keywords(content: str) -> dict:
    out = {}
    for group, pats in COMPILED.items():
        out[group] = sum(len(rx.findall(content)) for rx, _ in pats)
    return out


def scan(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["content"].map(count_keywords).apply(pd.Series)
    return pd.concat([df.drop(columns=["content"]), counts], axis=1)


# ---- 4. TỔNG HỢP ---------------------------------------------------------
def summarize(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    groups = list(KW)
    g = df.groupby(by)
    res = g.agg(n_articles=("title", "size"), n_words=("n_words", "sum"))
    for k in groups:
        res[f"{k}|bài_có"] = g[k].apply(lambda s: (s > 0).sum())       # số bài có nhắc nhóm
        res[f"{k}|%bài"] = (res[f"{k}|bài_có"] / res["n_articles"] * 100).round(1)
        res[f"{k}|/1000từ"] = (g[k].sum() / res["n_words"] * 1000).round(2)
    tot = df[groups].sum(axis=1)
    res["tổng_từ_khóa"] = tot.groupby([df[c] for c in by]).sum()
    res["mật_độ_/1000từ"] = (res["tổng_từ_khóa"] / res["n_words"] * 1000).round(2)
    res["%bài_có_≥1_từ_khóa"] = (
        (tot > 0).groupby([df[c] for c in by]).mean() * 100
    ).round(1)
    return res.reset_index()


def heatmap(summary: pd.DataFrame, path: Path):
    cols = [f"{k}|%bài" for k in KW]
    m = summary.set_index("ticker")[cols]
    m.columns = list(KW)
    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.imshow(m.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(m.columns)), m.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(m.index)), m.index)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, f"{m.values[i, j]:.0f}", ha="center", va="center", fontsize=9)
    ax.set_title("% bài viết có nhắc nhóm công nghệ, theo mã cổ phiếu")
    fig.colorbar(im, label="% bài")
    fig.tight_layout()
    fig.savefig(path, dpi=200)


# ---- MAIN ----------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=D / 'raw_news_enriched.csv' if (D / 'raw_news_enriched.csv').exists() else RAW)
    parser.add_argument('--output', type=Path, default=D)
    args = parser.parse_args()
    D = args.output
    D.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(args.input)
    raw = raw.rename(columns={"bank": "ticker"})  # tương thích file raw cũ
    print("Dòng thô:", len(raw))
    df = clean(raw)
    print("Sau làm sạch:", len(df))
    df.drop(columns=["content"]).to_csv(D / "clean_news.csv", index=False, encoding="utf-8-sig")

    scanned = scan(df)
    scanned.to_csv(D / "keyword_by_article.csv", index=False, encoding="utf-8-sig")

    by_ticker = summarize(scanned, ["ticker"])
    by_ticker.to_csv(D / "summary_by_ticker.csv", index=False, encoding="utf-8-sig")
    summarize(scanned, ["ticker", "type"]).to_csv(
        D / "summary_by_ticker_type.csv", index=False, encoding="utf-8-sig")
    heatmap(by_ticker, D / "heatmap.png")

    print("\n== Số bài theo mã cổ phiếu x loại ==")
    print(scanned.groupby(["ticker", "type"]).size().unstack(fill_value=0))
    print("\n== Tỷ lệ bài có full text (nếu ~0% thì đang quét theo tiêu đề) ==")
    print((scanned.groupby("ticker")["has_fulltext"].mean() * 100).round(1))
    print("\n== Mật độ từ khóa /1000 từ và % bài có từ khóa ==")
    print(by_ticker[["ticker", "n_articles", "mật_độ_/1000từ", "%bài_có_≥1_từ_khóa"]])
