"""Bổ sung toàn văn từ danh sách RSS; checkpoint từng bài, hỗ trợ pipeline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import trafilatura
from googlenewsdecoder import gnewsdecoder

BASE = Path(__file__).resolve().parent
DECODE_LOCK = threading.Lock()
FIELDS = ['article_id', 'ticker', 'date', 'source', 'type', 'title', 'url', 'publisher_url', 'text', 'fetch_status', 'error_reason', 'http_status', 'extraction_method', 'word_count', 'has_fulltext', 'entity_mentioned', 'attempts', 'fetched_at_utc']
ALIASES = {'VNG': ['VNG', 'VNZ', 'ZaloPay', 'Zalo Pay'], 'VPB': ['VPBank', 'VPBank NEO'], 'VCB': ['Vietcombank', 'VCB', 'Digibank'], 'HDB': ['HDBank', 'HD Bank'], 'ACB': ['ACB', 'Á Châu']}


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields=FIELDS):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def choose(rows, per_company=50):
    """Mẫu tái lập, luân phiên nguồn báo; không chọn toàn bộ từ một báo lớn."""
    groups = defaultdict(lambda: defaultdict(list))
    seen = set()
    for row in rows:
        ticker = row.get('ticker') or row.get('bank')
        title_key = re.sub(r'\W+', ' ', row['title'].lower()).strip()
        key = (ticker, title_key)
        if ticker not in ALIASES or key in seen:
            continue
        seen.add(key)
        row = dict(row, ticker=ticker)
        row['article_id'] = hashlib.sha256((ticker+'|'+row['url']).encode()).hexdigest()[:24]
        groups[ticker][row.get('source') or 'unknown'].append(row)
    result = []
    rng = random.Random(20261015)
    for ticker in sorted(groups):
        buckets = groups[ticker]
        for bucket in buckets.values():
            bucket.sort(key=lambda r: (r.get('date', ''), r['url']))
            rng.shuffle(bucket)
        sources = sorted(buckets)
        selected = []
        while len(selected) < per_company and any(buckets.values()):
            for source in sources:
                if buckets[source] and len(selected) < per_company:
                    selected.append(buckets[source].pop())
        result.extend(selected)
    return result


def extract(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    domain = urlparse(url).hostname or ''
    preferred = {'baodautu.vn': '#content_detail_news', 'bnews.vn': '.b-entry-details', 'thoibaonganhang.vn': '.__MASTERCMS_CONTENT'}
    for host, selector in preferred.items():
        if domain == host or domain.endswith('.'+host):
            node = soup.select_one(selector)
            if node:
                for extra in node.select('script,style,aside,.related,.related-news,.box-related'):
                    extra.decompose()
                return node.get_text('\n', strip=True), 'publisher_selector:'+selector
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False, favor_precision=True) or ''
    method = 'trafilatura'
    if len(text.split()) < 100:
        for node in soup.select('script,style,nav,footer,header,aside,form'):
            node.decompose()
        candidates = []
        for selector in ('article', '[itemprop="articleBody"]', '.detail-content', '.fck_detail', '.article-content', '.content-detail', '.detail__content', '.dt-news__content'):
            for node in soup.select(selector):
                candidates.append('\n'.join(p.get_text(' ', strip=True) for p in node.select('p')))
        fallback = max(candidates, key=len, default='')
        if len(fallback) > len(text):
            text, method = fallback, 'article_selector'
    for marker in ('Kết nối truyền thông\ncùng 24HMONEY', 'Tặng bài viết\nĐối với thành viên', '\nTin cùng chuyên mục\n'):
        text = text.split(marker, 1)[0]
    return text.strip(), method


def fetch_one(row, attempts=2, timeout=20):
    result = {key: row.get(key, '') for key in FIELDS}
    result.update(text='', has_fulltext=False, entity_mentioned=False, publisher_url=row.get('publisher_url', ''), fetch_status='pending')
    for attempt in range(1, attempts+1):
        result.update(attempts=attempt, fetched_at_utc=datetime.now(timezone.utc).isoformat(), error_reason='')
        try:
            target = result['publisher_url'] or row['url']
            if urlparse(target).hostname == 'news.google.com':
                with DECODE_LOCK:
                    decoded = gnewsdecoder(target)
                    time.sleep(1.2)
                target = decoded.get('decoded_url', '')
                if not target or urlparse(target).hostname == 'news.google.com':
                    result.update(fetch_status='decode_failed', error_reason=str(decoded.get('message') or decoded.get('error') or 'Không trả URL báo gốc')[:1000])
                    if attempt < attempts:
                        time.sleep(2*attempt)
                        continue
                    return result
            if urlparse(target).scheme not in ('http', 'https'):
                result.update(fetch_status='invalid_url', error_reason='URL không phải HTTP(S)')
                return result
            result['publisher_url'] = target
            response = requests.get(target, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0 (compatible; DBIResearch/1.0)', 'Accept-Language': 'vi,en;q=0.8'})
            result['http_status'] = response.status_code
            if response.status_code >= 400:
                result.update(fetch_status='http_error', error_reason=f'HTTP {response.status_code}')
                if response.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                    time.sleep(3*attempt)
                    continue
                return result
            result['publisher_url'] = response.url
            if urlparse(response.url).path in ('', '/'):
                result.update(fetch_status='redirected_to_home', error_reason='URL trả về trang chủ, không phải bài báo')
                return result
            if not response.encoding or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding
            text, method = extract(response.text, response.url)
            words = len(text.split())
            mentioned = any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)', text, re.I) for a in ALIASES[row['ticker']])
            # Chỉ là cổng chất lượng tự động, chưa thay thế đọc kiểm tra nội dung.
            quality = words >= 100 and len(text) >= 600
            status = 'too_short' if not quality else 'entity_mismatch' if not mentioned else 'success'
            result.update(text=text, word_count=words, extraction_method=method, has_fulltext=status=='success', entity_mentioned=mentioned, fetch_status=status, error_reason='' if status=='success' else 'Không tìm thấy thực thể trong nội dung' if status=='entity_mismatch' else 'Nội dung dưới 100 từ hoặc 600 ký tự')
            return result
        except requests.RequestException as exc:
            result.update(fetch_status='download_failed', error_reason=f'{type(exc).__name__}: {exc}'[:1000])
        except Exception as exc:
            # Lỗi thư viện ngoài cần ghi vào checkpoint, không làm mất toàn bộ lượt chạy.
            result.update(fetch_status='processing_failed', error_reason=f'{type(exc).__name__}: {exc}'[:1000])
        if attempt < attempts:
            time.sleep(2*attempt)
    return result


def enrich(rows, output, workers=3, attempts=2, retry_failed=False, refresh_domains=()):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / 'enriched_news.csv'
    prior = {r['article_id']: r for r in read_csv(checkpoint)} if checkpoint.exists() else {}
    selected_ids = {r['article_id'] for r in rows}
    results = {key: value for key, value in prior.items() if key in selected_ids}
    todo = []
    for r in rows:
        old = results.get(r['article_id'], {})
        refresh = any(domain in old.get('publisher_url','') for domain in refresh_domains)
        if not old or refresh or (retry_failed and old['fetch_status']!='success'):
            todo.append({**r, 'publisher_url':old.get('publisher_url','')})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, row, attempts): row for row in todo}
        for future in as_completed(futures):
            row = future.result()
            results[row['article_id']] = row
            write_csv(checkpoint, [results[r['article_id']] for r in rows if r['article_id'] in results])
            print(f"[{len(results)}/{len(rows)}] {row['ticker']} {row['fetch_status']} {row['word_count']} words", flush=True)
    complete = [results[r['article_id']] for r in rows]
    summaries = []
    for ticker in sorted({r['ticker'] for r in rows}):
        subset = [r for r in complete if r['ticker'] == ticker]
        counts = Counter(r['fetch_status'] for r in subset)
        summaries.append(dict(ticker=ticker, selected=len(subset), source_count=len({r['source'] for r in subset}), success=counts['success'], success_percent=round(100*counts['success']/len(subset), 2), entity_not_found=sum(str(r['entity_mentioned']).lower() != 'true' for r in subset if r['fetch_status']=='success'), statuses=json.dumps(counts, ensure_ascii=False)))
    write_csv(output/'summary.csv', summaries, list(summaries[0]))
    by_source = []
    for ticker, source in sorted({(r['ticker'], r['source']) for r in complete}):
        subset = [r for r in complete if (r['ticker'], r['source']) == (ticker, source)]
        by_source.append(dict(ticker=ticker, source=source, selected=len(subset), success=sum(r['fetch_status']=='success' for r in subset)))
    write_csv(output/'by_source.csv', by_source, list(by_source[0]))
    write_csv(output/'failed_news.csv', [r for r in complete if r['fetch_status']!='success'])
    metadata = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), selected=len(rows), statuses=dict(Counter(r['fetch_status'] for r in complete)), workers=workers, max_attempts=attempts, quality_gate='>=100 whitespace words, >=600 characters, entity alias present, not homepage; human QA still required')
    (output/'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Thử nghiệm bổ sung toàn văn nguồn 2', '', '| Đơn vị | Bài thử | Số nguồn báo | Đạt cổng toàn văn | Tỷ lệ % |', '|---|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f"| {r['ticker']} | {r['selected']} | {r['source_count']} | {r['success']} | {r['success_percent']} |")
    lines += ['', 'Mẫu luân phiên theo tên nguồn báo, seed cố định; không phải mẫu ngẫu nhiên đại diện toàn kho. VNG là tập đoàn, chưa đồng nhất ZaloPay. Thành công nghĩa là qua cổng độ dài, có alias thực thể và không phải trang chủ; chưa chứng minh bài đúng chủ đề DBI hoặc không lẫn nội dung thừa. Kiểm tra URL và nội dung trước khi đưa vào DBI.', '', 'Các tệp: enriched_news.csv (checkpoint từng bài), failed_news.csv, summary.csv, by_source.csv, metadata.json. Chạy lại cùng lệnh sẽ tiếp tục phần chưa chạy; --retry-failed để thử lại bài lỗi. Không sửa raw_news.csv/clean_news.csv cũ.']
    (output/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    return complete


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=BASE.parents[1]/'output/raw/press_2/clean_news.csv')
    parser.add_argument('--output', type=Path, default=BASE.parents[1]/'output/processed/press_2_fulltext')
    parser.add_argument('--per-company', type=int, default=50, help='Số bài mỗi đơn vị; dùng số lớn để xử lý toàn kho')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--attempts', type=int, default=2)
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--refresh-domains', nargs='*', default=[], help='Tải lại các tên miền sau khi sửa selector, giữ URL đã giải mã')
    args = parser.parse_args()
    if min(args.per_company, args.workers, args.attempts) < 1:
        parser.error('Các tham số số lượng phải >=1')
    selected = choose(read_csv(args.input), args.per_company)
    if not selected:
        parser.error('Không tìm thấy bài phù hợp')
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output/'sample_manifest.csv', selected, ['article_id','ticker','date','source','title','url'])
    enrich(selected, args.output, args.workers, args.attempts, args.retry_failed, args.refresh_domains)
