"""Tải báo cáo DBI 2025–2026, lập chỉ mục bằng chứng và xuất kết quả đã kiểm chứng.

Chạy trực tiếp trong PyCharm hoặc: python Crawl_Annual_Report_5_company.py
Nguồn: report_sources.json. Kết quả: output/raw/reports/.
Không tự biến kết quả dò từ khóa thành số liệu tài chính đã xác minh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import fitz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
COMPANIES = {"VNZ": "CTCP Tập đoàn VNG", "VPB": "VPBank", "VCB": "Vietcombank",
             "HDB": "HDBank", "ACB": "Ngân hàng TMCP Á Châu"}
METRICS = ["Tỷ lệ giao dịch qua kênh số", "Số lượng và giá trị giao dịch số",
           "Tỷ lệ khách hàng mới qua kênh số/eKYC", "Người dùng/khách hàng số",
           "Ngân sách/chi phí CNTT và chuyển đổi số", "Tài sản cố định vô hình/phần mềm",
           "CIR", "Số hóa quy trình nội bộ/STP/RLOS"]
KEYWORDS = {
    "chien_luoc": ["chuyển đổi số", "chiến lược số", "digital transformation", "ai-first"],
    "ha_tang": ["core banking", "core-banking", "ngân hàng lõi", "cloud", "genai", "llm",
                "big data", "open api", "sinh trắc", "nfc", "iso 27001", "pci dss", "pci-dss", "nist"],
    "khach_hang": ["giao dịch số", "giao dịch trực tuyến", "giao dịch online", "kênh số",
                   "người dùng", "active users", "digital", "ekyc", "neo", "digibank", "acb one", "zalopay"],
    "nhan_su": ["nhân sự công nghệ", "đội ngũ công nghệ", "đào tạo", "kỹ năng số", "nhân tài số"],
    "tai_chinh": ["cir", "cost to income", "chi phí công nghệ", "đầu tư công nghệ", "cntt",
                  "phần mềm máy tính", "tài sản cố định vô hình", "intangible", "software"],
    "van_hanh": ["stp", "rlos", "phê duyệt tự động", "tự động hóa", "số hóa quy trình"],
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c)))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> str:
    if path.exists() and not refresh:
        with fitz.open(path) as doc:
            if not doc.page_count:
                raise ValueError("PDF lưu sẵn không có trang")
        return "cached"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        with session.get(url, timeout=(15, 120), stream=True) as response:
            response.raise_for_status()
            with tmp.open("wb") as f:
                size = 0
                for chunk in response.iter_content(256 * 1024):
                    size += len(chunk)
                    if size > 250 * 1024 * 1024:
                        raise ValueError("PDF vượt giới hạn 250 MB")
                    f.write(chunk)
        with tmp.open("rb") as f:
            if b"%PDF-" not in f.read(1024):
                raise ValueError("Máy chủ trả về nội dung không phải PDF")
        with fitz.open(tmp) as doc:
            if not doc.page_count or doc.needs_pass:
                raise ValueError("PDF rỗng hoặc cần mật khẩu")
        tmp.replace(path)
        return "downloaded"
    finally:
        tmp.unlink(missing_ok=True)


def extract(path: Path, source: dict, out: Path) -> tuple[list, list, dict]:
    pages, candidates = [], []
    with fitz.open(path) as doc:
        for number, page in enumerate(doc, 1):
            text = page.get_text("text", sort=True)
            pages.append({"pdf_page": number, "text": text})
            normalized = normalize(text)
            groups = {group: [word for word in words if re.search(
                r"(?<!\w)" + re.escape(normalize(word)) + r"(?!\w)", normalized)]
                      for group, words in KEYWORDS.items()}
            groups = {k: v for k, v in groups.items() if v}
            if groups:
                candidates.append({"document_id": source["id"], "symbol": source["symbol"],
                                   "period": source["period"], "pdf_page": number,
                                   "source_url": source["url"] + f"#page={number}",
                                   "groups": groups,
                                   "status": "candidate_requires_review",
                                   "contains_older_year": bool(re.search(r"\b20(?:0\d|1\d|2[0-4])\b", text))})
    write_json(out / "text" / f"{source['id']}.json", pages)
    (out / "text" / f"{source['id']}.txt").write_text(
        "\n\n".join(f"=== PDF PAGE {p['pdf_page']} ===\n{p['text']}" for p in pages), encoding="utf-8")
    sparse = [p["pdf_page"] for p in pages if len(p["text"].strip()) < 50]
    return pages, candidates, {"pages": len(pages), "sparse_pages": sparse,
                               "ocr_may_be_needed": len(sparse) > max(3, len(pages) * .2)}


def md(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_review(out: Path, sources: list[dict], reviewed: dict, hashes: dict) -> None:
    """Chỉ xuất giá trị được đối chiếu thủ công với đúng hash của tài liệu nguồn."""
    lines = ["# Dữ liệu chuyển đổi số và ngân hàng số 2025–2026", "",
             "Số trang PDF tính từ 1 (bao gồm bìa); trang in được ghi riêng nếu đã đối chiếu.",
             "Chỉ tiêu thiếu ghi ‘Không đề cập’ chỉ khi tài liệu tương ứng đã được đọc.",
             "Không lấy số so sánh trước năm 2025. Không tự tính CIR hoặc ngân sách CNTT.",
             "VNG là doanh nghiệp công nghệ: người dùng Zalo/Zalopay không đồng nghĩa khách hàng ngân hàng.", ""]
    by_id = {s["id"]: s for s in sources}
    for symbol, name in COMPANIES.items():
        if not any(s["symbol"] == symbol for s in sources):
            continue
        item = reviewed.get(symbol, {})
        lines += [f"## {symbol} — {name}", "", "### Thông tin chung", ""]
        for s in sources:
            if s["symbol"] == symbol:
                lines.append(f"- [{s['period']}]({s['url']}) — {s.get('note', '')}")
        lines += ["", "### Dữ liệu định lượng", "",
                  "| Chỉ số | Giá trị/Số liệu (2025–2026) | Đơn vị tính | Trang/Mục trong BCTC/BCTN |",
                  "|---|---|---|---|"]
        for metric in METRICS:
            evidence = [x for x in item.get("metrics", []) if x["metric"] == metric]
            if not evidence:
                lines.append(f"| {metric} | Chưa xác minh | — | Chưa hoàn tất đối chiếu |")
            for entry in evidence:
                refs = entry.get("references", [])
                for ref in refs:
                    if hashes.get(ref["id"]) != ref["sha256"]:
                        raise ValueError(f"Nguồn {ref['id']} thay đổi hoặc chưa tải: cần kiểm chứng lại")
                citations = "; ".join(f"[{r['location']}]({by_id[r['id']]['url']}#page={r['page']})" for r in refs)
                lines.append("| " + " | ".join(map(md, [metric, entry["value"], entry.get("unit", "—"), citations or entry.get("scope", "")])) + " |")
        lines += ["", "### Bằng chứng định tính", ""]
        for entry in item.get("qualitative", []):
            refs = entry["references"]
            for ref in refs:
                if hashes.get(ref["id"]) != ref["sha256"]:
                    raise ValueError(f"Nguồn {ref['id']} thay đổi: cần kiểm chứng lại")
            citation = "; ".join(f"[{r['location']}]({by_id[r['id']]['url']}#page={r['page']})" for r in refs)
            lines += [f"**{entry['pillar']}** — {entry['text']} {citation}", ""]
        if item.get("limitations"):
            lines += ["**Giới hạn:** " + item["limitations"], ""]
    (out / "DBI_2025_2026.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=ROOT / "report_sources.json")
    parser.add_argument("--output", type=Path, default=ROOT / "output/raw/reports")
    parser.add_argument("--symbols", nargs="+", choices=COMPANIES, default=list(COMPANIES))
    parser.add_argument("--refresh", action="store_true", help="Tải lại PDF thay vì dùng bản đã lưu")
    parser.add_argument("--offline", action="store_true", help="Chỉ xử lý PDF đã có, không truy cập mạng")
    args = parser.parse_args(argv)
    catalog = json.loads(args.sources.read_text(encoding="utf-8"))
    sources = [s for s in catalog["documents"] if s["symbol"] in args.symbols]
    if not sources:
        parser.error("Không có tài liệu phù hợp")
    for s in sources:
        if s["year"] not in (2025, 2026) or (s["kind"] == "annual" and s["year"] != 2025):
            parser.error(f"Tài liệu ngoài phạm vi: {s['id']}")
        if not re.fullmatch(r"[A-Z0-9_]+", s["id"]):
            parser.error("Mã tài liệu không hợp lệ")
        if s["kind"] == "financial" and not s.get("consolidated"):
            parser.error(f"BCTC không phải hợp nhất: {s['id']}")
    args.output.mkdir(parents=True, exist_ok=True)
    statuses, candidates, hashes = [], [], {}
    with requests.Session() as session:
        session.headers["User-Agent"] = "DBI-Research/1.0 (public corporate reports)"
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))))
        for s in sources:
            path = args.output / "pdf" / f"{s['id']}.pdf"
            status = {**s, "checked_at_utc": datetime.now(timezone.utc).isoformat()}
            try:
                if args.offline and not path.exists():
                    raise FileNotFoundError(f"Thiếu PDF: {path}")
                state = "cached" if args.offline else download(session, s["url"], path, args.refresh)
                hashes[s["id"]] = hashlib.sha256(path.read_bytes()).hexdigest()
                _, found, quality = extract(path, s, args.output)
                candidates.extend(found)
                status.update(status=state, sha256=hashes[s["id"]], path=str(path), **quality)
                print(f"{s['id']}: {state}, {quality['pages']} trang", flush=True)
            except (requests.RequestException, OSError, ValueError, RuntimeError) as exc:
                status.update(status="error", error=str(exc))
                print(f"{s['id']}: ERROR {exc}", file=sys.stderr, flush=True)
            statuses.append(status)
            write_json(args.output / "download_manifest.json", statuses)
    write_json(args.output / "evidence_candidates.json", candidates)
    review_path = ROOT / "reviewed_evidence.json"
    reviewed = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    render_review(args.output, sources, reviewed, hashes)
    return int(any(s["status"] == "error" for s in statuses))


if __name__ == "__main__":
    raise SystemExit(main())
