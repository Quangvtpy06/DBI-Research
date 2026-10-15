"""Sentiment từ nội dung: baseline từ điển, không dùng sao làm nhãn chuẩn.

Chạy: sentiment_module.py --output output/processed/sentiment
Chỉ dùng thư viện chuẩn; sử dụng dữ liệu crawl và output cũ.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from analyze_text_mining import classify_topics

ROOT = Path(__file__).resolve().parent
POS = "tốt|rất tốt|tuyệt vời|xuất sắc|hài lòng|tiện lợi|thuận tiện|dễ dùng|dễ sử dụng|nhanh|mượt|ổn định|an toàn|tin cậy|thành công|hiệu quả|cải thiện|tiết kiệm thời gian|minh bạch|tối ưu|đột phá|tiên phong|đổi mới|thích|ok|oke|nên dùng|đẹp|hữu ích|chất lượng|tuyệt|ưng|good|great|excellent"
NEG = "tệ|rất tệ|kém|thất vọng|không hài lòng|lỗi|lỗi hệ thống|không vào được|không dùng được|không thể giao dịch|không giao dịch được|không đăng nhập được|không nhận được otp|chậm|lag|treo|crash|bất tiện|khó dùng|mất tiền|gián đoạn|rò rỉ dữ liệu|lộ dữ liệu|quá tải|thất bại|ức chế|bực|khó chịu|rác|lừa đảo|gian lận|tấn công mạng|sự cố|vô dụng|không chuyển được|không chuyển tiền được|không mở được|không được|ngu|bad|terrible"
EXCEPTIONS = ("không chỉ", "không những", "chẳng những", "không ngừng", "không thể thiếu")
NEGATORS = {"không", "chưa", "chẳng", "chả", "not", "never"}
PREVENT = re.compile(r"phòng chống|phòng ngừa|ngăn chặn|cảnh báo|phòng tránh|chống|nhận diện")
RISK = {"lừa đảo", "gian lận", "tấn công mạng", "rò rỉ dữ liệu", "lộ dữ liệu"}
MAP = {"VPB": "VPBank", "VCB": "VCB", "HDB": "HDBank", "ACB": "ACB", "VNG": "VNG", "VNZ": "VNG"}
DIGITAL_CONTEXT = re.compile(r"(?<!\w)(?:chuyển đổi số|số hóa|số hoá|ngân hàng số|kênh số|giao dịch số|công nghệ thông tin|công nghệ số|nền tảng số|hệ sinh thái số|trí tuệ nhân tạo|dữ liệu lớn|quản trị dữ liệu|điện toán đám mây|tự động hóa|tự động hoá|an ninh mạng|bảo mật|sinh trắc học|định danh điện tử|thanh toán điện tử|thanh toán số|ví điện tử|phần mềm|ứng dụng di động|ngân hàng điện tử|digibank|zalopay|neo|ebanking|e-banking|mobile banking|core banking|open banking|cloud|genai|big data|blockchain|ekyc|vneid|rpa|stp|rlos|clos|api)(?!\w)", re.I)


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return unicodedata.normalize("NFC", re.sub(r"https?://\S+", " ", text))


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").replace("đ", "d")


def tokens(text):
    return re.findall(r"\w+", text.lower(), re.UNICODE)


def make_trie():
    root = {}
    for polarity, phrases in ((1, POS), (-1, NEG)):
        for phrase in phrases.split("|"):
            for variant in {phrase, fold(phrase)}:
                node = root
                for token in tokens(variant):
                    node = node.setdefault(token, {})
                node[None] = (phrase, polarity)
    return root


TRIE = make_trie()


def sentence_evidence(text, negation_window=3):
    """Khớp cụm dài nhất, không đếm chồng lấn; phủ định không vượt câu.

    Cụm âm rõ nghĩa được giữ nguyên. Phủ định từ dương đảo sang âm;
    phủ định từ âm bị loại (không suy ra năng lực tốt từ phủ nhận sự cố).
    """
    text = clean(text).lower()
    ts = tokens(text)
    evidence = []
    index = 0
    while index < len(ts):
        node, end, best = TRIE, index, None
        while end < len(ts) and ts[end] in node:
            node = node[ts[end]]
            end += 1
            if None in node:
                best = (end, *node[None])
        if best is None:
            index += 1
            continue
        end, phrase, polarity = best
        # Không dùng biến thể bỏ dấu trong câu có dấu: tránh nhầm 'lợi' và 'lỗi'.
        matched = " ".join(ts[index:end])
        accented_sentence = fold(text) != text
        if accented_sentence and matched != phrase:
            index = end
            continue
        context = " ".join(ts[max(0, index-negation_window):index])
        context_fold = fold(context)
        exception = any(fold(p) in context_fold for p in EXCEPTIONS)
        negated = not exception and any(fold(t) in {fold(n) for n in NEGATORS} for t in ts[max(0, index-negation_window):index])
        reason = "direct"
        if phrase in RISK and PREVENT.search(context):
            polarity, reason = 0, "prevention_context"
        elif negated:
            polarity, reason = (-1 if polarity > 0 else 0), "negated"
        evidence.append({"term": phrase, "sign": polarity, "rule": reason})
        index = end
    return ts, evidence


def label(score, delta):
    return "Positive" if score > delta else "Negative" if score < -delta else "Neutral"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def inputs():
    for row in read_csv(ROOT / "output/raw/app_reviews/reviews_2025_to_now.csv"):
        yield dict(entity=row["entity"], source="app_review", platform=row["platform"], original_id=row["review_id"], date=row["review_date"], text=row["content"], rating=row["rating"], url="", page="", scope="product", fulltext="True")
    for row in read_csv(ROOT / "output/raw/press_1/press_events_2025_to_now.csv"):
        # Nội dung thường đã bao gồm sapo/tiêu đề, chỉ ghép tiêu đề khi cần.
        body = row.get("content") or row.get("sapo") or ""
        title = row.get("title", "")
        text = body if title in body else title + ". " + body
        yield dict(entity=row["entity"], source="press_crawl_1", platform=row["source_domain"], original_id=row["content_hash"], date=row["published_date"], text=text, rating="", url=row["url"], page="", scope="entity_tag_unverified", fulltext=str(bool(body)))
    source2 = ROOT / 'output/processed/press_2_fulltext/analyzed/clean_news.csv'
    if not source2.exists():
        source2 = ROOT / 'output/raw/press_2/clean_news.csv'
    for row in read_csv(source2):
        if 'fetch_status' in row and row['fetch_status'] != 'success':
            continue
        body = row.get("text", "")
        title = row.get("title", "")
        yield dict(entity=MAP.get(row["ticker"], row["ticker"]), source="press_crawl_2", platform=row["source"], original_id=row["url"], date=row["date"], text=body if title in body else title + ". " + body, rating="", url=row["url"], page="", scope="entity_tag_unverified", fulltext=row.get("has_fulltext", "False"))
    for path in sorted((ROOT / "output/raw/reports/text").glob("*.json")):
        ticker = path.stem.split("_")[0]
        for page in json.loads(path.read_text(encoding="utf-8-sig")):
            yield dict(entity=MAP[ticker], source="annual_report" if "_AR_" in path.stem else "financial_report", platform=path.stem, original_id=f"{path.stem}:{page['pdf_page']}", date="2025" if "_AR_" in path.stem else "2026-H1", text=page.get("text", ""), rating="", url="", page=page["pdf_page"], scope="group_report_not_product", fulltext="True")


def write_csv(path, rows, fields=None):
    rows = list(rows)
    if fields is None:
        fields = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(output, delta=0.1):
    output.mkdir(parents=True, exist_ok=True)
    documents, sentence_rows, seen, audit = [], [], set(), Counter()
    df = Counter()
    for record in inputs():
        audit[record["source"] + ":input"] += 1
        text = clean(record.pop("text"))
        if not text.strip():
            audit[record["source"] + ":empty"] += 1
            continue
        # ID review trước; tin dùng nội dung chuẩn hóa để bắt bài trùng chính xác giữa nguồn.
        key = (record["entity"], record["source"], record["platform"], record["original_id"]) if record["source"] == "app_review" else (record["entity"], "press" if record["source"].startswith("press") else record["platform"], re.sub(r"\s+", " ", text.lower()).strip())
        if key in seen:
            audit[record["source"] + ":duplicate"] += 1
            continue
        seen.add(key)
        doc_id = hashlib.sha256(repr(key).encode()).hexdigest()[:20]
        raw_sentences = [s.strip() for s in re.split(r"[!?。;]+|(?<!\d)\.(?!\d)|\n+", text) if s.strip()]
        counts, all_tokens, topics_all = Counter(), 0, set()
        units = []
        for number, sentence in enumerate(raw_sentences, 1):
            topics = classify_topics(sentence)
            # Báo cáo chỉ lấy câu/đoạn có tín hiệu chủ đề; không chấm tone toàn bộ BCTC.
            if record["source"].endswith("report") and not DIGITAL_CONTEXT.search(sentence):
                continue
            ts, evidence = sentence_evidence(sentence)
            hits = Counter((e["term"], e["sign"]) for e in evidence if e["sign"])
            positive = sum(n for (_, sign), n in hits.items() if sign > 0)
            negative = sum(n for (_, sign), n in hits.items() if sign < 0)
            tone = (positive-negative)/(positive+negative) if positive+negative else 0
            counts.update(hits)
            all_tokens += len(ts)
            topics_all.update(topics)
            units.append(tone)
            if evidence or topics:
                sentence_rows.append(dict(doc_id=doc_id, entity=record["entity"], source=record["source"], page=record["page"], sentence_index=number, text=sentence, topics=";".join(sorted(topics)), tone=round(tone, 6), sentiment=label(tone, delta), evidence_status="matched" if positive+negative else "no_sentiment_evidence", evidence=json.dumps(evidence, ensure_ascii=False)))
        if not units:
            audit[record["source"] + ":no_relevant_sentence"] += 1
            continue
        p = sum(n for (_, sign), n in counts.items() if sign > 0)
        n = sum(n for (_, sign), n in counts.items() if sign < 0)
        tone = (p-n)/(p+n) if p+n else 0
        rating = int(record["rating"]) if record["rating"] else None
        star_label = ("Negative" if rating <= 2 else "Positive" if rating >= 4 else "Neutral") if rating else ""
        status = "mixed" if p and n else "matched" if p+n else "no_sentiment_evidence"
        documents.append(dict(doc_id=doc_id, **record, text=text, topics=";".join(sorted(topics_all)), token_count=all_tokens, sentence_count=len(units), positive_count=p, negative_count=n, tone_ratio=round(tone, 6), tone_difference=round((p-n)/all_tokens, 6) if all_tokens else 0, sentence_mean=round(sum(units)/len(units), 6), sentiment=label(tone, delta), evidence_status=status, star_label=star_label, star_disagreement=bool(star_label and p+n and star_label != label(tone, delta)), _counts=counts))
        df.update(set(term for term, sign in counts))
    total = len(documents)
    summary = defaultdict(Counter)
    for doc in documents:
        scores = {1: 0.0, -1: 0.0}
        for (term, sign), count in doc.pop("_counts").items():
            # C2 sửa: chuẩn hóa độ dài đúng một lần; IDF làm trơn.
            scores[sign] += (1+math.log(count))/(1+math.log(max(1, doc["token_count"]))) * (math.log((1+total)/(1+df[term]))+1)
        denominator = scores[1]+scores[-1]
        tfidf = (scores[1]-scores[-1])/denominator if denominator else 0
        doc.update(tone_tfidf=round(tfidf, 6), sentiment_tfidf=label(tfidf, delta), method_disagreement=label(tfidf, delta) != doc["sentiment"])
        c = summary[(doc["entity"], doc["source"])]
        c[doc["sentiment"]] += 1
        c["total"] += 1
        c["no_evidence"] += doc["evidence_status"] == "no_sentiment_evidence"
        c["mixed"] += doc["evidence_status"] == "mixed"
        c["star_disagreement"] += doc["star_disagreement"]
        c["star_comparable"] += bool(doc["star_label"] and doc["evidence_status"] != "no_sentiment_evidence")
        c["method_disagreement"] += doc["method_disagreement"]
        c["title_only"] += str(doc["fulltext"]).lower() != "true"
    rows = []
    for (entity, source), c in sorted(summary.items()):
        rows.append(dict(entity=entity, source=source, **{k: c[k] for k in ("total", "Positive", "Neutral", "Negative", "no_evidence", "mixed", "star_disagreement", "star_comparable", "method_disagreement", "title_only")}, coverage_percent=round(100*(1-c["no_evidence"]/c["total"]), 2), nsi=round((c["Positive"]-c["Negative"])/c["total"], 4)))
    write_csv(output / "documents.csv", documents)
    write_csv(output / "sentences.csv", sentence_rows)
    write_csv(output / "summary.csv", rows)
    # Mẫu cố định phân tầng nguồn, đơn vị, nhãn và tình trạng bằng chứng.
    rng = random.Random(20261015)
    strata = defaultdict(list)
    for doc in documents:
        strata[(doc["source"], doc["entity"], doc["sentiment"], doc["evidence_status"])].append(doc)
    sample = []
    for group in strata.values():
        for doc in rng.sample(group, min(5, len(group))):
            sample.append({**doc, "annotator_1": "", "annotator_2": "", "gold_label": "", "review_note": ""})
    write_csv(output / "annotation_sample.csv", sample)
    queue = [d for d in documents if d["star_disagreement"] or d["method_disagreement"] or d["evidence_status"] == "mixed"]
    write_csv(output / "review_queue.csv", queue, list(documents[0]) if documents else None)
    source2_path=ROOT/'output/processed/press_2_fulltext/analyzed/clean_news.csv'
    if not source2_path.exists():source2_path=ROOT/'output/raw/press_2/clean_news.csv'
    input_paths = [ROOT / "output/raw/app_reviews/reviews_2025_to_now.csv", ROOT / "output/raw/press_1/press_events_2025_to_now.csv", source2_path, *sorted((ROOT / "output/raw/reports/text").glob("*.json"))]
    metadata = dict(generated_at_utc=datetime.now(timezone.utc).isoformat(), delta=delta, audit=dict(audit), documents=total, sentences_exported=len(sentence_rows), annotation_sample=len(sample), review_queue=len(queue), lexicon={"positive": POS.split("|"), "negative": NEG.split("|")}, method="Longest phrase; contextual negation; C1 ratio; smoothed C2 single length normalization; C4 sentence mean; G1 NSI", validation="Chưa có nhãn người gán: không công bố Accuracy/Macro-F1", dedup="Review ID theo app/platform; tin trùng nội dung chính xác theo entity. Chưa gom sự kiện/near-duplicate.", input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}, digital_context_pattern=DIGITAL_CONTEXT.pattern)
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Kết quả mô-đun sentiment", "", f"Đã xử lý **{total:,}** đơn vị văn bản; xuất {len(sentence_rows):,} câu/đoạn có từ khóa hoặc bằng chứng cảm xúc.", "", "Đơn vị: review và bài báo; báo cáo dùng trang có câu liên quan. Không so sánh trực tiếp số đếm giữa các loại nguồn. Nhãn Neutral gồm cả trường hợp không có bằng chứng; cột no_evidence tách riêng trường hợp này.", "", "| Đơn vị | Nguồn | N | Tích cực | Trung lập | Tiêu cực | Phủ từ điển % | Chỉ tiêu |", "|---|---|---:|---:|---:|---:|---:|---|" ]
    for r in rows:
        lines.append(f"| {r['entity']} | {r['source']} | {r['total']} | {r['Positive']} | {r['Neutral']} | {r['Negative']} | {r['coverage_percent']} | NSI={r['nsi']} |")
    lines += ["", "## Đánh giá khả năng tiếp tục DBI", "", "Có thể bắt đầu thiết kế và thí điểm trích xuất bằng chứng trên sentences.csv (có doc_id, trang, topic và văn bản gốc). Chưa đủ điều kiện công bố điểm/xếp hạng DBI:", "", "- Sentiment là baseline từ điển, chưa có kiểm định độc lập. Gán nhãn annotation_sample.csv bởi hai người; tính đồng thuận trước hòa giải và Macro-F1 sau khi chốt gold. Mẫu phân tầng không đại diện tỷ lệ tự nhiên; khi ước lượng chỉ số toàn kho cần trọng số lấy mẫu hoặc test đại diện riêng.", "- Không dùng sao làm gold: star_disagreement chỉ là tín hiệu rà soát. Không lấy điểm sentiment làm mức trưởng thành số.", "- Tin nguồn 2 có nhiều bản ghi chỉ có tiêu đề: xem title_only trong summary.csv; không suy diễn nội dung chưa crawl.", "- Cần gom các tin cùng sự kiện, xác nhận thực thể trong bài nhiều ngân hàng, kiểm tra ngày sự kiện và tách kế hoạch/đã triển khai/kết quả.", "- Báo cáo thuộc ngân hàng/tập đoàn, review thuộc sản phẩm. VNG giữ riêng với ZaloPay; không tự quy dữ liệu toàn VNG thành năng lực ZaloPay.", "- Topic là gợi ý regex, chưa phải năm trụ cột đã kiểm định. Câu không có sentiment vẫn có thể chứa bằng chứng năng lực số.", "- OCR có thể sai dấu, bảng có thể mất cấu trúc; kiểm tra PDF gốc trước khi trích số. Trang là đơn vị kỹ thuật, không phải bằng chứng độc lập.", "- IDF được tính trên kho đầu vào hiện tại cho mô tả; khi đánh giá holdout phải fit IDF/từ điển/ngưỡng trên train và cố định cho test. Delta=0.1 hiện là giả định, chưa được tối ưu.", "", "## Tệp đầu ra", "", "documents.csv: mọi văn bản được chấm; sentences.csv: câu/đoạn có tín hiệu; summary.csv: tổng hợp; review_queue.csv: nhãn hỗn hợp/bất đồng; annotation_sample.csv: mẫu gán nhãn; metadata.json: cấu hình và kiểm kê đầu vào."]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in ("documents", "sentences_exported", "annotation_sample", "review_queue", "audit")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/processed/sentiment")
    parser.add_argument("--delta", type=float, default=0.1)
    args = parser.parse_args()
    if not 0 <= args.delta <= 1:
        parser.error("delta phải nằm trong [0,1]")
    run(args.output, args.delta)
